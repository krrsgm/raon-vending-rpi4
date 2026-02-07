# MUX4 Raspberry Pi Integration Guide

## Overview

The MUX4 multiplexer (slots 49-64) now uses a split control architecture:
- **ESP32**: Controls multiplexer selector pins (S0-S3) 
- **Raspberry Pi**: Controls the signal output pin (SIG)

This setup allows direct GPIO control on the Pi for MUX4 outputs while keeping the selection logic on the ESP32.

## Hardware Connection

### ESP32 to MUX4 (unchanged)
```
ESP32 GPIO17 → MUX4 S0
ESP32 GPIO5  → MUX4 S1
ESP32 GPIO18 → MUX4 S2
ESP32 GPIO19 → MUX4 S3
```

### MUX4 SIG to Raspberry Pi
```
MUX4 SIG     → Raspberry Pi GPIO23 (configurable)
MUX4 GND     → Raspberry Pi GND
```

## Configuration

Add this section to your `config.json`:

```json
{
  "hardware": {
    "mux4": {
      "enabled": true,
      "sig_pin": 23
    }
  }
}
```

### Configuration Options

- **enabled** (boolean): Enable/disable MUX4 controller (default: true)
- **sig_pin** (integer): GPIO pin number for MUX4 SIG (default: 23)

## How It Works

When vending items assigned to slots 49-64:

1. **Slot Check**: The main app checks if slot is in range 49-64
2. **If Yes (MUX4)**:
   - ESP32 still sets selector pins (S0-S3) via RXTX commands
   - Raspberry Pi directly pulses the SIG pin using GPIO
3. **If No (Slots 1-48)**:
   - Traditional ESP32 control via TCP (all pins controlled by ESP32)

## Code Flow

```
main.py vend() method
  ↓
Check slot number (1-48 or 49-64?)
  ├→ Slots 1-48: pulse_slot(esp32_host, slot, ms)
  │   └→ ESP32 controls everything
  │
  └→ Slots 49-64: mux4_controller.pulse(ms)
      └→ RPi GPIO controls SIG pin
         (ESP32 still controls selector via separate command)
```

## Python API

### Initialize Controller
```python
from mux4_controller import MUX4Controller

mux4 = MUX4Controller(sig_pin=23)
```

### Control Methods
```python
# Pulse SIG for 800ms (blocking)
mux4.pulse(800)

# Set output continuously
mux4.set_output(True)   # HIGH
mux4.set_output(False)  # LOW

# Pulse asynchronously (non-blocking)
mux4.pulse_async(800)

# Read SIG input (for feedback)
state = mux4.read_input()  # Returns True/False

# Cleanup
mux4.cleanup()
```

## Testing

To test MUX4 control directly:

```python
from mux4_controller import MUX4Controller
import time

mux4 = MUX4Controller(sig_pin=23)

# Pulse test
print("Testing pulse...")
mux4.pulse(500)

# Output test
print("Setting HIGH...")
mux4.set_output(True)
time.sleep(1)

print("Setting LOW...")
mux4.set_output(False)

mux4.cleanup()
```

## Troubleshooting

### Permission Denied Error
```bash
# Add user to GPIO group
sudo usermod -a -G gpio $USER
# Log out and back in
```

### GPIO Already in Use
The controller handles this automatically by detecting if GPIO mode is already set.

### MUX4 Not Responding
1. Check physical connections (SIG → GPIO23)
2. Verify MUX4 power and GND connections
3. Check `config.json` has `"mux4": {"enabled": true}`
4. Check GPIO23 is not used by other devices

### Mock Mode (Non-Pi)
When running on non-Raspberry Pi systems, the controller automatically falls back to mock GPIO mode (prints debug messages instead of controlling actual pins).

## Architecture Diagram

```
┌─────────────────┐
│  Raspberry Pi   │
│    main.py      │
└────────┬────────┘
         │
         ├─→ Slots 1-48: pulse_slot() → ESP32 (TCP)
         │
         └─→ Slots 49-64: mux4_controller.pulse() → GPIO23
         
┌─────────────────┐
│     ESP32       │
│  vending_       │
│  controller.ino │
└────────┬────────┘
         │
         ├─→ MUX1-3: Full control (S0-S3, SIG)
         │
         └─→ MUX4: Control S0-S3 only
              (SIG controlled by RPi GPIO23)

┌─────────────────┐
│  MUX4 IC        │
│  CD74HC4067     │
└────────┬────────┘
         │
         ├─→ S0-S3 ← ESP32 GPIO17,5,18,19
         └─→ SIG   ← Raspberry Pi GPIO23
```

## Performance Notes

- **Pulse timing**: 800ms is typical motor activation
- **Non-blocking**: Use `pulse_async()` for longer operations
- **Thread-safe**: Controller uses locks for thread safety
- **GPIO cleanup**: Automatic on app exit

## Related Files

- `mux4_controller.py` - MUX4 controller implementation
- `vending_controller.ino` - ESP32 firmware (no MUX4_SIG handling)
- `main.py` - Integration point with vend() method
- `config.json` - Hardware configuration
