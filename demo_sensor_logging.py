#!/usr/bin/env python3
"""
Sensor Data Logging and Graphing Demo
Demonstrates sensor data recording and line graph generation
"""

from datetime import datetime
from sensor_data_logger import get_sensor_logger
from sensor_graph_generator import SensorGraphGenerator
import time
import random


def demo_sensor_logging():
    """Simulate logging sensor data and generate graphs."""
    print("=" * 70)
    print("Sensor Data Logging & Graphing Demo")
    print("=" * 70)
    print()
    
    # Get sensor logger
    sensor_logger = get_sensor_logger()
    
    print("[DEMO] Simulating sensor readings over time...")
    print()
    
    # Simulate reading data points
    num_readings = 12  # Simulate 12 readings (10 minutes of data at ~50-second intervals)
    
    for i in range(num_readings):
        # Simulate temperature fluctuations (cooling cycle)
        cycle_progress = (i % 4) / 4.0  # 4-step cycle
        
        # Sensor 1: starts at 25°C, cools to 10°C
        temp1 = 25.0 - (cycle_progress * 15.0)
        humidity1 = 45.0 + random.uniform(-5, 5)
        
        # Sensor 2: offset reading
        temp2 = 26.0 - (cycle_progress * 14.0)
        humidity2 = 48.0 + random.uniform(-5, 5)
        
        # Relay status: ON if cooling (cycle_progress < 0.5)
        relay_status = cycle_progress < 0.5
        
        # Log the reading
        sensor_logger.log_sensor_reading(
            sensor1_temp=round(temp1, 1),
            sensor1_humidity=round(humidity1, 1),
            sensor2_temp=round(temp2, 1),
            sensor2_humidity=round(humidity2, 1),
            relay_status=relay_status,
            target_temp=10.0
        )
        
        relay_text = "ON " if relay_status else "OFF"
        print(f"[{i+1:2d}] Sensor 1: {temp1:5.1f}°C | Humidity: {humidity1:5.1f}% | Relay: {relay_text}")
        
        # Wait before next reading (0.5 seconds for demo speed)
        if i < num_readings - 1:
            time.sleep(0.5)
    
    print()
    print("[DEMO] ✓ Sensor data logged successfully")
    print()
    
    # Generate graphs
    print("[DEMO] Generating graphs...")
    print()
    
    generator = SensorGraphGenerator()
    today = datetime.now()
    
    graphs = {
        'Temperature': generator.generate_temperature_graph(today),
        'Humidity': generator.generate_humidity_graph(today),
        'Combined': generator.generate_combined_graph(today)
    }
    
    print("[DEMO] ✓ Graphs generated successfully")
    print()
    print("Generated graph files:")
    for graph_name, filepath in graphs.items():
        if filepath:
            print(f"  • {graph_name}: {filepath}")
    print()
    
    # Get temperature statistics
    print("[DEMO] Temperature Statistics:")
    stats = sensor_logger.get_temperature_stats(today)
    
    if 'sensor1' in stats:
        s1 = stats['sensor1']
        if s1['samples'] > 0:
            print(f"  Sensor 1:")
            print(f"    Samples:  {s1['samples']}")
            print(f"    Min:      {s1['min']:.1f}°C")
            print(f"    Max:      {s1['max']:.1f}°C")
            print(f"    Average:  {s1['avg']:.1f}°C")
    
    if 'sensor2' in stats:
        s2 = stats['sensor2']
        if s2['samples'] > 0:
            print(f"  Sensor 2:")
            print(f"    Samples:  {s2['samples']}")
            print(f"    Min:      {s2['min']:.1f}°C")
            print(f"    Max:      {s2['max']:.1f}°C")
            print(f"    Average:  {s2['avg']:.1f}°C")
    
    print()
    print("[DEMO] ✓ Demo completed successfully")
    print()
    print("To generate graphs for a specific date:")
    print("  python sensor_graph_generator.py YYYY-MM-DD")
    print()
    print("To use in your application:")
    print("  from sensor_data_logger import get_sensor_logger")
    print("  logger = get_sensor_logger()")
    print("  logger.log_sensor_reading(sensor1_temp=25.5, sensor1_humidity=45.0, ...)")
    print()


if __name__ == "__main__":
    try:
        demo_sensor_logging()
    except KeyboardInterrupt:
        print("\n[DEMO] Interrupted by user")
    except Exception as e:
        print(f"\n[DEMO] Error: {e}")
        import traceback
        traceback.print_exc()
