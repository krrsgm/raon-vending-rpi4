#!/usr/bin/env python3
"""Simple serial test helper to send BILL: lines to a serial port.

Usage:
  python3 tools/serial_test.py --port /dev/ttyUSB0 --baud 115200
"""
import argparse
import serial
import time

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', required=True)
    p.add_argument('--baud', type=int, default=115200)
    args = p.parse_args()

    ser = serial.Serial(args.port, args.baud, timeout=1)
    print('Opened', ser.name)
    try:
        while True:
            for amt in (20, 50, 100, 500, 1000):
                line = f'BILL:{amt}\n'
                ser.write(line.encode('utf-8'))
                print('Sent', line.strip())
                time.sleep(1)
            time.sleep(2)
    except KeyboardInterrupt:
        print('Exiting')
    finally:
        ser.close()

if __name__ == '__main__':
    main()

