#!/usr/bin/env python3
"""Simple USB serial listener for Arduino bill forwarder.

Autodetects a likely Arduino / USB-serial device and prints parsed
BILL:<amount> lines with timestamps. Useful to verify Uno -> Pi USB
communication and to debug why bills aren't appearing in the kiosk.

Usage:
  python3 tools/usb_bill_listener.py          # autodetect device, use 115200
  python3 tools/usb_bill_listener.py /dev/ttyUSB0 9600

"""
import sys
import time
import argparse

try:
    import serial
    from serial.tools import list_ports
except Exception as e:
    print("pyserial is required: pip3 install pyserial")
    raise


def find_usb_serial():
    # Prefer devices that look like Arduino or common USB-serial chips
    ports = list(list_ports.comports())
    candidates = []
    for p in ports:
        desc = (p.description or '').lower()
        name = (p.device or '')
        if any(k in desc for k in ('arduino', 'cp210', 'ch340', 'ftdi')):
            return name
        candidates.append(name)
    return candidates[0] if candidates else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('port', nargs='?', help='Serial port (e.g. /dev/ttyUSB0)')
    ap.add_argument('baud', nargs='?', type=int, default=115200, help='Baud rate (default 115200)')
    ap.add_argument('--only-bill', action='store_true', help='Only print final bill lines (BILL: or Bill inserted)')
    args = ap.parse_args()

    port = args.port
    baud = args.baud

    if not port:
        autodetected = find_usb_serial()
        if not autodetected:
            print('No serial ports found. Connect the Arduino and try again.')
            sys.exit(1)
        print(f'Autodetected serial port: {autodetected}')
        port = autodetected

    try:
        ser = serial.Serial(port, baudrate=baud, timeout=1)
    except Exception as e:
        print(f'Failed to open serial port {port}: {e}')
        sys.exit(1)

    print(f'Listening on {port} @ {baud}. Press Ctrl-C to exit.')

    try:
        while True:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
            except Exception:
                line = ''
            if not line:
                continue
            ts = time.time()
            # If requested, filter to only show final bill lines
            up = line.upper()
            if args.only_bill:
                # Accept human-friendly or canonical BILL lines
                if up.startswith('BILL:') or 'BILL INSERTED' in up:
                    print(f"{time.strftime('%H:%M:%S', time.localtime(ts))}.{int((ts%1)*1000):03d} <- {line}")
                    # If it's a BILL: line, parse and print friendly message
                    if up.startswith('BILL:'):
                        try:
                            val = int(line.split(':',1)[1])
                            print(f"  -> Parsed bill: â‚±{val}")
                        except Exception:
                            print('  -> Unrecognized BILL line')
                continue

            # Print raw line with timestamp
            print(f"{time.strftime('%H:%M:%S', time.localtime(ts))}.{int((ts%1)*1000):03d} <- {line}")
            # If it's a BILL: line, parse and print friendly message
            if up.startswith('BILL:'):
                try:
                    val = int(line.split(':',1)[1])
                    print(f"  -> Parsed bill: â‚±{val}")
                except Exception:
                    print('  -> Unrecognized BILL line')
    except KeyboardInterrupt:
        print('\nExiting...')
    finally:
        try:
            ser.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

