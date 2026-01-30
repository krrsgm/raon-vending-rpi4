#!/usr/bin/env python3
"""
test_esp32_connection.py

Diagnostic tool to test ESP32 vending controller connection.
Helps debug motor test issues by checking connection status.

Usage:
    python test_esp32_connection.py <host> [--verbose]
    
Examples:
    python test_esp32_connection.py serial:/dev/ttyUSB0
    python test_esp32_connection.py 192.168.4.1
    python test_esp32_connection.py 192.168.4.1 --verbose
"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from esp32_client import send_command, pulse_slot
import logging

def test_connection(host, verbose=False):
    """Test ESP32 connection with detailed diagnostics."""
    
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
    
    print("=" * 70)
    print("ESP32 VENDING CONTROLLER CONNECTION TEST")
    print("=" * 70)
    print(f"\nTarget Host: {host}")
    
    # Determine connection type
    if host.startswith('serial:'):
        conn_type = "Serial (UART)"
        port_info = host.split(':', 1)[1]
        print(f"Connection Type: {conn_type}")
        print(f"Serial Port: {port_info}")
        print(f"Baud Rate: 115200")
    else:
        conn_type = "TCP/Network"
        print(f"Connection Type: {conn_type}")
        print(f"Host: {host}")
        print(f"Port: 5000 (default)")
    
    print("\n" + "-" * 70)
    print("Test 1: STATUS Command")
    print("-" * 70)
    
    try:
        print(f"Sending: STATUS")
        result = send_command(host, "STATUS", timeout=2.0)
        print(f"✓ Response received: {result}")
        print(f"✓ Connection test PASSED")
        return True, result
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print(f"✗ Connection test FAILED")
        return False, str(e)

def test_pulse(host, slot=1, verbose=False):
    """Test motor pulse on a specific slot."""
    
    print("\n" + "-" * 70)
    print(f"Test 2: PULSE Slot {slot}")
    print("-" * 70)
    
    try:
        print(f"Sending: PULSE {slot} 100")
        result = pulse_slot(host, slot, 100)
        print(f"✓ Pulse sent successfully")
        if result:
            print(f"✓ Response received: {result}")
        return True
    except Exception as e:
        print(f"✗ Pulse test failed: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Test ESP32 vending controller connection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_esp32_connection.py serial:/dev/ttyUSB0
  python test_esp32_connection.py 192.168.4.1
  python test_esp32_connection.py 192.168.4.1 --verbose
        """
    )
    
    parser.add_argument('host', help='ESP32 host (serial:/dev/ttyUSB0 or IP address)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    parser.add_argument('--slot', type=int, default=1, help='Slot number to test pulse on (default: 1)')
    
    args = parser.parse_args()
    
    if not args.host:
        print("Error: No host specified")
        parser.print_help()
        return 1
    
    # Test connection
    success, result = test_connection(args.host, args.verbose)
    
    if success:
        # Test pulse on specified slot
        pulse_ok = test_pulse(args.host, args.slot, args.verbose)
        
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"✓ ESP32 is reachable")
        print(f"✓ Connection working properly")
        print(f"\nYou can now use motor test in the admin screen.")
        print(f"ESP32 Status: {result}")
        return 0
    else:
        print("\n" + "=" * 70)
        print("TROUBLESHOOTING")
        print("=" * 70)
        
        if args.host.startswith('serial:'):
            port = args.host.split(':', 1)[1]
            print(f"\nSerial Connection Issues:")
            print(f"1. Check USB cable is properly connected")
            print(f"2. Verify serial port exists: {port}")
            print(f"3. Check USB permissions (may need sudo on Linux/Mac)")
            print(f"4. Try different USB port")
            print(f"5. Verify ESP32 firmware is loaded")
            print(f"\nOn Linux, list available ports:")
            print(f"  ls /dev/ttyUSB* /dev/ttyACM*")
        else:
            print(f"\nNetwork Connection Issues:")
            print(f"1. Check ESP32 is powered on")
            print(f"2. Verify network connection")
            print(f"3. Check firewall isn't blocking port 5000")
            print(f"4. Try pinging the host: ping {args.host}")
            print(f"5. Verify ESP32 IP address is correct")
        
        print(f"\nError: {result}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
