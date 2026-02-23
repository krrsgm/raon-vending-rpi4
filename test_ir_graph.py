"""
Test script for IR sensor graph generation
Demonstrates the new IR sensor logging and graphing functionality
"""

from sensor_data_logger import get_sensor_logger
from sensor_graph_generator import SensorGraphGenerator
from datetime import datetime, timedelta
import random

def generate_test_data():
    """Generate sample sensor data for testing."""
    logger = get_sensor_logger(logs_dir="logs")
    
    print("Generating test sensor data...")
    
    base_time = datetime.now() - timedelta(hours=6)
    
    # Generate 24 test readings over 6 hours
    for i in range(24):
        current_time = base_time + timedelta(minutes=i*15)
        
        # Simulate temperature readings (cycling between 18-25°C)
        temp1 = 20 + 3*((i % 8) / 8.0)
        humidity1 = 45 + 15*random.random()
        
        temp2 = 21 + 2*((i % 6) / 6.0)
        humidity2 = 50 + 10*random.random()
        
        # Simulate IR sensor detections (random events)
        ir1_detected = random.choice([True, False, False, False])  # 25% detection rate
        ir2_detected = random.choice([True, False, False, False])
        
        relay_on = temp1 > 22
        target_temp = 22.0
        
        logger.log_sensor_reading(
            sensor1_temp=temp1,
            sensor1_humidity=humidity1,
            sensor2_temp=temp2,
            sensor2_humidity=humidity2,
            ir_sensor1_detection=ir1_detected,
            ir_sensor2_detection=ir2_detected,
            relay_status=relay_on,
            target_temp=target_temp
        )
        
        # Also log IR data separately for demonstration
        if i % 3 == 0:  # Every 45 minutes
            logger.log_ir_sensor_reading(
                ir_sensor1_detection=ir1_detected,
                ir_sensor2_detection=ir2_detected
            )
    
    print("✓ Test data generated successfully!")

def generate_graphs():
    """Generate visualization graphs."""
    generator = SensorGraphGenerator()
    
    print("\nGenerating graphs...")
    
    today = datetime.now().date()
    test_date = datetime.combine(today, datetime.min.time())
    
    graphs = generator.generate_all_graphs(test_date)
    
    print("\n✓ Graphs generated successfully:")
    print("=" * 60)
    for graph_type, filepath in graphs.items():
        if filepath:
            print(f"  ✓ {graph_type:15s}: {filepath}")
        else:
            print(f"  ✗ {graph_type:15s}: FAILED")
    print("=" * 60)
    
    return graphs

if __name__ == "__main__":
    print("=" * 60)
    print("IR Sensor Data Logging and Graphing Test")
    print("=" * 60)
    
    try:
        # Generate test data
        generate_test_data()
        
        # Generate graphs
        graphs = generate_graphs()
        
        print("\n✓ Test completed successfully!")
        print("\nNew Features Added:")
        print("  • IR sensor detection columns in CSV (IR_Sensor1_Detection, IR_Sensor2_Detection)")
        print("  • log_ir_sensor_reading() method for logging IR detections")
        print("  • generate_ir_sensor_graph() method for visualizing IR sensor data")
        print("  • IR sensor graph included in generate_all_graphs()")
        
    except Exception as e:
        print(f"\n✗ Error during test: {e}")
        import traceback
        traceback.print_exc()
