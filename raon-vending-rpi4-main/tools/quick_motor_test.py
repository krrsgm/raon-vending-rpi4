#!/usr/bin/env python3
"""
quick_motor_test.py

Quick motor test script - fastest way to test if a motor works.

Usage:
    python quick_motor_test.py <slot> [config_file]
    
Examples:
    # Test slot 1 (uses default config.json)
    python quick_motor_test.py 1
    
    # Test slot 5
    python quick_motor_test.py 5
    
    # Test with custom config
    python quick_motor_test.py 1 custom_config.json
"""

import sys
import json
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from esp32_client import pulse_slot

def load_config(config_file='config.json'):
    """Load configuration from JSON file."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found: {config_file}")
        print("Make sure you're running from the vending kiosk directory")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {config_file}")
        return None

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    try:
        slot = int(sys.argv[1])
    except ValueError:
        print(f"Error: Slot must be a number, got: {sys.argv[1]}")
        return 1
    
    config_file = sys.argv[2] if len(sys.argv) > 2 else 'config.json'
    
    # Validate slot number
    if slot < 1 or slot > 64:
        print(f"Error: Slot must be between 1 and 64, got: {slot}")
        return 1
    
    # Load config
    config = load_config(config_file)
    if not config:
        return 1
    
    esp32_host = config.get('esp32_host', '192.168.4.1')
    pulse_ms = config.get('esp32_pulse_ms', 4500)
    
    if not esp32_host:
        print("Error: esp32_host not configured in config.json")
        print("Set it to one of:")
        print("  'serial:/dev/ttyUSB0' (for serial connection)")
        print("  '192.168.4.1' (for TCP/network connection)")
        return 1
    
    print(f"Testing motor on slot {slot}")
    print(f"ESP32 Host: {esp32_host}")
    print(f"Pulse Duration: {pulse_ms}ms")
    print(f"Config File: {config_file}")
    print()
    
    try:
        print(f"Sending PULSE command to slot {slot}...")
        result = pulse_slot(esp32_host, slot, pulse_ms)
        
        print(f"✓ SUCCESS! Motor should have pulsed.")
        print(f"  Response: {result if result else '(no response)'}")
        
        if not result:
            print()
            print("Note: No response from ESP32, but command was sent.")
            print("Motor may still have pulsed. Listen for the buzz/click sound.")
        
        return 0
        
    except TimeoutError as e:
        print(f"✗ TIMEOUT: ESP32 didn't respond in time")
        print(f"  Error: {e}")
        print()
        print("Troubleshooting:")
        print("- Check ESP32 is powered on")
        print("- Check USB cable (if using serial)")
        print("- Check network connection (if using TCP)")
        print("- Try running: python tools/test_esp32_connection.py {esp32_host}")
        return 1
        
    except ConnectionRefusedError as e:
        print(f"✗ CONNECTION REFUSED")
        print(f"  Error: {e}")
        print()
        print("Troubleshooting:")
        print("- Check ESP32 is powered on")
        print("- For serial: verify USB cable and port")
        print("- For TCP: verify network and IP address")
        return 1
        
    except Exception as e:
        print(f"✗ ERROR: {e}")
        print()
        print("Troubleshooting:")
        print("- Check config.json has correct esp32_host")
        print("- Run diagnostic: python tools/test_esp32_connection.py {esp32_host}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
