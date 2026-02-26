#!/usr/bin/env python3
"""
Manual TEC relay test via Arduino Uno serial.

Commands:
  TEC ON
  TEC OFF
  STATUS
"""

import argparse
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


def send_cmd(ser, cmd):
    ser.write((cmd + "\n").encode("utf-8"))
    ser.flush()
    time.sleep(0.05)
    lines = []
    t0 = time.time()
    while time.time() - t0 < 1.0:
        if ser.in_waiting:
            line = ser.readline().decode(errors="ignore").strip()
            if line:
                lines.append(line)
        else:
            time.sleep(0.01)
    return lines


def main():
    parser = argparse.ArgumentParser(description="Manual TEC relay control test")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port or 'auto'")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    port = autodetect_port() if args.port.lower() == "auto" else args.port
    if not port:
        print("No serial port found")
        sys.exit(1)

    print(f"[TEC MANUAL] Connected to {port} @ {args.baud}")
    with serial.Serial(port, args.baud, timeout=1) as ser:
        print("Commands: on, off, status, q")
        while True:
            cmd = input("> ").strip().lower()
            if cmd in ("q", "quit", "exit"):
                break
            if cmd == "on":
                out = send_cmd(ser, "TEC ON")
            elif cmd == "off":
                out = send_cmd(ser, "TEC OFF")
            elif cmd == "status":
                out = send_cmd(ser, "STATUS")
            else:
                print("Unknown command")
                continue
            for line in out:
                print(line)


if __name__ == "__main__":
    main()

