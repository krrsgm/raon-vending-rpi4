# System Status Panel - User Guide

## Overview

The **System Status Panel** is a real-time hardware and sensor status display widget that appears at the bottom of the vending machine UI. It provides live monitoring of all critical system components including:

- **🌡️ Environmental Sensors**: DHT22 temperature and humidity readings
- **❄️ Cooling System**: TEC Peltier controller status and target temperature
- **📡 Item Detection**: IR sensor status in the bin catch area
- **⚙️ System Health**: Overall operational status and uptime

## Location and Display

The status panel is positioned at the lower section of the Kiosk screen, above the group members footer information.

```
┌─────────────────────────────────────────────────────────────────┐
│                      RAON VENDING MACHINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Search  │  [Products Grid]                                     │
│  Recent  │                                                       │
│  Popular │                                                       │
│          │                                                       │
├─────────────────────────────────────────────────────────────────┤
│ 🔧 SYSTEM STATUS ●                                              │
│ 🌡️ ENVIRONMENT | ❄️ TEC COOLER | 📡 IR SENSORS | ⚙️ SYSTEM   │
│ S1: Temp: 22.5°C | Humid: 45%                                  │
│ S2: Temp: 23.0°C | Humid: 47%    Status: ON | Target: 10.0°C   │
│                                   Current: 15.2°C               │
├─────────────────────────────────────────────────────────────────┤
│ © RAON Group Members: Alice, Bob, Charlie                       │
└─────────────────────────────────────────────────────────────────┘
```

## Status Indicators

### 🌡️ Environment Section

Shows readings from both DHT22 environmental sensors:

- **S1 (Sensor 1 - GPIO27)**
  - Temperature: Current reading in °C
  - Humidity: Current relative humidity percentage

- **S2 (Sensor 2 - GPIO22)**
  - Temperature: Current reading in °C
  - Humidity: Current relative humidity percentage

Example:
```
S1: Temp: 22.5°C | Humid: 45%
S2: Temp: 23.0°C | Humid: 47%
```

### ❄️ TEC Cooler Section

Displays the Thermoelectric Cooler (Peltier module) status:

- **Status**
  - `ON` (Green): Actively cooling
  - `OFF` (Red): Not cooling
  - `DISABLED` (Gray): Not configured
  
- **Target**: Target temperature setting (e.g., 10.0°C)

- **Current**: Current control temperature (average or max of sensors based on config)

Example:
```
Status: ON | Target: 10.0°C
Current: 15.2°C
```

**Color Codes**:
- 🟢 Green: TEC is actively cooling (ON)
- 🔴 Red: TEC is idle (OFF)
- ⚪ Gray: TEC disabled

### 📡 IR Sensors Section

Shows the status of infrared sensors positioned in the bin catch area:

- **S1 & S2 Status**
  - `PRESENT` (🟠 Orange): Item detected in sensor range
  - `EMPTY` (🔴 Red): No item detected (item has fallen into bin)
  - `--` (⚪ Gray): Unknown/Error state

- **Mode**: Detection logic being used
  - `any`: Either sensor can trigger success (recommended for bin area)
  - `all`: Both sensors must confirm
  - `first`: Fastest detection on first sensor trigger

Example:
```
● S1: PRESENT  | ● S2: EMPTY
Mode: any
```

### ⚙️ System Section

Overall system health indicator:

- **Status Indicator** (● dot)
  - 🟢 Green: Operational - System running normally
  - 🟠 Orange: Warning - Minor issues detected
  - 🔴 Red: Error - Critical issue requiring attention

- **Health Text**
  - `Operational`: All systems normal
  - `Warning`: Non-critical issue
  - `Error`: Requires intervention

- **Uptime**: Time system has been running

Example:
```
● Operational
Uptime: 12:34
```

## Real-Time Updates

The status panel updates automatically every 1 second with the latest sensor readings and system state. All updates are:

- **Thread-safe**: Uses locking mechanisms to prevent data corruption
- **Non-blocking**: Updates don't freeze the UI
- **Efficient**: Only updates changed values

## Color Scheme

The panel uses a professional dark theme for easy readability:

