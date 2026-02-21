#!/bin/bash
# Setup script for Raspberry Pi 4 - RAON Vending Machine Kiosk
# Run this on your Raspberry Pi 4 to prepare the environment

set -e  # Exit on error

echo "========================================="
echo "RAON Vending Machine - Raspberry Pi 4 Setup"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running on Raspberry Pi
if [[ ! -f /proc/device-tree/model ]]; then
    echo -e "${YELLOW}Warning: Not running on Raspberry Pi${NC}"
    echo "Setup may still proceed, but hardware features won't work."
fi

echo -e "${GREEN}Step 1: Update system packages${NC}"
sudo apt-get update
sudo apt-get upgrade -y

echo -e "${GREEN}Step 2: Install system dependencies${NC}"
sudo apt-get install -y \
    python3-pip \
    python3-dev \
    python3-tk \
    python3-pil \
    python3-pil.imagetk \
    git \
    wget \
    curl \
    libatlas-base-dev \
    libjasper-dev \
    libtiff5 \
    libjasper1 \
    libharfbuzz0b \
    libwebp6 \
    libtiff5 \
    libjasper1

echo -e "${GREEN}Step 3: Enable SPI and I2C interfaces (for sensors)${NC}"
# Enable I2C for DHT11 sensors
sudo raspi-config nonint do_i2c 0
# Enable SPI for potential additional hardware
sudo raspi-config nonint do_spi 0
# Enable Serial for bill acceptor
sudo raspi-config nonint do_serial_hw 0

echo -e "${GREEN}Step 4: Create application directory${NC}"
APP_DIR="/home/$(whoami)/raon-vending"
if [ ! -d "$APP_DIR" ]; then
    mkdir -p "$APP_DIR"
    echo "Created directory: $APP_DIR"
else
    echo "Directory already exists: $APP_DIR"
fi

echo -e "${GREEN}Step 5: Clone or update repository${NC}"
if [ -d "$APP_DIR/.git" ]; then
    cd "$APP_DIR"
    git pull
    echo "Repository updated"
else
    # Placeholder - user should clone their own repo
    echo "Note: Clone your repository to $APP_DIR"
    echo "  cd $APP_DIR && git clone <your-repo-url> ."
fi

echo -e "${GREEN}Step 6: Install Python dependencies${NC}"
cd "$APP_DIR"
pip3 install --upgrade pip
pip3 install -r requirements-rpi4.txt

echo -e "${GREEN}Step 7: Fix GPIO permissions${NC}"
sudo usermod -a -G gpio $(whoami)
echo "GPIO permissions updated (may require logout/login)"

echo -e "${GREEN}Step 8: Create systemd service (optional)${NC}"
sudo tee /etc/systemd/system/raon-vending.service > /dev/null << 'EOF'
[Unit]
Description=RAON Vending Machine Kiosk
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/raon-vending
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created. To enable:"
echo "  sudo systemctl enable raon-vending"
echo "  sudo systemctl start raon-vending"

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Configure GPIO pins in config.json"
echo "2. Connect your hardware (coin acceptor, bill acceptor, sensors)"
echo "3. Run: python3 main.py"
echo ""
echo "For troubleshooting, check:"
echo "  - /var/log/raon-vending.log (if using systemd service)"
echo "  - GPIO pin configuration matches your hardware"
echo "  - Serial ports for bill acceptor (/dev/ttyUSB0, /dev/ttyAMA0, etc.)"
echo ""
