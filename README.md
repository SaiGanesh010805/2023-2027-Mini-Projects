# IoT Forensic Audit & Security System
A real-time security dashboard for IoT devices using Flask, MQTT, and AI-based anomaly detection.

## Features
- **Real-time Monitoring:** DHT22 sensor data via MQTT.
- **AI Anomaly Detection:** Random Forest model flags suspicious login times.
- **VPN Detection:** Integration with IP-API to identify proxy users.
- **Multi-Channel Alerts:** Instant notifications via Discord and Telegram.

## Tech Stack
- Python (Flask, SQLAlchemy, Scikit-Learn)
- MQTT (HiveMQ Broker)
- Frontend: HTML5, Bootstrap