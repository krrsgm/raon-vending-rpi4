"""
Sensor Data Visualization - Generate line graphs for temperature and humidity data
Creates matplotlib graphs showing sensor readings over time
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from sensor_data_logger import get_sensor_logger
import os


class SensorGraphGenerator:
    """Generate line graphs for sensor data visualization."""
    
    def __init__(self):
        """Initialize graph generator."""
        self.sensor_logger = get_sensor_logger()
        self.output_dir = "sensor_graphs"
        
        # Create output directory if needed
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except Exception as e:
            print(f"[SensorGraph] ERROR creating output directory: {e}")
    
    def generate_temperature_graph(self, date=None, filename=None):
        """Generate temperature vs time line graph.
        
        Args:
            date: datetime object (default: today)
            filename: output filename (default: temp_YYYY-MM-DD.png)
            
        Returns:
            str: Path to saved graph image or None on error
        """
        try:
            if date is None:
                date = datetime.now()
            
            if filename is None:
                filename = f"temperature_{date.strftime('%Y-%m-%d')}.png"
            
            filepath = os.path.join(self.output_dir, filename)
            
            # Get sensor data
            readings = self.sensor_logger.get_sensor_data(date=date)
            if not readings:
                print(f"[SensorGraph] No sensor data found for {date.strftime('%Y-%m-%d')}")
                return None
            
            # Parse data
            times = []
            temps1 = []
            temps2 = []
            target_temps = []
            
            for row in readings:
                try:
                    # Parse timestamp
                    time_str = row.get('Timestamp', '')
                    if time_str:
                        time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                        times.append(time)
                        
                        # Parse temperatures
                        if row.get('Sensor1_Temp_C'):
                            temps1.append(float(row['Sensor1_Temp_C']))
                        else:
                            temps1.append(None)
                        
                        if row.get('Sensor2_Temp_C'):
                            temps2.append(float(row['Sensor2_Temp_C']))
                        else:
                            temps2.append(None)
                        
                        if row.get('Target_Temp_C'):
                            target_temps.append(float(row['Target_Temp_C']))
                        else:
                            target_temps.append(None)
                except Exception as e:
                    print(f"[SensorGraph] Error parsing row: {e}")
                    continue
            
            if not times:
                print(f"[SensorGraph] No valid time data found")
                return None
            
            # Create figure
            fig, ax = plt.subplots(figsize=(14, 6))
            
            # Plot data
            if any(t is not None for t in temps1):
                ax.plot(times, temps1, marker='o', label='Sensor 1', linewidth=2, markersize=4, color='#FF6B6B')
            
            if any(t is not None for t in temps2):
                ax.plot(times, temps2, marker='s', label='Sensor 2', linewidth=2, markersize=4, color='#4ECDC4')
            
            if any(t is not None for t in target_temps):
                ax.axhline(y=target_temps[0] if target_temps[0] else 10, 
                          color='#95E1D3', linestyle='--', linewidth=2, label='Target Temp', alpha=0.7)
            
            # Format axes
            ax.set_xlabel('Time', fontsize=12, fontweight='bold')
            ax.set_ylabel('Temperature (°C)', fontsize=12, fontweight='bold')
            ax.set_title(f'Temperature Readings - {date.strftime("%Y-%m-%d")}', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best', fontsize=10)
            
            # Format x-axis with time labels
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            fig.autofmt_xdate(rotation=45, ha='right')
            
            # Save figure
            fig.tight_layout()
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            print(f"[SensorGraph] Temperature graph saved: {filepath}")
            return filepath
        
        except Exception as e:
            print(f"[SensorGraph] ERROR generating temperature graph: {e}")
            return None
    
    def generate_humidity_graph(self, date=None, filename=None):
        """Generate humidity vs time line graph.
        
        Args:
            date: datetime object (default: today)
            filename: output filename (default: humidity_YYYY-MM-DD.png)
            
        Returns:
            str: Path to saved graph image or None on error
        """
        try:
            if date is None:
                date = datetime.now()
            
            if filename is None:
                filename = f"humidity_{date.strftime('%Y-%m-%d')}.png"
            
            filepath = os.path.join(self.output_dir, filename)
            
            # Get sensor data
            readings = self.sensor_logger.get_sensor_data(date=date)
            if not readings:
                print(f"[SensorGraph] No sensor data found for {date.strftime('%Y-%m-%d')}")
                return None
            
            # Parse data
            times = []
            humidity1 = []
            humidity2 = []
            
            for row in readings:
                try:
                    # Parse timestamp
                    time_str = row.get('Timestamp', '')
                    if time_str:
                        time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                        times.append(time)
                        
                        # Parse humidity
                        if row.get('Sensor1_Humidity_Pct'):
                            humidity1.append(float(row['Sensor1_Humidity_Pct']))
                        else:
                            humidity1.append(None)
                        
                        if row.get('Sensor2_Humidity_Pct'):
                            humidity2.append(float(row['Sensor2_Humidity_Pct']))
                        else:
                            humidity2.append(None)
                except Exception as e:
                    print(f"[SensorGraph] Error parsing row: {e}")
                    continue
            
            if not times:
                print(f"[SensorGraph] No valid time data found")
                return None
            
            # Create figure
            fig, ax = plt.subplots(figsize=(14, 6))
            
            # Plot data
            if any(h is not None for h in humidity1):
                ax.plot(times, humidity1, marker='o', label='Sensor 1', linewidth=2, markersize=4, color='#4ECDC4')
            
            if any(h is not None for h in humidity2):
                ax.plot(times, humidity2, marker='s', label='Sensor 2', linewidth=2, markersize=4, color='#FFE66D')
            
            # Format axes
            ax.set_xlabel('Time', fontsize=12, fontweight='bold')
            ax.set_ylabel('Humidity (%)', fontsize=12, fontweight='bold')
            ax.set_title(f'Humidity Readings - {date.strftime("%Y-%m-%d")}', fontsize=14, fontweight='bold')
            ax.set_ylim(0, 100)
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best', fontsize=10)
            
            # Format x-axis with time labels
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            fig.autofmt_xdate(rotation=45, ha='right')
            
            # Save figure
            fig.tight_layout()
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            print(f"[SensorGraph] Humidity graph saved: {filepath}")
            return filepath
        
        except Exception as e:
            print(f"[SensorGraph] ERROR generating humidity graph: {e}")
            return None
    
    def generate_combined_graph(self, date=None, filename=None):
        """Generate combined temperature and humidity graph with dual y-axes.
        
        Args:
            date: datetime object (default: today)
            filename: output filename (default: combined_YYYY-MM-DD.png)
            
        Returns:
            str: Path to saved graph image or None on error
        """
        try:
            if date is None:
                date = datetime.now()
            
            if filename is None:
                filename = f"combined_{date.strftime('%Y-%m-%d')}.png"
            
            filepath = os.path.join(self.output_dir, filename)
            
            # Get sensor data
            readings = self.sensor_logger.get_sensor_data(date=date)
            if not readings:
                print(f"[SensorGraph] No sensor data found for {date.strftime('%Y-%m-%d')}")
                return None
            
            # Parse data
            times = []
            temps1 = []
            humidity1 = []
            
            for row in readings:
                try:
                    time_str = row.get('Timestamp', '')
                    if time_str:
                        time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                        times.append(time)
                        
                        temps1.append(float(row['Sensor1_Temp_C']) if row.get('Sensor1_Temp_C') else None)
                        humidity1.append(float(row['Sensor1_Humidity_Pct']) if row.get('Sensor1_Humidity_Pct') else None)
                except Exception:
                    continue
            
            if not times:
                return None
            
            # Create figure with dual y-axes
            fig, ax1 = plt.subplots(figsize=(14, 6))
            
            # Temperature on left axis
            if any(t is not None for t in temps1):
                color1 = '#FF6B6B'
                ax1.set_xlabel('Time', fontsize=12, fontweight='bold')
                ax1.set_ylabel('Temperature (°C)', color=color1, fontsize=12, fontweight='bold')
                ax1.plot(times, temps1, color=color1, marker='o', linewidth=2, markersize=4, label='Temperature')
                ax1.tick_params(axis='y', labelcolor=color1)
                ax1.grid(True, alpha=0.3)
            
            # Humidity on right axis
            ax2 = ax1.twinx()
            if any(h is not None for h in humidity1):
                color2 = '#4ECDC4'
                ax2.set_ylabel('Humidity (%)', color=color2, fontsize=12, fontweight='bold')
                ax2.plot(times, humidity1, color=color2, marker='s', linewidth=2, markersize=4, label='Humidity')
                ax2.tick_params(axis='y', labelcolor=color2)
                ax2.set_ylim(0, 100)
            
            # Format x-axis
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax1.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            fig.autofmt_xdate(rotation=45, ha='right')
            
            # Title
            fig.suptitle(f'Temperature & Humidity - Sensor 1 - {date.strftime("%Y-%m-%d")}', 
                        fontsize=14, fontweight='bold')
            
            # Save figure
            fig.tight_layout()
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            print(f"[SensorGraph] Combined graph saved: {filepath}")
            return filepath
        
        except Exception as e:
            print(f"[SensorGraph] ERROR generating combined graph: {e}")
            return None
    
    def generate_ir_sensor_graph(self, date=None, filename=None):
        """Generate IR sensor detection graph with DHT22 temperature overlay.
        
        Shows IR sensor detection status (1=DETECTED, 0=CLEAR) as a line graph
        with DHT22 temperature readings on a secondary axis.
        
        Args:
            date: datetime object (default: today)
            filename: output filename (default: ir_sensors_YYYY-MM-DD.png)
            
        Returns:
            str: Path to saved graph image or None on error
        """
        try:
            if date is None:
                date = datetime.now()
            
            if filename is None:
                filename = f"ir_sensors_{date.strftime('%Y-%m-%d')}.png"
            
            filepath = os.path.join(self.output_dir, filename)
            
            # Get sensor data
            readings = self.sensor_logger.get_sensor_data(date=date)
            if not readings:
                print(f"[SensorGraph] No sensor data found for {date.strftime('%Y-%m-%d')}")
                return None
            
            # Parse data
            times = []
            ir_sensor1 = []
            ir_sensor2 = []
            temps1 = []
            
            for row in readings:
                try:
                    # Parse timestamp
                    time_str = row.get('Timestamp', '')
                    if time_str:
                        time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                        times.append(time)
                        
                        # Parse IR sensor status (convert to binary: 1 for DETECTED, 0 for CLEAR)
                        ir1_status = row.get('IR_Sensor1_Detection', '')
                        ir2_status = row.get('IR_Sensor2_Detection', '')
                        
                        ir_sensor1.append(1 if ir1_status == 'DETECTED' else (0 if ir1_status == 'CLEAR' else None))
                        ir_sensor2.append(1 if ir2_status == 'DETECTED' else (0 if ir2_status == 'CLEAR' else None))
                        
                        # Parse temperature for reference
                        if row.get('Sensor1_Temp_C'):
                            temps1.append(float(row['Sensor1_Temp_C']))
                        else:
                            temps1.append(None)
                except Exception as e:
                    print(f"[SensorGraph] Error parsing row: {e}")
                    continue
            
            if not times:
                print(f"[SensorGraph] No valid time data found")
                return None
            
            # Create figure with dual y-axes
            fig, ax1 = plt.subplots(figsize=(14, 6))
            
            # IR sensors on left axis
            color1 = '#E74C3C'
            ax1.set_xlabel('Time', fontsize=12, fontweight='bold')
            ax1.set_ylabel('IR Sensor Detection Status', color=color1, fontsize=12, fontweight='bold')
            
            if any(ir_val is not None for ir_val in ir_sensor1):
                ax1.plot(times, ir_sensor1, marker='o', linewidth=2, markersize=5, 
                        color=color1, label='IR Sensor 1', linestyle='-', alpha=0.8)
            
            if any(ir_val is not None for ir_val in ir_sensor2):
                ax1.plot(times, ir_sensor2, marker='s', linewidth=2, markersize=5, 
                        color='#C0392B', label='IR Sensor 2', linestyle='--', alpha=0.8)
            
            ax1.set_ylim(-0.2, 1.2)
            ax1.set_yticks([0, 1])
            ax1.set_yticklabels(['CLEAR', 'DETECTED'])
            ax1.tick_params(axis='y', labelcolor=color1)
            ax1.grid(True, alpha=0.3, axis='y')
            
            # Temperature on right axis (as reference)
            ax2 = ax1.twinx()
            if any(t is not None for t in temps1):
                color2 = '#3498DB'
                ax2.set_ylabel('Temperature (°C)', color=color2, fontsize=12, fontweight='bold')
                ax2.plot(times, temps1, color=color2, marker='^', linewidth=1.5, markersize=3, 
                        label='DHT22 Sensor 1 (Reference)', linestyle=':', alpha=0.6)
                ax2.tick_params(axis='y', labelcolor=color2)
            
            # Format x-axis
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax1.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            fig.autofmt_xdate(rotation=45, ha='right')
            
            # Title and legend
            fig.suptitle(f'IR Sensor Detection Status - {date.strftime("%Y-%m-%d")}', 
                        fontsize=14, fontweight='bold')
            
            # Combine legends from both axes
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)
            
            # Save figure
            fig.tight_layout()
            fig.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            print(f"[SensorGraph] IR sensor graph saved: {filepath}")
            return filepath
        
        except Exception as e:
            print(f"[SensorGraph] ERROR generating IR sensor graph: {e}")
            return None
        
    def generate_all_graphs(self, date=None):
        """Generate all available graphs for a date.
        
        Args:
            date: datetime object (default: today)
            
        Returns:
            dict: Paths to generated graphs
        """
        if date is None:
            date = datetime.now()
        
        return {
            'temperature': self.generate_temperature_graph(date),
            'humidity': self.generate_humidity_graph(date),
            'combined': self.generate_combined_graph(date),
            'ir_sensors': self.generate_ir_sensor_graph(date)
        }


if __name__ == "__main__":
    # Example usage
    import sys
    
    date = None
    if len(sys.argv) > 1:
        try:
            date = datetime.strptime(sys.argv[1], "%Y-%m-%d")
        except:
            print("Usage: python sensor_graph_generator.py [YYYY-MM-DD]")
            sys.exit(1)
    
    generator = SensorGraphGenerator()
    graphs = generator.generate_all_graphs(date)
    
    print("\nGenerated graphs:")
    for graph_type, filepath in graphs.items():
        print(f"  {graph_type}: {filepath}")