| Component | Color | Hex Code |
|-----------|-------|----------|
| Background | Dark Blue-Gray | #2c3e50 |
| Sections | Medium Blue-Gray | #34495e |
| Section Headers | Blue | #3498db |
| Normal Text | Light Gray | #ecf0f1 |
| Active/On | Green | #27ae60 |
| Item Present/Ready | Orange | #f39c12 |
| Error/Off | Red | #e74c3c |
| Disabled/Unknown | Gray | #95a5a6 |

## Data Flow

The status panel receives updates from multiple sources:

```
┌─────────────────────┐
│  DHT22 Sensors      │
│  (GPIO27, GPIO22)   │
└────────┬────────────┘
         │ Temperature, Humidity
         │
         └──────────────┐
                        │
┌──────────────────┐    │     ┌──────────────────┐
│  TEC Controller  │────┼────→│ System Status    │
│  (GPIO26 relay)  │    │     │ Panel Widget     │─→ Display
└──────────────────┘    │     └──────────────────┘
                        │
┌──────────────────┐    │
│  IR Sensors      │    │
│  (GPIO23, GPIO24)├────┘
└──────────────────┘
```

## Integration with Application

The system status panel is automatically initialized when the KioskFrame is created:

```python
# Automatically created in kiosk_app.py
self.status_panel = SystemStatusPanel(self, controller=self.controller)
self.status_panel.pack(side='bottom', fill='x')
```

The main application (main.py) registers callbacks to send real-time updates:

- `_on_tec_status_update()`: Receives TEC controller status changes
- `_on_dht22_update()`: Receives DHT22 sensor readings
- `_on_ir_status_update()`: Receives IR sensor status changes

## Customization

### Adjust Update Frequency

Edit `system_status_panel.py` in the `start_update_loop()` method:

```python
time.sleep(1)  # Change to update more/less frequently
```

### Change Colors

Modify color values in `create_widgets()` method:

```python
'background': '#2c3e50',  # Main background
'active': '#27ae60',      # Active/on color
'error': '#e74c3c',       # Error color
```

### Resize Panel Height

Adjust in the `__init__` method:

```python
self.configure(bg='#2c3e50', height=100)  # Height in pixels
```

## Troubleshooting

### Panel Not Updating

1. Check that callbacks are registered in `main.py`
2. Verify hardware is enabled in `config.json`
3. Check terminal for error messages
4. Ensure sensors are connected and readable

### Incorrect Readings

1. Verify sensor GPIO pins match configuration
2. Check sensor connectivity
3. Ensure sensors are not blocked
4. Allow time for sensors to warm up

### Display Issues

1. Verify color codes are valid hex values
2. Check font sizes aren't too large for screen
3. Ensure resolution supports panel width
4. Test on different displays if needed

## Technical Details

### Thread Safety

The status panel uses threading locks to ensure data consistency:

```python
with self._lock:
    # Update data safely
    self.dht22_data = {...}
```

### Memory Efficiency

- Minimal memory footprint: Updates only display when values change
- Background thread daemon: Automatically stops when app closes
- No circular references: Clean garbage collection

### Performance

- Update loop: 1Hz (updates every 1 second)
- Callback latency: < 50ms
- UI responsiveness: No blocking operations
- CPU usage: < 1% overhead

## Example: Monitoring System Status

To monitor system health, watch for these indicator transitions:

1. **Normal Operation**
   ```
   ● Operational | Temp: 22.5°C | TEC: ON | IR: S1=EMPTY, S2=PRESENT
   ```

2. **Temperature Rising**
   ```
   ● Warning | Temp: 28.5°C | TEC: ON | (actively cooling)
   ```

3. **Sensor Error**
   ```
   ● Error | Temp: --°C | TEC: OFF | IR: S1=--, S2=-- (sensor issue)
   ```

4. **Over-temperature**
   ```
   ● Error | Temp: 35.0°C | TEC: ON | (cannot cool further)
   ```

## Advanced Configuration

See `IR_SENSOR_BIN_SETUP.md` and `TEC_CONTROLLER_README.md` for detailed hardware-specific configuration information.

## Support

For issues or questions:
1. Check sensor connections
2. Verify GPIO pin assignments in `config.json`
3. Review application logs in terminal
4. Test individual components with provided test scripts

## Version History

- **v1.0** (2026-01-25): Initial release
  - Real-time DHT22 sensor display
  - TEC controller status monitoring
  - IR sensor bin area detection display
  - System health indicators
