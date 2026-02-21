# RAON Vending Machine Kiosk - Raspberry Pi 4 Edition

A complete touchscreen kiosk application for managing and operating an automated vending machine with coin/bill payment, temperature monitoring, and inventory management.

**This version is optimized for Raspberry Pi 4 with full hardware support.**

## Features

- **Touchscreen UI**: Tkinter-based responsive interface for product selection and checkout
- **Multi-Payment Support**: 
  - Coin acceptor (Allan 123A-Pro): Accepts ₱1, ₱5, ₱10 coins
  - Bill acceptor (TB74): Accepts ₱20, ₱50, ₱100, ₱500, ₱1000 bills
- **Inventory Management**: Admin interface for adding/editing products and assigning slots
- **Hardware Monitoring**: DHT11 sensors for temperature and humidity in components and payment areas
- **Motor Control**: ESP32-based motor control for vending via multiplexers (CD74HC4067)
- **Change Dispensing**: Automatic coin hopper for dispensing change
- **Kiosk Mode**: Full-screen operation with optional window decorations

## Hardware Requirements

### Raspberry Pi Setup
- **Board**: Raspberry Pi 4 (2GB RAM minimum, 4GB recommended)
- **Storage**: 32GB microSD card (Class 10 or better)
- **OS**: Raspberry Pi OS (Bullseye or later)
- **Power**: 5V 3A USB-C power supply

### Connected Devices
| Device | Interface | Pin/Port | Notes |
|--------|-----------|----------|-------|
| Coin Acceptor (Allan 123A-Pro) | GPIO | Pin 17 | Coin pulse detection |
| Bill Acceptor (TB74) | RS-232 (MAX232) | `/dev/ttyAMA0` | Via MAX232 level converter |
| DHT11 Sensor #1 (Components) | GPIO | Pin 4 | I2C interface |
| DHT11 Sensor #2 (Payment Area) | GPIO | Pin 17 | I2C interface |
| Coin Hopper (1₱) | GPIO | Pin 24 | Motor output |
| Coin Hopper (5₱) | GPIO | Pin 25 | Motor output |
| Coin Hopper Sensor (1₱) | GPIO | Pin 26 | Feedback input |
| Coin Hopper Sensor (5₱) | GPIO | Pin 27 | Feedback input |
| ESP32 (Motor Control) | UART | `/dev/ttyAMA0` | Serial communication |
| Display/Touchscreen | HDMI | Physical connector | Via X11 |

## Installation

### Quick Start (Automated)

```bash
# SSH into your Raspberry Pi
ssh pi@<raspberrypi.local>

# Download and run setup script
curl -sSL https://raw.githubusercontent.com/rphlcarlos/raon-vending-rpi4/main/setup-rpi4.sh | bash

# Or download and run manually
wget https://raw.githubusercontent.com/rphlcarlos/raon-vending-rpi4/main/setup-rpi4.sh
chmod +x setup-rpi4.sh
./setup-rpi4.sh
```

### Manual Installation

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install dependencies
sudo apt-get install -y python3-pip python3-tk python3-pil git

# Clone repository
cd ~
git clone https://github.com/rphlcarlos/raon-vending-rpi4.git raon-vending
cd raon-vending

# Install Python packages
pip3 install -r requirements-rpi4.txt

# Enable GPIO permissions for your user
sudo usermod -a -G gpio $(whoami)

# Enable I2C and Serial interfaces
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_serial_hw 0
```

**Note**: After enabling GPIO permissions, you may need to log out and back in for changes to take effect.

## Configuration

### config.json

Create or edit `config.json` in the application directory:

```json
{
  "currency_symbol": "₱",
  "always_fullscreen": true,
  "allow_decorations_for_admin": false,
  "rotate_display": "normal",
  "esp32_host": "192.168.4.1",
  "coin_hoppers": {
    "one_peso": {
      "motor_pin": 24,
      "sensor_pin": 26
    },
    "five_peso": {
      "motor_pin": 25,
      "sensor_pin": 27
    }
  }
}
```

### GPIO Pin Configuration

Update the following files if your hardware uses different pins:

- **coin_handler.py**: `coin_pin` (default: 17)
- **coin_hopper.py**: Motor and sensor pins in config.json
- **dht11_handler.py**: Sensor pins (GPIO 4, 17)

### Serial Port Configuration

For the bill acceptor (TB74) with MAX232:

```python
# In payment_handler.py initialization:
# Default: Uses /dev/ttyAMA0 (hardware UART with MAX232)
PaymentHandler(config, coin_pin=17)

