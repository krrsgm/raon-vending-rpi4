#!/usr/bin/env python3
"""
diagnose_serial.py
Diagnose serial port issues and show what's happening when motor test fails.
"""
import json
import os
import sys
import platform

def check_config():
    """Check what's in config.json"""
    print("\n" + "="*60)
    print("1. CHECKING CONFIG FILE")
    print("="*60)
    
    config_path = "config.json"
    if not os.path.exists(config_path):
        print(f"  ✗ config.json NOT FOUND at {os.path.abspath(config_path)}")
        return None
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        esp32_host = config.get('esp32_host', 'NOT SET')
        print(f"  ✓ config.json found")
        print(f"    - esp32_host: {esp32_host}")
        return esp32_host
    except Exception as e:
        print(f"  ✗ Error reading config.json: {e}")
        return None

def check_platform():
    """Check what platform we're on"""
    print("\n" + "="*60)
    print("2. CHECKING PLATFORM")
    print("="*60)
    
    system = platform.system()
    print(f"  - OS: {system}")
    
    if system == "Windows":
        print(f"  ⚠ Running on Windows!")
        print(f"    - Motor test needs to run on Raspberry Pi")
        print(f"    - /dev/ttyS0 paths don't exist on Windows")
        print(f"    - You must test on the Raspberry Pi itself")
        return False
    elif system == "Linux":
        print(f"  ✓ Running on Linux (likely Raspberry Pi)")
        return True
    else:
        print(f"  ? Unknown OS")
        return None

def check_serial_port(port_name):
    """Check if serial port exists and is accessible"""
    print("\n" + "="*60)
    print("3. CHECKING SERIAL PORT")
    print("="*60)
    
    if port_name.startswith('serial:'):
        port_name = port_name.split(':', 1)[1]
    
    print(f"  - Port: {port_name}")
    
    if not os.path.exists(port_name):
        print(f"  ✗ Port does NOT exist: {port_name}")
        print(f"    - ESP32 might not be connected")
        print(f"    - Try listing /dev/tty*")
        return False
    
    print(f"  ✓ Port exists: {port_name}")
    
    # Check permissions
    if os.access(port_name, os.R_OK):
        print(f"  ✓ Port is readable")
    else:
        print(f"  ✗ Port is NOT readable (permission denied)")
        return False
    
    if os.access(port_name, os.W_OK):
        print(f"  ✓ Port is writable")
    else:
        print(f"  ✗ Port is NOT writable (permission denied)")
        return False
    
    return True

def check_pyserial():
    """Check if pyserial is installed"""
    print("\n" + "="*60)
    print("4. CHECKING PYSERIAL")
    print("="*60)
    
    try:
        import serial
        print(f"  ✓ pyserial is installed")
        print(f"    - Version: {serial.VERSION}")
        return True
    except ImportError:
        print(f"  ✗ pyserial is NOT installed")
        print(f"    - Install with: pip3 install pyserial")
        return False

def test_serial_open(port_name):
    """Try to actually open the serial port"""
    print("\n" + "="*60)
    print("5. TESTING SERIAL PORT OPEN")
    print("="*60)
    
    if port_name.startswith('serial:'):
        port_name = port_name.split(':', 1)[1]
    
    try:
        import serial
    except ImportError:
        print(f"  ⚠ pyserial not installed, skipping test")
        return False
    
    try:
        print(f"  - Attempting to open {port_name}...")
        ser = serial.Serial(port_name, baudrate=115200, timeout=1.0)
        print(f"  ✓ Port opened successfully!")
        ser.close()
        print(f"  ✓ Port closed")
        return True
    except PermissionError as e:
        print(f"  ✗ Permission denied: {e}")
        print(f"    - Try: sudo chmod 666 {port_name}")
        print(f"    - Or: sudo usermod -a -G dialout pi")
        return False
    except OSError as e:
        print(f"  ✗ Cannot open port: {e}")
        if "Device or resource busy" in str(e):
            print(f"    - Port is already in use by another process")
            print(f"    - Check if another program has the port open")
        return False
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def list_serial_ports():
    """List available serial ports"""
    print("\n" + "="*60)
    print("6. AVAILABLE SERIAL PORTS")
    print("="*60)
    
    try:
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        
        if ports:
            for p in ports:
                print(f"  - {p.device}: {p.description}")
        else:
            print(f"  - No serial ports found")
    except Exception as e:
        print(f"  - Cannot list ports: {e}")

def main():
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║  RAON VENDING - SERIAL COMMUNICATION DIAGNOSTIC  ║")
    print("╚" + "="*58 + "╝")
    
    # Check config
    esp32_host = check_config()
    if not esp32_host:
        print("\n✗ Cannot proceed without esp32_host in config.json")
        return
    
    # Check platform
    is_linux = check_platform()
    if is_linux is False:
        print("\n✗ This diagnostic must be run on Raspberry Pi!")
        print("  Copy and run this script on the Raspberry Pi:")
        print("  $ python3 tools/diagnose_serial.py")
        return
    
    # Check serial port
    if is_linux:
        port_ok = check_serial_port(esp32_host)
        
        if not port_ok:
            print("\n⚠ Serial port is not accessible")
            list_serial_ports()
            return
        
        # Check pyserial
        if not check_pyserial():
            return
        
        # Try to open port
        if test_serial_open(esp32_host):
            print("\n" + "="*60)
            print("✓ SERIAL PORT IS READY")
            print("="*60)
            print("\nNow test motor with assign_items_screen!")
            print("If it still fails, try:")
            print("  1. Make sure ESP32 is powered on")
            print("  2. Verify RXTX cable is connected properly")
            print("  3. Check ESP32 firmware is loaded")
            print("  4. Run: python3 tools/test_rxtx_communication.py")
        else:
            print("\n" + "="*60)
            print("✗ CANNOT OPEN SERIAL PORT")
            print("="*60)

if __name__ == '__main__':
    main()
