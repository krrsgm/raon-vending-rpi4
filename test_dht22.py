#!/usr/bin/env python3
"""
Arduino Uno DHT22 serial test.

Reads and prints DHT lines emitted by ArduinoUno_Bill_Forward.ino:
  DHT1: <temp>C <humidity>%
  DHT2: <temp>C <humidity>%
"""

import argparse
import re
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except Exception:
    print("Error: pyserial is required (pip install pyserial)")
    sys.exit(1)


def autodetect_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        mfg = (p.manufacturer or "").lower()
        if any(k in desc or k in mfg for k in ("arduino", "ch340", "cp210", "usb serial", "silicon labs")):
            return p.device
    return ports[0].device if ports else None


def main():
    parser = argparse.ArgumentParser(description="Arduino DHT22 serial test")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port or 'auto'")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    port = autodetect_port() if args.port.lower() == "auto" else args.port
    if not port:
        print("Error: No serial port found")
        sys.exit(1)

    p1 = re.compile(r"DHT1.*?:\s*([-\d.]+)C\s*([-\d.]+)%", re.IGNORECASE)
    p2 = re.compile(r"DHT2.*?:\s*([-\d.]+)C\s*([-\d.]+)%", re.IGNORECASE)
    d1 = (None, None)
    d2 = (None, None)

    print(f"[DHT TEST] Reading from {port} @ {args.baud}")
    print("[DHT TEST] Press Ctrl+C to stop.")
    try:
        with serial.Serial(port, args.baud, timeout=1) as ser:
            while True:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                m1 = p1.search(line)
                if m1:
                    d1 = (float(m1.group(1)), float(m1.group(2)))
                m2 = p2.search(line)
                if m2:
                    d2 = (float(m2.group(1)), float(m2.group(2)))
                if m1 or m2:
                    t = time.strftime("%H:%M:%S")
                    d1s = f"{d1[0]:.1f}C {d1[1]:.1f}%" if d1[0] is not None else "--"
                    d2s = f"{d2[0]:.1f}C {d2[1]:.1f}%" if d2[0] is not None else "--"
                    print(f"[{t}] DHT1={d1s} | DHT2={d2s}")
    except KeyboardInterrupt:
        print("\n[DHT TEST] Stopped")


if __name__ == "__main__":
    main()
