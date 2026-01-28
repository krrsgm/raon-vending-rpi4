# IR Sensor Bin Area Detection - Setup Guide

## Overview

This guide explains how to set up and configure IR sensors in the bin catch area to detect when items have successfully fallen into the collection bin.

## Physical Setup

### Sensor Placement

The two IR sensors are positioned to maximize coverage of the bin catch area:

```
     Vending Slots (Top)
     ┌─────────────────┐
     │ Item Dispensed  │
     │       ↓↓        │
     └────────┬────────┘
              │
         FALL ZONE
              │
     ┌────────▼────────┐
     │  IR Sensor 1    │
     │  (GPIO23)       │◄─── Positioned to catch items
     │                 │     falling to the left/center
     └─────────────────┘
     
     ┌────────────────┐
     │  IR Sensor 2   │
     │  (GPIO24)      │◄─── Positioned to catch items
     │                │     falling to the right/center
     └────────────────┘
     
     ┌─────────────────┐
     │   BIN/TRAY      │
     │  (Collection)   │
     └─────────────────┘
```

### Optimal Positioning

**Distance**: Place sensors 2-10cm above the bin opening
**Angle**: Position to detect items passing through the fall zone
**Spacing**: Spread sensors horizontally to cover maximum fall area
**Height**: Position so items trigger sensors as they fall

### Wiring Diagram

```
IR Sensor Module
    ┌────────────┐
    │VCC ●───┬──→ 3.3V
    │GND ●───┬──→ GND
    │OUT ●───┬──→ GPIO23 (Sensor 1) / GPIO24 (Sensor 2)
    └────────┘    with 10kΩ pull-up resistor

Repeating for both sensors on different GPIO pins.
```

## Detection Modes

The system supports three detection modes to handle different sensor coverage scenarios:

### 1. **'any' Mode (Recommended)** ⭐

```
detection_mode: "any"
```

**Logic**: Item detected if EITHER sensor detects absence

**Behavior**:
- Sensor 1: Item present → ❌ Not yet
- Sensor 2: Item absent → ✅ **SUCCESS!**

**Use Case**: Items can fall through different paths, maximize detection coverage
**Reliability**: Highest - works even if one sensor misses
**False Positives**: Lowest - requires actual item to trigger

**Example Timeline**:
```
T=0s    Motor activates, item falls
T=0.5s  Sensor 1: PRESENT, Sensor 2: PRESENT (item in fall zone)
T=1.0s  Sensor 1: PRESENT, Sensor 2: ABSENT ← ✓ DETECTED! (Either sensor)
T=1.5s  Result: SUCCESS in 1.0 second
```

### 2. **'all' Mode (Redundant)**

```
detection_mode: "all"
```

**Logic**: Item detected only if ALL sensors detect absence

**Behavior**:
- Sensor 1: Item absent → ✓
- Sensor 2: Item absent → ✓
- **Both absent** → ✅ **SUCCESS!**

**Use Case**: Extra verification, ensure item passed completely through both zones
**Reliability**: Very high for redundancy
**False Positives**: Very low - dual confirmation

**Example Timeline**:
```
T=0s    Motor activates
T=0.5s  Sensor 1: ABSENT, Sensor 2: PRESENT (item passing sensor 1)
T=1.0s  Sensor 1: ABSENT, Sensor 2: ABSENT ← ✓ DETECTED! (Both absent)
T=1.5s  Result: SUCCESS in 1.5 seconds
```

### 3. **'first' Mode (Fastest)**

```
detection_mode: "first"
```

**Logic**: Item detected as soon as FIRST sensor detects absence

**Behavior**:
- Sensor 1: Item absent → ✅ **SUCCESS immediately!**

**Use Case**: Fastest feedback, item just entered bin zone
**Reliability**: Medium - single sensor detection
**False Positives**: Possible if sensor briefly triggered by shadow/obstruction

**Example Timeline**:
```
T=0s    Motor activates
T=0.5s  Sensor 1: ABSENT ← ✓ DETECTED immediately! (First to trigger)
T=0.5s  Result: SUCCESS in 0.5 seconds
```

## Configuration

### Basic Configuration

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
      "dispense_timeout": 10.0,
      "detection_mode": "any"
    }
  }
}
```

### Configuration by Use Case

**For Maximum Reliability (Recommended for Bin Area)**:
```json
{
  "detection_mode": "any",
  "dispense_timeout": 10.0
}
```
- ✓ Either sensor can detect
- ✓ Covers entire fall bin area
- ✓ Forgiving of sensor placement

**For Maximum Verification (Redundancy Check)**:
```json
{
  "detection_mode": "all",
  "dispense_timeout": 15.0
}
```
- ✓ Both sensors must confirm
- ✓ Lower false positive rate
- ⚠ Requires both sensors aligned

**For Fastest Response (Quick Feedback)**:
```json
{
  "detection_mode": "first",
  "dispense_timeout": 5.0
}
```
- ✓ Fastest detection
- ⚠ Higher sensitivity to false triggers
- ⚠ Less forgiving positioning

## Detection Flow

### Successful Dispensing (with 'any' mode)

```
1. User purchases item (e.g., "Soda Bottle")
2. Payment accepted
3. Dispense monitor starts: start_dispense(slot_id=1, timeout=10.0)
4. Motor activates
5. Item falls through dispense slot
6. Enters fall zone
7. IR Sensor 1 detects absence (item passing) → ✓ DETECTED!
8. Monitor triggers success callback
9. Display: "✓ Soda Bottle detected in bin!"
10. Dispense complete
```

### Timeout Scenario

```
1. User purchases item (e.g., "Candy Bar")
2. Payment accepted
3. Dispense monitor starts: start_dispense(slot_id=2, timeout=10.0)
4. Motor activates
5. Item stuck or failed to dispense
6. Both sensors still show: PRESENT
7. 10 seconds elapsed
8. Monitor triggers timeout callback
9. Alert popup: "⚠️ Item from Slot 2 failed to dispense!"
10. Status: "GPIO23=PRESENT, GPIO24=PRESENT"
11. User intervention required
```

## Sensor Debugging

### Check Sensor Status

```bash
# Quick test
python3 -c "
from item_dispense_monitor import ItemDispenseMonitor
import time

