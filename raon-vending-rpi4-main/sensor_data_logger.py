"""
Sensor Data Logger - Records temperature, humidity, and IR sensor readings with timestamps
Provides data visualization capabilities (line graphs)

Logs sensor readings to CSV format for easy parsing and graphing:
- Timestamp
- DHT22 Sensor 1: Temperature, Humidity
- DHT22 Sensor 2: Temperature, Humidity
- IR Sensor 1: Item Detection Status
- IR Sensor 2: Item Detection Status
- TEC Relay Status
- Target Temperature
"""

import os
import csv
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock


class SensorDataLogger:
    """Log sensor readings with timestamps for data visualization."""
    
    def __init__(self, logs_dir="logs"):
        """Initialize sensor data logger.
        
        Args:
            logs_dir (str): Directory to store sensor log files
        """
        self.logs_dir = logs_dir
        self._lock = Lock()
        
        # Create logs directory if needed
        try:
            os.makedirs(logs_dir, exist_ok=True)
        except Exception as e:
            print(f"[SensorLogger] ERROR creating logs directory: {e}")
    
    def _get_sensor_log_filename(self, date=None):
        """Get sensor log filename for the given date.
        
        Args:
            date: datetime object or None for today
            
        Returns:
            str: Full path to sensor log file
        """
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime("%Y-%m-%d")
        return os.path.join(self.logs_dir, f"sensor_data_{date_str}.csv")
    
    def _ensure_csv_header(self, log_file):
        """Ensure CSV file has proper header row."""
        try:
            if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
                with open(log_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        'Timestamp',
                        'DateTime',
                        'Sensor1_Temp_C',
                        'Sensor1_Humidity_Pct',
                        'Sensor2_Temp_C',
                        'Sensor2_Humidity_Pct',
                        'IR_Sensor1_Detection',
                        'IR_Sensor2_Detection',
                        'Relay_Status',
                        'Target_Temp_C'
                    ])
        except Exception as e:
            print(f"[SensorLogger] ERROR creating CSV header: {e}")
    
    def log_sensor_reading(self, sensor1_temp=None, sensor1_humidity=None,
                          sensor2_temp=None, sensor2_humidity=None,
                          ir_sensor1_detection=None, ir_sensor2_detection=None,
                          relay_status=None, target_temp=None):
        """Log a sensor reading with timestamp.
        
        Args:
            sensor1_temp (float): DHT22 Sensor 1 temperature in °C
            sensor1_humidity (float): DHT22 Sensor 1 humidity in %
            sensor2_temp (float): DHT22 Sensor 2 temperature in °C
            sensor2_humidity (float): DHT22 Sensor 2 humidity in %
            ir_sensor1_detection (bool): IR Sensor 1 detection status (ON/OFF)
            ir_sensor2_detection (bool): IR Sensor 2 detection status (ON/OFF)
            relay_status (bool): TEC relay status (ON/OFF)
            target_temp (float): Target temperature setpoint in °C
        """
        try:
            timestamp = datetime.now()
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            timestamp_epoch = timestamp.isoformat()
            
            # Format values, use empty string for None (CSV won't break)
            s1_temp = f"{sensor1_temp:.1f}" if sensor1_temp is not None else ""
            s1_humidity = f"{sensor1_humidity:.1f}" if sensor1_humidity is not None else ""
            s2_temp = f"{sensor2_temp:.1f}" if sensor2_temp is not None else ""
            s2_humidity = f"{sensor2_humidity:.1f}" if sensor2_humidity is not None else ""
            ir1_detect = "DETECTED" if ir_sensor1_detection is True else ("CLEAR" if ir_sensor1_detection is False else "")
            ir2_detect = "DETECTED" if ir_sensor2_detection is True else ("CLEAR" if ir_sensor2_detection is False else "")
            relay = "ON" if relay_status is True else ("OFF" if relay_status is False else "")
            target = f"{target_temp:.1f}" if target_temp is not None else ""
            
            with self._lock:
                log_file = self._get_sensor_log_filename(timestamp)
                
                # Ensure header exists
                self._ensure_csv_header(log_file)
                
                # Append data row
                try:
                    with open(log_file, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            timestamp_str,
                            timestamp_epoch,
                            s1_temp,
                            s1_humidity,
                            s2_temp,
                            s2_humidity,
                            ir1_detect,
                            ir2_detect,
                            relay,
                            target
                        ])
                except Exception as e:
                    print(f"[SensorLogger] ERROR writing sensor data: {e}")
        except Exception as e:
            print(f"[SensorLogger] ERROR in log_sensor_reading: {e}")
    
    def log_ir_sensor_reading(self, ir_sensor1_detection=None, ir_sensor2_detection=None):
        """Log IR sensor detection readings with timestamp.
        
        Args:
            ir_sensor1_detection (bool): IR Sensor 1 detection status
            ir_sensor2_detection (bool): IR Sensor 2 detection status
        """
        try:
            timestamp = datetime.now()
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            timestamp_epoch = timestamp.isoformat()
            
            ir1_detect = "DETECTED" if ir_sensor1_detection is True else ("CLEAR" if ir_sensor1_detection is False else "")
            ir2_detect = "DETECTED" if ir_sensor2_detection is True else ("CLEAR" if ir_sensor2_detection is False else "")
            
            with self._lock:
                log_file = self._get_sensor_log_filename(timestamp)
                
                # Ensure header exists
                self._ensure_csv_header(log_file)
                
                # Append data row with only IR sensor data
                try:
                    with open(log_file, 'a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            timestamp_str,
                            timestamp_epoch,
                            "",  # Sensor1_Temp_C
                            "",  # Sensor1_Humidity_Pct
                            "",  # Sensor2_Temp_C
                            "",  # Sensor2_Humidity_Pct
                            ir1_detect,
                            ir2_detect,
                            "",  # Relay_Status
                            ""   # Target_Temp_C
                        ])
                except Exception as e:
                    print(f"[SensorLogger] ERROR writing IR data: {e}")
        except Exception as e:
            print(f"[SensorLogger] ERROR in log_ir_sensor_reading: {e}")
    
    def get_sensor_data(self, date=None, start_datetime=None, end_datetime=None):
        """Read sensor data from log file.
        
        Args:
            date: datetime object for specific date (default: today)
            start_datetime: datetime to start reading from
            end_datetime: datetime to stop reading at
            
        Returns:
            list: List of dicts with sensor readings
        """
        try:
            if date is None and start_datetime is None:
                date = datetime.now()
            
            if date is not None:
                log_file = self._get_sensor_log_filename(date)
                if not os.path.exists(log_file):
                    return []
                
                readings = []
                with self._lock:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            readings.append(row)
                return readings
            
            # If date range specified, read from multiple files
            if start_datetime and end_datetime:
                readings = []
                current_date = start_datetime.date()
                end_date = end_datetime.date()
                
                while current_date <= end_date:
                    log_file = self._get_sensor_log_filename(
                        datetime.combine(current_date, datetime.min.time())
                    )
                    
                    if os.path.exists(log_file):
                        with self._lock:
                            with open(log_file, 'r', encoding='utf-8') as f:
                                reader = csv.DictReader(f)
                                for row in reader:
                                    try:
                                        row_datetime = datetime.fromisoformat(row.get('DateTime', ''))
                                        if start_datetime <= row_datetime <= end_datetime:
                                            readings.append(row)
                                    except:
                                        pass
                    
                    current_date += timedelta(days=1)
                
                return readings
        
        except Exception as e:
            print(f"[SensorLogger] ERROR reading sensor data: {e}")
            return []
    
    def get_temperature_stats(self, date=None):
        """Get temperature statistics for a date.
        
        Args:
            date: datetime object (default: today)
            
        Returns:
            dict: Min, max, avg temperatures for each sensor
        """
        try:
            readings = self.get_sensor_data(date=date)
            if not readings:
                return {}
            
            stats = {
                'sensor1': {'min': None, 'max': None, 'avg': None, 'samples': 0},
                'sensor2': {'min': None, 'max': None, 'avg': None, 'samples': 0},
                'date': date.strftime("%Y-%m-%d") if date else datetime.now().strftime("%Y-%m-%d")
            }
            
            temps1 = []
            temps2 = []
            
            for row in readings:
                try:
                    if row.get('Sensor1_Temp_C'):
                        temp = float(row['Sensor1_Temp_C'])
                        temps1.append(temp)
                    if row.get('Sensor2_Temp_C'):
                        temp = float(row['Sensor2_Temp_C'])
                        temps2.append(temp)
                except:
                    pass
            
            # Calculate sensor 1 stats
            if temps1:
                stats['sensor1']['min'] = min(temps1)
                stats['sensor1']['max'] = max(temps1)
                stats['sensor1']['avg'] = sum(temps1) / len(temps1)
                stats['sensor1']['samples'] = len(temps1)
            
            # Calculate sensor 2 stats
            if temps2:
                stats['sensor2']['min'] = min(temps2)
                stats['sensor2']['max'] = max(temps2)
                stats['sensor2']['avg'] = sum(temps2) / len(temps2)
                stats['sensor2']['samples'] = len(temps2)
            
            return stats
        
        except Exception as e:
            print(f"[SensorLogger] ERROR calculating stats: {e}")
            return {}


# Global sensor logger instance
_sensor_logger_instance = None

def get_sensor_logger(logs_dir="logs"):
    """Get or create the global sensor logger instance."""
    global _sensor_logger_instance
    if _sensor_logger_instance is None:
        _sensor_logger_instance = SensorDataLogger(logs_dir=logs_dir)
    return _sensor_logger_instance
