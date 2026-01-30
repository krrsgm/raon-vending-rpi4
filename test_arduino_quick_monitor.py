#!/usr/bin/env python3
"""
Quick Arduino diagnostic - shows raw serial data
Run this to see what Arduino is sending in real-time
"""

import serial
import sys
import glob

def find_arduino():
    """Auto-detect Arduino port"""
    ports = glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyUSB*')
    if ports:
        return ports[0]
    return '/dev/ttyACM0'

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_arduino()
    
    print(f"🔌 Connecting to {port}...")
    try:
        ser = serial.Serial(port, 115200, timeout=1)
        print(f"✓ Connected!")
        print(f"\n📨 Raw Arduino output (Ctrl+C to stop):\n")
        print("=" * 60)
        
        while True:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                text = data.decode('utf-8', errors='ignore')
                print(text, end='', flush=True)
                
    except FileNotFoundError:
        print(f"✗ Port {port} not found")
        print("\nAvailable USB ports:")
        ports = glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyUSB*')
        if ports:
            for p in ports:
                print(f"  - {p}")
        else:
            print("  (none found)")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n✓ Stopped")
    finally:
        ser.close()

if __name__ == '__main__':
    main()
