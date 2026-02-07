# Quick Start Guide - RAON Vending Machine on Raspberry Pi 4

## 5-Minute Quick Setup

### What You Need
- Raspberry Pi 4 with Raspberry Pi OS (Bullseye or later)
- Touchscreen display
- Internet connection
- SSH access or keyboard/mouse

### Step 1: Download Setup Script
```bash
cd ~
wget https://raw.githubusercontent.com/rphlcarlos/raon-vending-rpi4/main/setup-rpi4.sh
chmod +x setup-rpi4.sh
```

### Step 2: Run Setup
```bash
./setup-rpi4.sh
```

This will:
- ✅ Update system packages
- ✅ Install Python dependencies
- ✅ Enable GPIO and Serial interfaces
- ✅ Set up systemd service
- ✅ Configure permissions

### Step 3: Configuration
```bash
cd ~/raon-vending
cp config.example.json config.json
nano config.json  # Edit as needed
```

### Step 4: First Run
```bash
python3 main.py
```

## Hardware Wiring

### GPIO Pins (BCM Numbering)

| Component | Pin | Purpose |
|-----------|-----|---------|
| Coin Acceptor | GPIO17 | Coin pulse input |
| Coin Hopper 1₱ Motor | GPIO24 | Motor control |
| Coin Hopper 5₱ Motor | GPIO25 | Motor control |
| Coin Hopper 1₱ Sensor | GPIO26 | Feedback input |
| Coin Hopper 5₱ Sensor | GPIO27 | Feedback input |
| DHT11 (Components) | GPIO4 | I2C data |
| DHT11 (Payment) | GPIO17 | I2C data |

### Serial Devices

| Device | Port | Baud Rate |
|--------|------|-----------|
| Bill Acceptor (TB74) | /dev/ttyUSB0 | 9600 |
| ESP32 Motor Control | /dev/ttyAMA0 | 115200 |

## Testing Hardware

### Test Coin Acceptor
```bash
python3 simulate_coin.py
```

### Test Bill Acceptor
```python
from bill_acceptor import MockBillAcceptor
acceptor = MockBillAcceptor()
acceptor.simulate_bill_accepted(100)
print(acceptor.get_received_amount())
```

### Test DHT11 Sensor
```python
from dht11_handler import DHT11Sensor
sensor = DHT11Sensor(pin=4)
humidity, temp = sensor.read()
print(f"Temp: {temp}°C, Humidity: {humidity}%")
```

## Running as a Service

### Enable Automatic Startup
```bash
sudo systemctl enable raon-vending
sudo systemctl start raon-vending
```

### View Logs
```bash
sudo journalctl -u raon-vending -f
```

### Stop Service
```bash
sudo systemctl stop raon-vending
```

## Troubleshooting

### GPIO Permission Denied
```bash
sudo usermod -a -G gpio $USER
# Log out and back in
```

### Serial Port Not Found
```bash
# List available ports
ls /dev/tty*

# Check permissions
ls -l /dev/ttyUSB0
sudo usermod -a -G dialout $USER
```

### DHT11 Not Reading
```bash
# Enable I2C
sudo raspi-config nonint do_i2c 0

# Test I2C
i2cdetect -y 1
```

### Display Rotation Not Working
```bash
# Manual rotation
xrandr -o right    # 90° clockwise
xrandr -o left     # 90° counter-clockwise
xrandr -o normal   # Reset
```

## Configuration Reference

### config.json Options

```json
{
  "currency_symbol": "₱",           // Currency display
  "always_fullscreen": true,        // Auto fullscreen on startup
  "allow_decorations_for_admin": false,  // Window decorations
  "rotate_display": "normal",       // Display rotation: normal, left, right, inverted
  "esp32_host": "192.168.4.1"      // ESP32 IP address
}
```

## Common Tasks

### Add New Product
1. Click "Admin" on start screen
2. Enter admin password (default: none)
3. Click "Add Item"
4. Fill in details
5. Click "Save"

### Assign Product to Slot
1. Click "Admin" → "Assign Items"
2. Select item from dropdown
3. Click slots to select them (highlighted in green)
4. Click "Assign Selected"
5. Click "Save"

### View Temperature/Humidity
- Displayed in top-right of kiosk screen
- Updates every 2 seconds
- Shows both components area and payment area sensors

## Next Steps

- [ ] Configure all hardware pins in config.json
- [ ] Connect and test coin acceptor
- [ ] Connect and test bill acceptor
- [ ] Verify DHT11 sensors
- [ ] Add your inventory items
- [ ] Assign items to slots
- [ ] Enable kiosk mode in systemd

## Support

For issues or questions:
1. Check [Troubleshooting Guide](README-RPi4.md#troubleshooting)
2. View [GitHub Issues](https://github.com/rphlcarlos/raon-vending-rpi4/issues)
3. Check [Full Documentation](README-RPi4.md)

## Version Info

- **Application**: RAON Vending Machine v1.0.0
- **Platform**: Raspberry Pi 4
- **OS**: Raspberry Pi OS (Bullseye+)
- **Python**: 3.7+

---

Happy vending! 🎉
