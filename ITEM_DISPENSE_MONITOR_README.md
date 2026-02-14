# Item Dispense Monitor - IR Sensor Detection System

## Overview

The Item Dispense Monitor uses IR (Infrared) sensors to detect whether items have been successfully dispensed from vending slots. It provides automatic timeout detection and callback notifications when dispensing fails or takes too long.

## Features

- **Real-time Item Detection**: IR sensors detect item presence/absence in real-time
- **Automatic Timeout Alerts**: Shows popup alert if item doesn't dispense within timeout
- **Multi-Slot Support**: Monitor up to multiple vending slots simultaneously
- **Configurable Timeout**: Set different timeout values per slot or use default
- **Thread-Safe Operation**: Safe concurrent access from multiple threads
- **Status Callbacks**: Get real-time updates on dispense status
- **Graceful Cleanup**: Proper GPIO and thread cleanup

## GPIO Configuration

| Component | GPIO | Purpose |
|-----------|------|---------|
| IR Sensor 1 | GPIO6 | Detects items in Slot 1 |
| IR Sensor 2 | GPIO5 | Detects items in Slot 2 |

## How It Works

### Hardware Setup

Each vending slot has an IR sensor that reads item presence:
- **HIGH (Item Present)**: Item is in the slot
- **LOW (Item Absent)**: Item has been removed/dispensed

### Dispense Flow

1. **User purchases item** → Payment accepted
2. **Cart screen triggers vending** → `vend_slots_for(item_name, quantity)`
3. **Main app starts dispense monitor** → `dispense_monitor.start_dispense(slot_id, timeout, item_name)`
4. **Motor activates** → Pushes item out
5. **IR sensor monitors slot**:
   - ✅ **Item disappears** → Success! Dispense complete
   - ⏱️ **Timeout exceeded** → Alert dialog shows on screen
6. **Cleanup** → Remove from active monitoring

### Timeout Mechanism

With `default_timeout=10.0` seconds:
- Monitoring starts when dispense begins
- Every 500ms: Check if item is still present
- If item absent: Mark as SUCCESS
- If still present after 10s: Mark as TIMEOUT, show alert

## Configuration

Add to `config.json`:

```json
{
  "hardware": {
    "ir_sensors": {
      "sensor_1": {
        "enabled": true,
        "gpio_pin": 23
      },
      "sensor_2": {
        "enabled": true,
        "gpio_pin": 24
      },
      "dispense_timeout": 10.0
    }
  }
}
```

### Configuration Parameters

- **sensor_1.gpio_pin**: GPIO pin for IR sensor 1 (default: 6)
- **sensor_2.gpio_pin**: GPIO pin for IR sensor 2 (default: 5)
- **dispense_timeout**: Default timeout in seconds (default: 10.0)

## Usage

### Automatic Integration (Main Application)

The item dispense monitor is automatically initialized and integrated:

```python
# In main.py - already integrated!
dispense_monitor = ItemDispenseMonitor(ir_sensor_pins=[23, 24])
dispense_monitor.set_on_dispense_timeout(self._on_dispense_timeout)
dispense_monitor.set_on_item_dispensed(self._on_item_dispensed)
dispense_monitor.start_monitoring()

# When user purchases item:
dispense_monitor.start_dispense(slot_id=1, timeout=10.0, item_name="Soda Bottle")
```

### Manual Usage

```python
from item_dispense_monitor import ItemDispenseMonitor

# Create monitor
monitor = ItemDispenseMonitor(ir_sensor_pins=[23, 24], default_timeout=10.0)

# Register callbacks
def on_timeout(slot_id, elapsed_time):
    print(f"ERROR: Slot {slot_id} timeout after {elapsed_time}s!")

def on_dispensed(slot_id, success):
    if success:
        print(f"✓ Slot {slot_id} dispensed successfully")
    else:
        print(f"✗ Slot {slot_id} dispense FAILED")

monitor.set_on_dispense_timeout(on_timeout)
monitor.set_on_item_dispensed(on_dispensed)

# Start monitoring
monitor.start_monitoring()

# Start dispense operation
monitor.start_dispense(slot_id=1, timeout=10.0, item_name="Snack Bag")

# Wait for result...
# Cleanup
monitor.cleanup()
```

## API Reference

### ItemDispenseMonitor Class

#### Methods

**`start_monitoring()`**
- Start the background monitoring loop
- Safe to call multiple times (only starts once)

**`stop_monitoring()`**
- Stop the background monitoring loop
- Cancels all active dispenses

**`start_dispense(slot_id, timeout=None, item_name="Item")`**
- Signal start of item dispensing
- `slot_id`: Vending slot identifier (1-based)
- `timeout`: Dispense timeout in seconds (uses default if None)
- `item_name`: Name of the item being dispensed

**`cancel_dispense(slot_id)`**
- Cancel monitoring for a specific slot
- Useful if manual intervention stops the dispense

**`is_dispensing(slot_id)`**
- Check if a slot is currently being monitored
- Returns: bool

**`get_active_dispenses()`**
- Get all currently active dispense operations
- Returns: dict with slot_id as keys

**`set_on_item_dispensed(callback)`**
- Register callback when dispense completes
- Signature: `callback(slot_id, success: bool)`

**`set_on_dispense_timeout(callback)`**
- Register callback when dispense times out
- Signature: `callback(slot_id, elapsed_time: float)`

