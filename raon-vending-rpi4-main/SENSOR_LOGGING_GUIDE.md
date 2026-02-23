# Sensor Data Logging & Graphing

## Overview

This feature automatically logs temperature and humidity readings from DHT22 sensors with timestamps, allowing you to:
- Track temperature changes over time
- Visualize sensor data as line graphs
- Analyze temperature statistics
- Monitor TEC (Peltier) cooling system performance

## Files

### Core Logging System
- **`sensor_data_logger.py`** - Records sensor readings to CSV files with timestamps
- **`sensor_graph_generator.py`** - Generates matplotlib line graphs from logged data
- **`demo_sensor_logging.py`** - Demo script showing sensor logging and graphing

### Integration
- **`tec_controller.py`** - Updated to log sensor readings every ~60 seconds automatically

## Features

### Sensor Data Logger
Records the following data every ~60 seconds to `logs/sensor_data_YYYY-MM-DD.csv`:
- Timestamp (ISO format)
- DHT22 Sensor 1: Temperature (°C), Humidity (%)
- DHT22 Sensor 2: Temperature (°C), Humidity (%)
- TEC Relay Status (ON/OFF)
- Target Temperature (°C)

### Graph Generation
Creates professional line graphs showing:
1. **Temperature Graph** - Sensor 1 & 2 temps vs time with target temp line
2. **Humidity Graph** - Sensor 1 & 2 humidity levels vs time
3. **Combined Graph** - Temperature and humidity on dual Y-axes

Graphs are saved to `sensor_graphs/` directory as PNG files (150 DPI).

## Usage

### Automatic Logging (with TEC Controller)
When the TEC controller is running, sensor data is automatically logged:
```python
from main import MainApp
# Sensor data is logged automatically ~every 60 seconds
```

### Manual Logging
```python
from sensor_data_logger import get_sensor_logger

logger = get_sensor_logger()
logger.log_sensor_reading(
    sensor1_temp=25.5,
    sensor1_humidity=45.0,
    sensor2_temp=26.0,
    sensor2_humidity=48.0,
    relay_status=True,
    target_temp=10.0
)
```

### Generate Graphs
```python
from sensor_graph_generator import SensorGraphGenerator
from datetime import datetime

generator = SensorGraphGenerator()

# Generate all graphs for today
graphs = generator.generate_all_graphs()
# Returns: {'temperature': path, 'humidity': path, 'combined': path}

# Generate graph for specific date
generator.generate_temperature_graph(datetime(2026, 2, 20))
generator.generate_humidity_graph(datetime(2026, 2, 20))
generator.generate_combined_graph(datetime(2026, 2, 20))
```

### Command Line Usage
```bash
# Generate graphs for today
python sensor_graph_generator.py

# Generate graphs for a specific date
python sensor_graph_generator.py 2026-02-20

# Run demo
python demo_sensor_logging.py
```

### Get Statistics
```python
from sensor_data_logger import get_sensor_logger
from datetime import datetime

logger = get_sensor_logger()
stats = logger.get_temperature_stats(datetime.now())

# Returns:
# {
#   'sensor1': {'min': 9.5, 'max': 25.0, 'avg': 15.2, 'samples': 50},
#   'sensor2': {'min': 10.0, 'max': 26.0, 'avg': 16.0, 'samples': 50},
#   'date': '2026-02-20'
# }
```

## Data Format

### CSV File: `logs/sensor_data_YYYY-MM-DD.csv`
```
Timestamp,DateTime,Sensor1_Temp_C,Sensor1_Humidity_Pct,Sensor2_Temp_C,Sensor2_Humidity_Pct,Relay_Status,Target_Temp_C
2026-02-20 10:00:00,2026-02-20T10:00:00,25.5,45.0,26.0,48.0,ON,10.0
2026-02-20 10:01:00,2026-02-20T10:01:00,25.4,44.9,25.9,47.9,ON,10.0
2026-02-20 10:02:00,2026-02-20T10:02:00,25.0,44.5,25.5,47.5,ON,10.0
```

## Installation

Install matplotlib for graph generation:
```bash
pip install matplotlib==3.7.1
```

## Logging Frequency

By default, sensor readings are logged every ~60 seconds (30 sensor read cycles × 2 seconds per cycle).

To adjust frequency, modify in `tec_controller.py`:
```python
# Log every 30 cycles (~60 seconds)
if self.sensor_log_counter >= 30 and self.sensor_logger:
    # Change 30 to desired number of cycles
    # (1 cycle = 2 seconds for DHT22 minimum interval)
```

## Integration with Logs Screen

The sensor data can be visualized in the kiosk UI:
```python
from sensor_graph_generator import SensorGraphGenerator
from datetime import datetime

# In logs_screen.py or similar UI:
generator = SensorGraphGenerator()
graph_path = generator.generate_temperature_graph(datetime.now())
# Display graph_path in UI
```

## Troubleshooting

### No graphs generated
1. Check if sensor data exists: `ls -l logs/sensor_data_*.csv`
2. Ensure TEC controller is running
3. Check matplotlib installation: `python -c "import matplotlib; print('OK')"`

### "No sensor data found"
- Ensure TEC controller has been running for at least 60 seconds
- Check that sensors are properly connected and reading

### Graph filenames incorrect
- Graphs are saved with local system date/time
- Ensure system time/timezone is correct

## Performance Notes

- CSV files are thread-safe (use locking)
- Graph generation is CPU-intensive, may take 2-5 seconds
- Store graphs in `sensor_graphs/` to avoid clutter
- Daily CSV files stay small (~5-50 KB for a full day of logging)

## Future Enhancements

Potential additions:
- Real-time graph updates in UI
- Data export to JSON
- Trend analysis (temperature drift detection)
- Alerts for temperature anomalies
- Weekly/monthly summary reports
- Database backend (instead of CSV)
