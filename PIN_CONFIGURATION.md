# Pin Configuration Guide

Complete pinout documentation for RAON Vending Machine hardware (Raspberry Pi 4, ESP32 modules, Arduino).

## Quick Reference

### Raspberry Pi 4 (BCM GPIO)
| Component | Pin | Pin Name | Purpose |
|-----------|-----|----------|---------|
| DHT22 Sensor 1 (ESP32) | GPIO 36 | ADC1_CH0 | Temperature/Humidity monitor |
| DHT22 Sensor 2 (ESP32) | GPIO 39 | ADC1_CH3 | Temperature/Humidity monitor |
| TEC Relay Control | GPIO 26 | BCM 26 | Peltier cooling module ON/OFF |
| IR Sensor 1 (Bin, ESP32) | GPIO 34 | ADC1_CH6 | Item detection in bin |
| IR Sensor 2 (Bin, ESP32) | GPIO 35 | ADC1_CH7 | Item detection in bin |
| Coin Acceptor | GPIO 17 | BCM 17 | Coin detection input |
| Serial UART TX | GPIO 14 | TXD | Communicate with ESP32 (RXTX cable) |
| Serial UART RX | GPIO 15 | RXD | Communicate with ESP32 (RXTX cable) |

---

## ESP32 - Bill Acceptor & Coin Hopper (`esp32_bill_forward.ino`)

### Hardware Connections
- **USB Serial**: 115200 baud (primary communication)
- **Power**: 5V from USB
- **Bill Acceptor**: Interrupt-driven pulse counting
- **Coin Hoppers**: Motor relay control with sensor feedback

### Pin Definitions

| Component | GPIO | Pin Name | Direction | Purpose |
|-----------|------|----------|-----------|---------|
| **BILL ACCEPTOR** | | | | |
| Bill Pulse Input | GPIO 2 | D2 | INPUT_PULLUP | Detects bill insertion (external interrupt) |
| | | | | |
| **COIN HOPPER - 1-Peso** | | | | |
| Motor Relay | GPIO 9 | D9 | OUTPUT | Controls 1-peso hopper motor |
| Coin Sensor | GPIO 11 | D11 | INPUT | Detects falling 1-peso coins |
| | | | | |
| **COIN HOPPER - 5-Peso** | | | | |
| Motor Relay | GPIO 10 | D10 | OUTPUT | Controls 5-peso hopper motor |
| Coin Sensor | GPIO 12 | D12 | INPUT | Detects falling 5-peso coins |

### Communication Protocol
```
Serial (USB): 115200 baud
Commands:
  DISPENSE_AMOUNT <amount> [timeout_ms]   - Dispense change
  DISPENSE_DENOM <denom> <count> [timeout_ms] - Dispense specific coins
  OPEN <denom>                             - Manually open hopper (1 or 5)
  CLOSE <denom>                            - Manually close hopper
  STATUS                                   - Report hopper status
  STOP                                     - Stop all operations
```

### Arduino Code Reference
```cpp
const int pulsePin = 2;       // Bill acceptor interrupt
const int ONE_MOTOR_PIN = 9;  // 1-peso hopper motor
const int FIVE_MOTOR_PIN = 10; // 5-peso hopper motor
const int ONE_SENSOR_PIN = 14; // 1-peso sensor
const int FIVE_SENSOR_PIN = 15; // 5-peso sensor
```

---

## ESP32 - Vending Controller (`vending_controller.ino`)

Handles motor control for item dispensing.

### Pin Definitions

| Component | GPIO | Pin Name | Direction | Purpose |
|-----------|------|----------|-----------|---------|
| **MOTOR CONTROL** | | | | |
| PWM Output | GPIO 19 | D19 | OUTPUT | Controls motor speed via PWM |
| | | | | |
| **COIN ACCEPTOR** | | | | |
| Coin Detect | GPIO 5 | D5 | INPUT | Detects coin insertions |
| Counter Feedback | GPIO 18 | D18 | INPUT | Optional counter feedback |
| | | | | |
| **SERIAL COMMUNICATION** | | | | |
| Serial2 RX | GPIO 3 | RX2 | INPUT | Receives from Raspberry Pi TX (GPIO 14) |
| Serial2 TX | GPIO 1 | TX2 | OUTPUT | Sends to Raspberry Pi RX (GPIO 15) |