**`set_on_dispense_status(callback)`**
- Register callback for status messages
- Signature: `callback(slot_id, status_message: str)`

**`cleanup()`**
- Stop monitoring and cleanup GPIO
- Should be called before exit

### IRSensor Class

#### Methods

**`read()`**
- Read current item presence state
- Returns: bool (True if item present, False if absent)

**`is_item_present()`**
- Thread-safe check of item presence
- Returns: bool

## Alert Dialog System

When a timeout occurs, the system shows an alert dialog:

```
┌─────────────────────────────────┐
│  ⚠️ DISPENSE ERROR               │
├─────────────────────────────────┤
│  Item from Slot 1                │
│  failed to dispense!             │
│                                  │
│  Timeout after 10.5s            │
│                                  │
│          [OK]                    │
└─────────────────────────────────┘
```

The alert is shown on the main screen using `messagebox.showerror()`.

## Monitoring Loop Behavior

The monitoring loop runs continuously and:

1. **Every 500ms**:
   - Read all active IR sensors
   - Check for item absence (dispense success)
   - Check for timeout condition

2. **On Item Absence Detected**:
   - Remove from active monitoring
   - Trigger `on_item_dispensed(slot_id, True)`
   - Trigger `on_dispense_status(slot_id, "✓ Item dispensed successfully!")`

3. **On Timeout**:
   - Remove from active monitoring
   - Trigger `on_dispense_timeout(slot_id, elapsed_time)`
   - Trigger `on_item_dispensed(slot_id, False)`
   - Trigger `on_dispense_status(slot_id, "✗ TIMEOUT: Item not dispensed after Xs!")`

## Testing

Run the test script:

```bash
python3 test_item_dispense_monitor.py
```

Expected output:
```
============================================================
Item Dispense Monitor Test
============================================================

[TEST] Starting monitoring...
[TEST] Simulating dispensing operations...

[Slot 1] Dispensing Soda Bottle... (timeout: 5.0s)
[Slot 2] Dispensing Snack Bag... (timeout: 5.0s)

[TEST] Waiting for dispense operations to complete...

>>> DISPENSE SUCCESS: Slot 1
>>> DISPENSE SUCCESS: Slot 2

[TEST] ✓ Test completed
```

## Troubleshooting

### IR Sensor Not Detecting Items

1. **Check GPIO pin configuration**:
   ```bash
   python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(6, GPIO.IN); print('GPIO6:', GPIO.input(6))"
   ```

2. **Verify sensor wiring**:
   - 3.3V → VCC
   - GND → GND
   - DATA → GPIO6/5

3. **Check sensor lens**:
   - Clean IR lens
   - Ensure unobstructed view of slot

4. **Test with debug output**:
   ```python
   monitor = ItemDispenseMonitor(ir_sensor_pins=[23, 24])
   for _ in range(10):
       status = monitor.get_active_dispenses()
       for pin, sensor in monitor.sensors.items():
           print(f"GPIO{pin}: {sensor.read()}")
       time.sleep(0.5)
   ```

### Timeout Alerts Not Showing

1. Check that `dispense_monitor` is initialized in main.py
2. Verify callbacks are registered:
   ```python
   print(dispense_monitor._on_dispense_timeout)  # Should not be None
   ```
3. Check for exceptions in console output

### False Timeouts (Item Present but Marked as Timeout)

1. **Increase timeout value** in config.json:
   ```json
   "dispense_timeout": 15.0
   ```

2. **Check debounce time**:
   - Modify `IRSensor.debounce_time = 0.3` in code if sensor is noisy

3. **Verify sensor sensitivity**:
   - IR sensor may need potentiometer adjustment
   - Check manufacturer documentation

## Performance Considerations

- **Check frequency**: 500ms (every 0.5 seconds)
- **Overhead**: Minimal - only reads GPIO pins
- **Thread-safe**: Uses locks for concurrent access
- **Memory**: Tracks one dict per active dispense

## Hardware Requirements

### IR Sensor
- Operating voltage: 3.3V DC
- Output type: Digital (HIGH/LOW)
- Detection range: 2-10cm (typical)
- Response time: <100ms

### Wiring Example

```
IR Sensor Module
    ┌────────┐
    │VCC ●───┼──→ 3.3V
    │GND ●───┼──→ GND
    │OUT ●───┼──→ GPIO6 (with pull-up resistor)
    └────────┘
```

## Integration with Cart Screen

The system automatically integrates with the vending process:

```python
# In cart_screen.py - when user confirms purchase:
def _vend_items():
    for entry in vend_list:
        # This now automatically calls:
        # dispense_monitor.start_dispense(slot_id, timeout, item_name)
        self.controller.vend_slots_for(entry['item']['name'], entry['quantity'])

# If timeout occurs:
# 1. Popup alert appears: "⚠️ DISPENSE ERROR - Item from Slot X failed to dispense!"
# 2. User sees error message on screen
# 3. Log entry recorded
```

## Future Enhancements

- [ ] Multiple IR sensors per slot (redundancy)
- [ ] Configurable alert sounds/notifications
- [ ] Retry mechanism for failed dispenses
- [ ] Statistics tracking (success rate, average dispense time)
- [ ] Remote monitoring dashboard
- [ ] Integration with refund system

## References

- [IR Sensor Detection Modules](https://en.wikipedia.org/wiki/Infrared)
- [Raspberry Pi GPIO Documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html)
- [Tkinter Message Box](https://docs.python.org/3/library/tkinter.messagebox.html)
