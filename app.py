import paho.mqtt.client as mqtt
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import requests
from sklearn.ensemble import RandomForestClassifier

# --- APP SETUP ---
app = Flask(__name__)
app.secret_key = "super_secret_audit_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///audit_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- DISCORD CONFIG ---
# PASTE YOUR WEBHOOK URL HERE
DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1496048197846437889/AKySDvpTYmdxkLrmR0tx-YDLuCwbUufH6tmzOEUTA0Entbh_InVIewhXH30LGPXv9jP6'

# --- TELEGRAM CONFIG ---
TELEGRAM_TOKEN = '8729369826:AAFPDM6UZEoQF6whAU01kcEyjdszNlvRv7k'
CHAT_ID = '1706421138'

# --- ALERT FUNCTIONS ---
def send_discord_alert(message):
    try:
        data = {"content": message}
        response = requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=5)
        if response.status_code == 204:
            print("✅ Discord Forensic Alert Sent Successfully")
    except Exception as e:
        print(f"❌ Discord Alert Failed: {e}")

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Telegram Alert Sent Successfully!")
    except Exception as e:
        print(f"⚠️ Telegram Alert Failed (Normal if on restricted Wi-Fi): {e}")

# --- VPN DETECTION ---
def is_vpn_proxy(ip):
    if ip in ["127.0.0.1", "localhost", "Hardware"]: 
        return False
    try:
        res = requests.get(f"http://ip-api.com/json/{ip}?fields=proxy,hosting,status", timeout=3).json()
        if res.get('status') == 'success':
            return res.get('proxy') or res.get('hosting')
    except:
        pass
    return False

# --- AI MODEL (Random Forest) ---
X_train = [[14, 1], [15, 2], [10, 1], [3, 40], [2, 55], [4, 30]]
y_train = [0, 0, 0, 1, 1, 1] 
model = RandomForestClassifier(n_estimators=10)
model.fit(X_train, y_train)

# --- DATABASE MODEL ---
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    user = db.Column(db.String(50))
    action = db.Column(db.String(200))
    data_value = db.Column(db.String(50))
    ai_status = db.Column(db.String(20))
    ip_address = db.Column(db.String(50))
    vpn_detected = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

# --- MQTT SETUP ---
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        temp, hum = payload.get("temp"), payload.get("hum")
        with app.app_context():
            db.session.add(AuditLog(
                user="ESP32_Sensor", action="Update",
                data_value=f"{temp}, {hum}", ai_status="AUTHORIZED", ip_address="Hardware"
            ))
            db.session.commit()
    except Exception as e:
        print(f"MQTT Error: {e}")

mqtt_client = mqtt.Client(client_id="iot_audit_system", protocol=mqtt.MQTTv311)
mqtt_client.on_message = on_message
mqtt_client.connect("broker.hivemq.com", 1883)
mqtt_client.subscribe("gouthami/security/dht22")
mqtt_client.loop_start()

# --- ROUTES ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.headers.getlist("X-Forwarded-For"):
        user_ip = request.headers.getlist("X-Forwarded-For")[0]
    else:
        user_ip = request.remote_addr
    
    vpn_status = is_vpn_proxy(user_ip)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        hour = datetime.now().hour
        prediction = model.predict([[hour, 1]])[0] 
        ai_res = "⚠️ SUSPICIOUS" if (prediction == 1 or vpn_status) else "✅ SECURE"

        if username == "admin" and password == "1234":
            session['user'] = "admin"
            db.session.add(AuditLog(user="admin", action="Login", ai_status=ai_res, ip_address=user_ip, vpn_detected=vpn_status))
            db.session.commit()
            return redirect(url_for('index'))
        else:
            # LOG FAILED ATTEMPT
            db.session.add(AuditLog(user=username, action="FAILED LOGIN", ai_status="⚠️ SUSPICIOUS", ip_address=user_ip, vpn_detected=vpn_status))
            db.session.commit()

            # CONSTRUCT ALERT MESSAGE
            alert_msg = (
                f"🚨 **IOT SECURITY BREACH DETECTED**\n"
                f"━━━━━━━━━━━━━━━\n"
                f"**User:** `{username}`\n"
                f"**IP Address:** `{user_ip}`\n"
                f"**VPN Status:** {'DETECTED 🚩' if vpn_status else 'Clean ✅'}\n"
                f"**Action:** Access Denied"
            )
            
            # TRIGGER BOTH ALERTS
            send_discord_alert(alert_msg)
            send_telegram_alert(alert_msg)
            
            return "Unauthorized Access Denied", 401

    return render_template('login.html')

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    logs = AuditLog.query.filter(AuditLog.user != "ESP32_Sensor").order_by(AuditLog.id.desc()).limit(15).all()
    sensor = AuditLog.query.filter_by(user="ESP32_Sensor").order_by(AuditLog.id.desc()).first()
    temp, hum = ("0.0", "0.0")
    if sensor and sensor.data_value:
        try:
            parts = sensor.data_value.split(", ")
            temp, hum = parts[0], parts[1]
        except: pass
    return render_template('index.html', logs=logs, latest_temp=temp, latest_hum=hum)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)