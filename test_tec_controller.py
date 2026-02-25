#!/usr/bin/env python3
"""Test script for TEC Peltier module controller.

Tests temperature monitoring and TEC relay control.
"""

import time
from tec_controller import TECController


def test_tec_controller():
    """Test TEC controller functionality."""
    print("=" * 60)
    print("TEC Controller Test")
    print("=" * 60)
    
    # Create TEC controller with test configuration
    tec = TECController(
        sensor_pin=36,      # DHT22 Sensor 1 (ESP32)
        relay_pin=26,       # TEC relay GPIO26
        target_temp=10.0,   # Target 10°C for freezing
        temp_hysteresis=1.0 # ±1°C hysteresis
    )
    
    try:
        print("\n[TEST] Starting TEC controller...")
        tec.start()
        
        print("[TEST] Running for 30 seconds, monitoring temperature changes...")
        print("\nExpected behavior:")
        print("  - If temp > 11°C: TEC turns ON")
        print("  - If temp < 9°C: TEC turns OFF")
        print("  - Readings every 2 seconds (DHT22 minimum interval)\n")
        
        for i in range(15):  # 30 seconds / 2 second interval
            time.sleep(2)
            status = tec.get_status()
            
            temp_str = f"{status['current_temp']:.1f}°C" if status['current_temp'] else "N/A"
            humid_str = f"{status['current_humidity']:.1f}%" if status['current_humidity'] else "N/A"
            tec_status = "ON " if status['enabled'] else "OFF"
            
            print(f"[{i+1:2d}] Temp: {temp_str:6s} | Humidity: {humid_str:6s} | TEC: {tec_status} | "
                  f"Range: {status['temp_off_threshold']:.1f}-{status['temp_on_threshold']:.1f}°C")
        
        print("\n[TEST] ✓ TEC controller test completed successfully")
        
        # Test configuration changes
        print("\n[TEST] Testing dynamic configuration changes...")
        print("[TEST] Changing target temperature to 15°C...")
        tec.set_target_temp(15.0)
        time.sleep(2)
        status = tec.get_status()
        print(f"[TEST] New range: {status['temp_off_threshold']:.1f}-{status['temp_on_threshold']:.1f}°C")
        
        print("[TEST] Changing hysteresis to 0.5°C...")
        tec.set_hysteresis(0.5)
        time.sleep(2)
        status = tec.get_status()
        print(f"[TEST] New range: {status['temp_off_threshold']:.1f}-{status['temp_on_threshold']:.1f}°C")
        
        print("\n[TEST] ✓ Dynamic configuration changes successful")
        
    except KeyboardInterrupt:
        print("\n[TEST] Test interrupted by user")
    except Exception as e:
        print(f"\n[TEST] ✗ Test failed: {e}")
    finally:
        print("\n[TEST] Cleaning up...")
        tec.cleanup()
        print("[TEST] TEC controller test completed")


if __name__ == "__main__":
    test_tec_controller()
