# TEC Peltier Module Controller

## Overview

The TEC (Thermoelectric Cooler) Peltier module controller automatically manages refrigeration for the vending machine based on real-time temperature readings from DHT22 sensors.

## Features

- **Automatic Temperature Control**: Monitors temperature and enables/disables TEC based on target range
- **Hysteresis Control**: Prevents rapid on/off cycling with configurable temperature hysteresis
- **Multi-Sensor Support**: Can monitor different areas (components, payment)
- **Dynamic Configuration**: Adjust target temperature and hysteresis at runtime
- **Thread-Safe Operation**: Safe concurrent access to controller state
- **Manual Override**: Can manually turn TEC on/off regardless of temperature
- **Status Monitoring**: Get real-time status of TEC and sensor readings

## GPIO Configuration

| Component | GPIO | Purpose |
|-----------|------|---------|
| DHT22 Sensor 1 | GPIO27 | Temperature/humidity monitoring (components area) |
| TEC Relay Control | GPIO26 | Controls relay for TEC Peltier module |

## Configuration

Add the following to `config.json` to enable and configure the TEC controller:

```json
{
  "hardware": {
    "dht22_sensors": {
      "sensor_1": {
        "enabled": true,
        "gpio_pin": 27
      }
    },
    "tec_relay": {
      "enabled": true,
      "gpio_pin": 26,
      "target_temp": 10.0,
      "hysteresis": 1.0
    }
  }
}
```

### Configuration Parameters

- **enabled**: Enable/disable TEC controller (default: true)
- **gpio_pin**: GPIO pin for relay control (default: 26)
- **target_temp**: Target temperature in Celsius (default: 10.0)
- **hysteresis**: Temperature tolerance in Celsius (default: 1.0)

### How It Works

With `target_temp=10.0` and `hysteresis=1.0`:

- **Activation Range**: 9°C to 11°C
- **TEC turns ON** when temperature exceeds 11°C (target + hysteresis)
- **TEC turns OFF** when temperature falls below 9°C (target - hysteresis)
- **No action** when between 9-11°C (prevents cycling)

## Usage

### Basic Usage

The TEC controller is automatically initialized by the main application if enabled in config:

```python
# Automatic initialization in main.py
if self.tec_controller:
    status = self.tec_controller.get_status()
```

### Manual Control

```python
from tec_controller import TECController

# Create controller
tec = TECController(sensor_pin=27, relay_pin=26, target_temp=10.0)

# Start automatic control
tec.start()

# Check status
status = tec.get_status()
print(f"Temperature: {status['current_temp']}°C")
print(f"TEC enabled: {status['enabled']}")

# Change target temperature
tec.set_target_temp(15.0)

# Manual control (overrides automatic)
tec.manual_on()   # Force TEC on
tec.manual_off()  # Force TEC off

# Stop and cleanup
tec.stop()
tec.cleanup()
```

## Status Information

The `get_status()` method returns:

```python
{
    'enabled': True,                    # TEC relay is ON
    'current_temp': 12.5,              # Current temperature in °C
    'current_humidity': 45.2,          # Current humidity in %
    'target_temp': 10.0,               # Target temperature
    'hysteresis': 1.0,                 # Hysteresis value
    'temp_on_threshold': 11.0,         # Turn on if temp exceeds this
    'temp_off_threshold': 9.0,         # Turn off if temp falls below this
    'last_update': 1234567890.5        # Unix timestamp of last sensor read
}
```

## Testing

Run the test script to verify TEC controller operation:

```bash
python3 test_tec_controller.py
```

The test will:
1. Initialize the TEC controller
2. Monitor temperature for 30 seconds
3. Test dynamic configuration changes
4. Display real-time TEC status

Expected output:
```
[TEST] TEC Controller Test
[TEST] Starting TEC controller...
[TEST] Running for 30 seconds...

[ 1] Temp: 12.5°C | Humidity: 45.2% | TEC: ON  | Range: 9.0-11.0°C
[ 2] Temp: 12.3°C | Humidity: 45.1% | TEC: ON  | Range: 9.0-11.0°C
...
```

## Hardware Requirements

### TEC Peltier Module
- Operating voltage: 12V DC
- Maximum current: 5-10A (model dependent)
- PWM capable for variable cooling

### Relay Control
- GPIO26 controls relay module
- Relay switches 12V power to TEC
- Pull-up resistor recommended on GPIO pin

### DHT22 Sensor
- 3.3V power supply
- GPIO27 data pin
- 10kΩ pull-up resistor on data line

## Wiring Diagram

```
Raspberry Pi GPIO26 (TEC Relay)
        ↓
    [Relay Module]
        ↓
    12V Power Supply → TEC Peltier Module
```

## Troubleshooting

### TEC not turning on
1. Check GPIO26 is set to correct pin in config
2. Verify relay module is receiving 3.3V signal
3. Test GPIO with: `python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(26, GPIO.OUT); GPIO.output(26, GPIO.HIGH)"`

### Temperature readings are N/A
1. Verify DHT22 sensor connected to GPIO27
2. Check 10kΩ pull-up resistor is installed
3. Run DHT22 test: `python3 -c "from dht11_handler import DHT22Sensor; s = DHT22Sensor(27); print(s.read())"`

### TEC cycling rapidly (on/off)
1. Increase hysteresis value in config
2. Check that sensor is stable and not fluctuating
3. Ensure TEC module is properly mounted with thermal contact

## Performance Considerations

- **Minimum read interval**: 2 seconds (DHT22 hardware limitation)
- **Control loop interval**: 2 seconds
- **Response time**: ~2-4 seconds from temperature threshold to TEC state change
- **Power consumption**: Relay on (5W TEC) + monitoring (0.1W sensors)

## Future Enhancements

- [ ] PID control for smoother temperature management
- [ ] Multiple TEC zones with different target temperatures
- [ ] History logging of temperature and TEC usage
- [ ] Web dashboard for remote monitoring
- [ ] Predictive cooling based on ambient temperature
- [ ] Error detection and alerts (sensor failure, overcurrent)

## References

- [DHT22 Sensor Documentation](https://www.sparkfun.com/datasheets/Sensors/Temperature/DHT22.pdf)
- [TEC Module Basics](https://en.wikipedia.org/wiki/Thermoelectric_cooling)
- [Raspberry Pi GPIO Reference](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)