### Communication
- **Serial2**: UART communication with Raspberry Pi
- **Baud Rate**: 115200 (configured in vending_controller.ino)

### Arduino Code Reference
```cpp
const int SERIAL2_RX_PIN = 3;   // ESP32 receives from Pi TX
const int SERIAL2_TX_PIN = 1;   // ESP32 sends to Pi RX
const int PWM_PIN = 19;         // Motor speed control
const int COIN_PIN = 5;         // Coin detect input
const int COUNTER_PIN = 18;     // Counter feedback (optional)
```

---

## Complete Communication Flow

```
┌─────────────────────────────────────────────────────┐
│         Raspberry Pi 4 (Python Application)          │
├─────────────────────────────────────────────────────┤
│ GPIO 14 (TX) ────RXTX Cable──── ESP32 GPIO 3 (RX2)  │
│ GPIO 15 (RX) ────RXTX Cable──── ESP32 GPIO 1 (TX2)  │
│                (115200 baud, RS485)                 │
│                                                      │
│ GPIO 27 ← DHT22 Sensor 1 (Temperature/Humidity)     │
│ GPIO 22 ← DHT22 Sensor 2 (Temperature/Humidity)     │
│ GPIO 26 → TEC Relay (Cooling on/off)                │
│ GPIO 24 ← IR Sensor 1 (Item detection)              │
│ GPIO 25 ← IR Sensor 2 (Item detection)              │
│ GPIO 17 ← Coin Acceptor (Coin detection)            │
└─────────────────────────────────────────────────────┘
│
├──→ ESP32-Bill-Forward (USB Serial 115200)
│    ├─ GPIO 2:  Bill acceptor pulse input
│    ├─ GPIO 12: 1-peso motor relay
│    ├─ GPIO 13: 5-peso motor relay
│    ├─ GPIO 14: 1-peso sensor
│    └─ GPIO 15: 5-peso sensor
│
└──→ ESP32-Vending-Controller (UART Serial2)
     ├─ GPIO 19: Motor PWM control
     ├─ GPIO 5:  Coin detect
     └─ GPIO 18: Counter feedback
```

---

## Pin Usage by Functional Area

### Temperature & Cooling System
```
ESP32 GPIO 36 ──┐
                       ├──→ Temperature Monitor (main.py)
ESP32 GPIO 39 ──┘

Raspberry Pi GPIO 26 ──→ TEC Relay (tec_controller.py)
                        └→ Controls Peltier cooling module
```

### Item Dispensing with Detection
```
Raspberry Pi GPIO 14/15 ─UART─→ ESP32-Vending-Controller (GPIO 19 PWM)
                                └→ Drives motor to dispense items

ESP32 GPIO 34/35 ← IR Sensors in catch bin
                        └→ Detects successful dispensing
```

### Payment & Change
```
Raspberry Pi GPIO 17 ← Coin Acceptor input

Raspberry Pi GPIO 14/15 ─USB/UART─→ ESP32-Bill-Forward
                         ├─ GPIO 2:  Bill acceptor pulses
                         ├─ GPIO 12/13: Hopper motors
                         └─ GPIO 14/15: Hopper sensors
```

---

## Wiring Checklist

### Raspberry Pi → ESP32-Bill-Forward
- [ ] GPIO 14 (TX) → RX pin via RXTX cable (MAX485 module)
- [ ] GPIO 15 (RX) → TX pin via RXTX cable (MAX485 module)
- [ ] GND → GND (common ground)
- [ ] Power: 5V from USB (both devices)

### Raspberry Pi → Temperature Sensors (DHT22)
- [ ] GPIO 27 → DHT22 Sensor 1 data pin
- [ ] GPIO 22 → DHT22 Sensor 2 data pin
- [ ] 5V → DHT22 power pins
- [ ] GND → DHT22 ground pins