monitor = ItemDispenseMonitor(ir_sensor_pins=[23, 24])
monitor.start_monitoring()

for i in range(10):
    for pin, sensor in monitor.sensors.items():
        reading = sensor.read()
        print(f'GPIO{pin}: {reading}')
    time.sleep(1)
"
```

### Sensor States

**Reading Values**:
- `True` = ITEM PRESENT (sensor sees reflection)
- `False` = ITEM ABSENT (no reflection, item fell)
- `None` = ERROR (GPIO read error)

**Typical Output**:
```
GPIO23: True   (item in slot)
GPIO24: True   (item in slot)

[... item falls ...]

GPIO23: False  (item passed)
GPIO24: True   (still in zone)

[... second sensor triggers ...]

GPIO23: False
GPIO24: False  (both detected)
```

### Testing Detection Modes

```python
from item_dispense_monitor import ItemDispenseMonitor

# Test 'any' mode
monitor_any = ItemDispenseMonitor(detection_mode='any')
# Result: Success if Sensor1 OR Sensor2 detects absence

# Test 'all' mode
monitor_all = ItemDispenseMonitor(detection_mode='all')
# Result: Success only if Sensor1 AND Sensor2 detect absence

# Test 'first' mode
monitor_first = ItemDispenseMonitor(detection_mode='first')
# Result: Success as soon as any sensor detects absence
```

## Performance Metrics

### Detection Time (from dispense start)

**'any' Mode**:
- Typical: 0.5-2.0 seconds
- Range: 0.5-5.0 seconds

**'all' Mode**:
- Typical: 1.0-3.0 seconds
- Range: 1.0-8.0 seconds

**'first' Mode**:
- Typical: 0.3-1.0 seconds
- Range: 0.3-3.0 seconds

### Factors Affecting Detection Time

1. **Sensor Position**: Higher placement = longer fall time
2. **Item Type**: Heavy items fall faster
3. **Motor Speed**: Faster motors push harder
4. **Sensor Sensitivity**: Well-calibrated sensors respond faster
5. **GPIO Response**: System processing time

## Troubleshooting

### Problem: "Item detected correctly but takes too long"

**Solutions**:
1. Lower timeout to match expected fall time
2. Check sensor alignment - may be detecting late
3. Verify motor power - slow motors take longer
4. Consider 'first' mode for faster feedback

```json
"dispense_timeout": 5.0,
"detection_mode": "first"
```

### Problem: "False timeouts - item present but marked as timeout"

**Solutions**:
1. Increase timeout value
2. Check sensor orientation
3. Verify IR sensor sensitivity
4. Clean sensor lenses (dust blocks IR)

```json
"dispense_timeout": 15.0
```

### Problem: "One sensor not detecting consistently"

**Solutions**:
1. Check GPIO wiring for that sensor
2. Test GPIO pin: `python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(23, GPIO.IN); print(GPIO.input(23))"`
3. Clean sensor lens
4. Verify pull-up resistor (10kΩ recommended)
5. Switch to 'all' mode to ensure backup sensor works

### Problem: "Both sensors showing PRESENT even after item falls"

**Solutions**:
1. Sensors may be too high - adjust position
2. Item may not be reaching sensors - check mechanics
3. Sensor sensitivity too low - adjust potentiometer
4. Check if item path changed - verify dispense mechanism

## Hardware Maintenance

### Regular Checks

- **Weekly**: Clean sensor lenses (soft cloth)
- **Monthly**: Check wiring connections
- **Quarterly**: Verify sensor alignment
- **Annually**: Replace if needed (wear/damage)

### Sensor Cleaning

```
1. Gently wipe lens with soft, dry cloth
2. If dirty, use isopropyl alcohol (90%+)
3. Allow to dry completely
4. Do NOT use abrasive materials
5. Do NOT apply pressure - lenses are fragile
```

## References

- [Infrared Sensor Operation](https://en.wikipedia.org/wiki/Infrared)
- [Raspberry Pi GPIO Guide](https://www.raspberrypi.com/documentation/)
- [IR Sensor Modules Datasheet](https://www.robotshop.com/products/ir-sensor)
- [Vending Machine Design Best Practices](https://en.wikipedia.org/wiki/Vending_machine)