# Or specify custom port if needed:
PaymentHandler(config, coin_pin=17, bill_port='/dev/ttyUSB0')
```

Common serial ports on RPi:
- `/dev/ttyAMA0` - Built-in UART (Pi 4) ← **Default for MAX232**
- `/dev/ttyUSB0` - USB serial converter (first)
- `/dev/ttyUSB1` - USB serial converter (second)
- `/dev/ttyS0` - Alternative built-in UART

**Hardware Connection**: TB74 (RS-232) ↔ MAX232 (Level Converter) ↔ GPIO 14/15 (RPi UART)

For detailed MAX232 wiring, see **HARDWARE_MAX232_SETUP.md**

## Running the Application

### Development Mode
```bash
cd ~/raon-vending
python3 main.py
```

### Kiosk Mode (Systemd Service)

```bash
# Enable and start the service
sudo systemctl enable raon-vending
sudo systemctl start raon-vending

# View status
sudo systemctl status raon-vending

# View logs
sudo journalctl -u raon-vending -f
```

### On Startup (via crontab)

```bash
# Edit crontab
crontab -e

# Add this line:
@reboot cd /home/pi/raon-vending && /usr/bin/python3 main.py
```

## Directory Structure

```
raon-vending/
├── main.py                    # Entry point
├── config.json               # Configuration file
├── item_list.json            # Inventory items
├── assigned_items.json       # Slot assignments
├── 
├── # UI Screens
├── kiosk_app.py             # Main kiosk interface
├── selection_screen.py       # Admin/User selection
├── item_screen.py           # Product detail view
├── cart_screen.py           # Shopping cart & checkout
├── admin_screen.py          # Admin panel
├── assign_items_screen.py   # Slot assignment UI
├──
├── # Hardware Handlers
├── coin_handler.py          # Coin acceptor (Allan 123A-Pro)
├── coin_hopper.py           # Coin dispensing
├── bill_acceptor.py         # Bill acceptor (TB74)
├── dht11_handler.py         # Temperature/humidity sensors
├── payment_handler.py       # Payment processing
├── esp32_client.py          # ESP32 communication
├──
├── # Utilities
├── rpi_gpio_mock.py         # GPIO mocking for testing
├── fix_paths.py             # File path utilities
├── simulate_coin.py         # Coin simulator for testing
├──
├── requirements.txt         # Core dependencies
├── requirements-rpi4.txt    # Raspberry Pi 4 dependencies
├── setup-rpi4.sh           # Setup script
└── README.md               # This file
```

## Troubleshooting

### GPIO Permissions Error
```
RuntimeError: No access to /dev/mem
```

**Solution**: Ensure your user is in the `gpio` group:
```bash
sudo usermod -a -G gpio $(whoami)
# Log out and back in
```

### Serial Port Not Found
```
SerialException: could not open port /dev/ttyAMA0
```

**Solutions for MAX232 (Hardware UART)**:
1. Verify UART is enabled: `sudo raspi-config nonint get_serial_hw`
2. Check connection: `ls -l /dev/ttyAMA0`
3. If needed, add user to dialout group: `sudo usermod -a -G dialout $(whoami)`
4. Verify MAX232 capacitors are installed (see HARDWARE_MAX232_SETUP.md)
5. Check ground connections between RPi, MAX232, and TB74

**For USB Serial Adapter**:
1. Check device: `lsusb`
2. Check port: `ls /dev/ttyUSB*`
3. Verify permissions: `ls -l /dev/ttyUSB0`

### DHT11 Sensor Timeouts
```
RuntimeError: DHT11 sensor not responding
```

**Solutions**:
1. Verify wiring and pull-up resistors (4.7kΩ)
2. Try different GPIO pins
3. Check I2C is enabled: `sudo raspi-config nonint get_i2c`
4. Check sensor with: `python3 -c "import board; import adafruit_dht; sensor = adafruit_dht.DHT11(board.D4); print(sensor.temperature)"`

### Display Not Rotating
The automatic rotation uses `xrandr` on X11:
```bash
# Manual rotation test
xrandr -o right   # 90° clockwise
xrandr -o left    # 90° counter-clockwise
xrandr -o inverted # 180°
xrandr -o normal   # Reset
```

### Touchscreen Not Working
Ensure your touchscreen driver is installed:
```bash
# For Adafruit touchscreen
sudo apt-get install -y libts-bin ts_calibrate
```

## Testing

### Test Coin Handler
```bash
cd ~/raon-vending
python3 simulate_coin.py
```

### Test Bill Acceptor (Mock)
```python
from bill_acceptor import MockBillAcceptor

