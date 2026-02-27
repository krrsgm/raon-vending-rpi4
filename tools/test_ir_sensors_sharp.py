#!/usr/bin/env python3
"""
Sharp GP2Y0A21YK0F IR Sensor Test (serial).

Reads IR1/IR2 BLOCKED/CLEAR lines from Arduino/ESP32 firmware and reports
live status plus simple statistics to validate chute detection behavior.

Expected serial output lines:
  IR1: BLOCKED|CLEAR
  IR2: BLOCKED|CLEAR
"""

import argparse
import re
import sys
import time

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except Exception:
    SERIAL_AVAILABLE = False


def autodetect_port():
    if not SERIAL_AVAILABLE:
        return None
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        mfg = (p.manufacturer or "").lower()
        if any(k in desc or k in mfg for k in ("esp32", "arduino", "cp210", "ch340", "silicon labs")):
            return p.device
    return ports[0].device if ports else None


def read_ir_stream(port, duration, baud):
    try:
        ser = serial.Serial(port, baud, timeout=1)
    except Exception as e:
        print(f"[ERROR] Could not open serial port {port}: {e}")
        return 1

    pattern1 = re.compile(r"IR1.*?:\s*(BLOCKED|CLEAR)", re.IGNORECASE)
    pattern2 = re.compile(r"IR2.*?:\s*(BLOCKED|CLEAR)", re.IGNORECASE)

    start = time.time()
    ir1 = None
    ir2 = None
    last_ir1 = None
    last_ir2 = None
    ir1_blocked = 0
    ir1_clear = 0
    ir2_blocked = 0
    ir2_clear = 0
    ir1_changes = 0
    ir2_changes = 0

    print("=" * 64)
    print("Sharp IR Sensor Test (Serial)")
    print(f"Port: {port}  Baud: {baud}  Duration: {duration}s")
    print("Listening for IR1/IR2 BLOCKED/CLEAR lines...")
    print("=" * 64)
    print(f"{'Time (s)':>8} | {'IR1':>8} | {'IR2':>8} | {'Notes':<30}")
    print("-" * 64)

    try:
        while time.time() - start < duration:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue
            t = time.time() - start
            note = ""

            m1 = pattern1.search(line)
            m2 = pattern2.search(line)
            if m1:
                ir1 = m1.group(1).upper()
                if ir1 == "BLOCKED":
                    ir1_blocked += 1
                else:
                    ir1_clear += 1
                if last_ir1 is not None and ir1 != last_ir1:
                    ir1_changes += 1
                    note = "IR1 change"
                last_ir1 = ir1
            if m2:
                ir2 = m2.group(1).upper()
                if ir2 == "BLOCKED":
                    ir2_blocked += 1
                else:
                    ir2_clear += 1
                if last_ir2 is not None and ir2 != last_ir2:
                    ir2_changes += 1
                    note = (note + ", " if note else "") + "IR2 change"
                last_ir2 = ir2

            if m1 or m2:
                s1 = ir1 if ir1 is not None else "--"
                s2 = ir2 if ir2 is not None else "--"
                print(f"{t:8.1f} | {s1:>8} | {s2:>8} | {note:<30}")

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    finally:
        try:
            ser.close()
        except Exception:
            pass

    print("\nSummary")
    print("-" * 64)
    print(f"IR1 samples: blocked={ir1_blocked} clear={ir1_clear} changes={ir1_changes}")
    print(f"IR2 samples: blocked={ir2_blocked} clear={ir2_clear} changes={ir2_changes}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Sharp GP2Y0A21YK0F IR sensor test (serial)")
    parser.add_argument("--port", default="auto", help="Serial port (or 'auto')")
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    args = parser.parse_args()

    if not SERIAL_AVAILABLE:
        print("[ERROR] pyserial is required. Install with: pip install pyserial")
        return 1

    port = autodetect_port() if args.port.lower() == "auto" else args.port
    if not port:
        print("[ERROR] No serial port found. Specify --port explicitly.")
        return 1

    return read_ir_stream(port, args.duration, args.baud)


if __name__ == "__main__":
    sys.exit(main())