### Raspberry Pi → TEC Relay
- [ ] GPIO 26 → Relay module control input
- [ ] 5V → Relay module power
- [ ] GND → Relay module ground
- [ ] Relay NO contact → Peltier + (with diode protection)
- [ ] Relay NC contact → Peltier - 

### Raspberry Pi → IR Sensors (Bin Detection)
- [ ] GPIO 24 → IR Sensor 1
- [ ] GPIO 25 → IR Sensor 2
- [ ] 5V → Sensor power pins
- [ ] GND → Sensor ground pins

### Raspberry Pi → Coin Acceptor
- [ ] GPIO 17 → Coin acceptor pulse input
- [ ] 5V → Coin acceptor power
- [ ] GND → Coin acceptor ground

### ESP32-Bill-Forward (USB)
- [ ] GPIO 2 → Bill acceptor pulse input
- [ ] GPIO 12 → 1-peso hopper relay (through relay module)
- [ ] GPIO 13 → 5-peso hopper relay (through relay module)
- [ ] GPIO 14 → 1-peso coin sensor
- [ ] GPIO 15 → 5-peso coin sensor
- [ ] USB → Raspberry Pi USB port
- [ ] GND → Common ground with all devices

### ESP32-Vending-Controller (UART)
- [ ] GPIO 19 → Motor driver PWM input
- [ ] GPIO 5 → Coin detect input (optional)
- [ ] GPIO 18 → Counter feedback (optional)
- [ ] GPIO 3 (RX2) ← Raspberry Pi GPIO 14 (TX)
- [ ] GPIO 1 (TX2) → Raspberry Pi GPIO 15 (RX)
- [ ] GND → Common ground

---

## Configuration in Code

### config.json (Raspberry Pi)
```json
{
  "hardware": {
    "dht22_sensors": {"sensor_1": {"enabled": true, "gpio_pin": 36}, "sensor_2": {"enabled": true, "gpio_pin": 39}, "use_esp32_serial": true},
    "tec_relay": {
      "enabled": true,
      "gpio_pin": 26,
      "target_temp": 10.0
    },
    "ir_sensors": {"sensor_1": {"enabled": true, "gpio_pin": 34}, "sensor_2": {"enabled": true, "gpio_pin": 35}, "use_esp32_serial": true}
  }
}
```

### coin_hopper.py (Raspberry Pi)
```python
serial_port = '/dev/ttyUSB0'  # or '/dev/ttyACM0' for ESP32-Bill-Forward
baudrate = 115200
```

### vending_controller.ino (ESP32)
```cpp
const int SERIAL2_RX_PIN = 3;   // Receives from Raspberry Pi
const int SERIAL2_TX_PIN = 1;   // Sends to Raspberry Pi
const int PWM_PIN = 19;         // Motor control PWM
```

---

## Troubleshooting Pin Issues

### ESP32 GPIO Pin Limitations
- **GPIO 6, 7, 8, 9, 10, 11**: Reserved for SPI flash (do not use)
- **GPIO 37, 38, 39**: Input only (no output)
- **ADC pins** (34, 35, 36, 39): Input only
- **Strapping pins** (5, 12, 15): Boot mode dependent - use with caution

### Raspberry Pi GPIO Notes
- All GPIO pins are 3.3V output
- Use level shifters for 5V devices
- GPIO 2/3 are I2C (avoid unless using I2C)
- GPIO 14/15 are UART (used for UART communication)

### Common Issues
1. **Button stuck in LOW state**: Check if GPIO pin is sinking current
2. **Motor won't start**: Verify relay GPIO pin is HIGH
3. **Sensor not reading**: Check pull-up resistors and noise
4. **Serial communication fails**: Verify baud rate matches (115200)

---

## References

- [Raspberry Pi 4 GPIO Pinout](https://pinout.xyz/)
- [ESP32 Pinout Diagram](https://www.espressif.com/sites/default/files/documentation/esp32_datasheet_en.pdf)
- Project Files:
  - `tec_controller.py` - Temperature control
  - `coin_hopper.py` - Change dispensing
  - `item_dispense_monitor.py` - Item detection
  - `esp32_bill_forward/esp32_bill_forward.ino` - Bill & hopper control
  - `vending_controller/vending_controller.ino` - Motor control