acceptor = MockBillAcceptor()
acceptor.connect()
acceptor.start_reading()
acceptor.simulate_bill_accepted(100)  # Simulate ₱100 bill
print(f"Received: ₱{acceptor.get_received_amount()}")
```

### Test DHT11 Sensors
```python
from dht11_handler import DHT11Sensor

sensor = DHT11Sensor(pin=4)
humidity, temp = sensor.read()
print(f"Temp: {temp}°C, Humidity: {humidity}%")
```

## Performance Optimization for RPi4

1. **Reduce UI refresh rate** if experiencing lag
2. **Disable screen rotation** in config.json if not needed
3. **Use hardware acceleration** for Tkinter rendering (if available)
4. **Monitor temperatures**: DHT11 readings help identify thermal issues
5. **Use SSD cache** for images instead of re-loading

## Security Considerations

- **Run in kiosk mode** to prevent user access to system
- **Disable SSH** on public-facing machines
- **Use strong admin passwords** if implementing authentication
- **Regularly update** OS and Python packages
- **Disable unnecessary services** (SSH, cron, etc.)

## Admin Features

### Access Admin Panel
1. Press ESC on the selection screen
2. Enter admin credentials (if configured)
3. Available functions:
   - Add/Edit/Remove inventory items
   - Assign items to vending slots
   - View system status
   - Configure hardware

### Slot Assignment
- 60 total slots organized in a 6×10 grid
- Horizontal slider for viewing all slots
- Drag to select multiple slots for quick assignment
- Support for images, descriptions, and pricing

## Troubleshooting Hardware Integration

### ESP32 Motor Control
- Ensure ESP32 is flashed with `vending_controller.ino`
- Verify UART connection: RX→TX, TX→RX, GND→GND
- Check IP address in config.json

### Coin Acceptor (Allan 123A-Pro)
- Verify calibration for ₱1, ₱5, ₱10 coins
- Use GPIO pin 17 (or configure differently)
- Test with `simulate_coin.py`

### Bill Acceptor (TB74)
- Verify serial port: Default `/dev/ttyAMA0` (hardware UART with MAX232)
- Check baud rate (9600 for TB74)
- Supported bills: ₱20, ₱50, ₱100, ₱500, ₱1000
- MAX232 Level Converter required (see HARDWARE_MAX232_SETUP.md)
- Verify all 4 capacitors installed on MAX232
- Check ground connections between RPi ↔ MAX232 ↔ TB74
- Enable in config if not auto-detected

## Development

### Adding New Hardware

Create a new handler file following the pattern:

```python
# my_device_handler.py
import threading
from queue import Queue

class MyDevice:
    def __init__(self, pin=17):
        self.pin = pin
        # Initialize hardware
        
    def read(self):
        # Read from device
        pass
        
    def cleanup(self):
        # Clean up resources
        pass
```

Then integrate into `payment_handler.py` or relevant screen.

### Running Tests
```bash
pytest
```

## Contributing

This is part of the RAON Vending Machine project. For contributions, please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly on actual RPi4 hardware
5. Submit a pull request

## Support and Issues

For bugs, feature requests, or questions:
- Check the [GitHub Issues](https://github.com/rphlcarlos/raon-vending-rpi4/issues)
- Review the [Documentation](https://github.com/rphlcarlos/raon-vending-rpi4/wiki)
- Contact the maintainers

## License

[Add appropriate license - e.g., MIT, GPL, etc.]

## Changelog

### v1.0.0 (2025-11-12)
- Initial Raspberry Pi 4 optimized release
- Full coin and bill payment support
- DHT11 temperature/humidity monitoring
- ESP32 motor control integration
- Admin interface for slot assignment
- Kiosk mode with display rotation

## Acknowledgments

- Allan coin acceptor protocols and calibration
- Adafruit libraries for sensor integration
- Raspberry Pi Foundation for excellent documentation
- Community contributions and testing feedback
