#!/usr/bin/env python3
"""
TEC Peltier Relay Manual Control Test
Tests turning the TEC relay on and off manually.
"""

import time
from tec_controller import TECController


def test_relay_on_off():
    """Test manual relay on/off control."""
    print("=" * 70)
    print("TEC Peltier Relay Manual Control Test")
    print("=" * 70)
    print()
    
    # Create TEC controller
    tec = TECController(
        sensor_pins=[27, 22],  # GPIO27 Sensor 1, GPIO22 Sensor 2
        relay_pin=26,          # TEC relay on GPIO26
        target_temp=10.0,
        temp_hysteresis=1.0
    )
    
    try:
        print("[INFO] Initializing TEC controller...")
        tec.start()
        time.sleep(1)
        
        print("[INFO] TEC controller started successfully")
        print()
        
        # Test sequence
        test_sequence = [
            ("ON", 5, tec.manual_on),
            ("OFF", 5, tec.manual_off),
            ("ON", 5, tec.manual_on),
            ("OFF", 5, tec.manual_off),
            ("ON", 5, tec.manual_on),
            ("OFF", 5, tec.manual_off),
        ]
        
        for state, duration, control_func in test_sequence:
            print(f"[TEST] Turning relay {state}...")
            control_func()
            
            status = tec.get_status()
            relay_state = "ON " if status['enabled'] else "OFF"
            print(f"[TEST] Current relay state: {relay_state}")
            print(f"[TEST] Holding for {duration} seconds...")
            
            # Show countdown
            for i in range(duration):
                remaining = duration - i
                temp_str = f"{status['current_temp']:.1f}°C" if status['current_temp'] else "N/A"
                humidity_str = f"{status['current_humidity']:.1f}%" if status['current_humidity'] else "N/A"
                
                print(f"       [{remaining:d}s] Temp: {temp_str:6s} | Humidity: {humidity_str:6s} | Relay: {relay_state}")
                
                if i < duration - 1:
                    time.sleep(1)
                    status = tec.get_status()
                    relay_state = "ON " if status['enabled'] else "OFF"
            
            print()
        
        print("[TEST] ✓ Relay on/off test completed successfully!")
        print()
        
        # Final state
        print("[INFO] Turning relay OFF for safety...")
        tec.manual_off()
        
    except KeyboardInterrupt:
        print("\n[TEST] Test interrupted by user")
        tec.manual_off()
    except Exception as e:
        print(f"\n[TEST] ✗ Test failed: {e}")
        tec.manual_off()
    finally:
        print("[INFO] Cleaning up...")
        tec.cleanup()
        print("[INFO] Test completed")


def test_relay_with_interactive():
    """Interactive relay control test."""
    print("=" * 70)
    print("TEC Peltier Relay Interactive Control Test")
    print("=" * 70)
    print()
    
    # Create TEC controller
    tec = TECController(
        sensor_pins=[27, 22],
        relay_pin=26,
        target_temp=10.0,
        temp_hysteresis=1.0
    )
    
    try:
        print("[INFO] Initializing TEC controller...")
        tec.start()
        time.sleep(1)
        
        print("[INFO] TEC controller started successfully")
        print()
        print("Commands: (O)n | (F)off | (S)tatus | (Q)uit")
        print()
        
        while True:
            try:
                command = input("Enter command: ").strip().upper()
                
                if command == 'O':
                    print("[TEST] Turning Relay ON...")
                    tec.manual_on()
                    status = tec.get_status()
                    print(f"[TEST] Relay is now: {'ON' if status['enabled'] else 'OFF'}")
                    
                elif command == 'F':
                    print("[TEST] Turning Relay OFF...")
                    tec.manual_off()
                    status = tec.get_status()
                    print(f"[TEST] Relay is now: {'ON' if status['enabled'] else 'OFF'}")
                    
                elif command == 'S':
                    status = tec.get_status()
                    relay_state = "ON " if status['enabled'] else "OFF"
                    temp_str = f"{status['current_temp']:.1f}°C" if status['current_temp'] else "N/A"
                    humidity_str = f"{status['current_humidity']:.1f}%" if status['current_humidity'] else "N/A"
                    
                    print()
                    print("=== TEC Status ===")
                    print(f"  Relay State:    {relay_state}")
                    print(f"  Temperature:    {temp_str}")
                    print(f"  Humidity:       {humidity_str}")
                    print(f"  Target Temp:    {status['target_temp']}°C")
                    print(f"  Control Range:  {status['temp_off_threshold']:.1f}°C - {status['temp_on_threshold']:.1f}°C")
                    print(f"  Sensor Temps:   {status['sensor_temps']}")
                    print(f"  Sensor Humid:   {status['sensor_humidities']}")
                    print()
                    
                elif command == 'Q':
                    print("[INFO] Exiting...")
                    break
                    
                else:
                    print("[ERROR] Invalid command. Use O, F, S, or Q")
                
            except KeyboardInterrupt:
                print("\n[INFO] Exiting...")
                break
        
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
    finally:
        print("[INFO] Cleaning up...")
        tec.manual_off()
        tec.cleanup()
        print("[INFO] Test completed")


if __name__ == "__main__":
    import sys
    
    print()
    print("Available tests:")
    print("  1. Automatic relay on/off sequence")
    print("  2. Interactive relay control")
    print()
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
    else:
        test_type = input("Select test (1 or 2): ").strip()
    
    print()
    
    if test_type == '2':
        test_relay_with_interactive()
    else:
        test_relay_on_off()
