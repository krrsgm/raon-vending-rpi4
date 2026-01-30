# Raspberry Pi 4 Quick Setup Guide

## Prerequisites
- Raspberry Pi 4 with Raspbian OS installed
- Internet connection

## Installation Steps

### 1. Clone or Download the Project
```bash
cd ~/Desktop
unzip raon-vending-rpi4-main.zip
cd raon-vending-rpi4-main
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Update pip and Install Dependencies
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements-rpi4.txt
```

### 4. Run the Application
```bash
python3 main.py
```

## Troubleshooting

### If you get "externally-managed-environment" error:
Use the virtual environment as shown above. This is the correct way.

### If you get "ModuleNotFoundError":
Make sure the virtual environment is activated:
```bash
source venv/bin/activate
```

### If PIL/Pillow fails to install:
```bash
sudo apt-get update
sudo apt-get install python3-tk python3-dev libjpeg-dev zlib1g-dev
pip install --upgrade pillow
```

### To activate venv in the future:
```bash
cd ~/Desktop/raon-vending-rpi4-main
source venv/bin/activate
python3 main.py
```

## Hardware Configuration
Make sure your hardware is connected:
- DHT sensor (GPIO pin)
- Coin acceptor (USB/Serial)
- Bill acceptor (USB/Serial)
- Other peripherals as configured

## For Autostart (Optional)
See the `deploy/raon-vending.service` file for systemd service setup.
