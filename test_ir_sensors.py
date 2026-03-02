#!/usr/bin/env python3
"""
IR Sensor Test - Arduino Uno serial first (A0/A1 analog IR via serial).

Expected Arduino serial output examples:
  IR1: BLOCKED|CLEAR
  IR2: BLOCKED|CLEAR
  IR1: BLOCKED ADC=512 | IR2: CLEAR ADC=301
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

GPIO_AVAILABLE = False
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except Exception:
    # Allow running on non-RPi machines.
    try:
        from rpi_gpio_mock import GPIO as GPIO
        GPIO_AVAILABLE = True
    except Exception:
        GPIO_AVAILABLE = False

# Raspberry Pi sensor pins (legacy digital mode).
SENSOR_1_PIN = 24
SENSOR_2_PIN = 25

# Arduino Uno analog pin labels (from firmware).
UNO_IR1_LABEL = "IR1 (A0)"
UNO_IR2_LABEL = "IR2 (A1)"


def autodetect_serial_port():
    if not SERIAL_AVAILABLE:
        return None
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        mfg = (p.manufacturer or "").lower()
        if any(k in desc or k in mfg for k in ("esp32", "arduino", "cp210", "ch340", "silicon labs")):
            return p.device
    return ports[0].device if ports else None


def read_from_serial(port, duration=30):
    """Read IR status lines from serial and print a table for Uno A0/A1 sensors."""
    try:
        ser = serial.Serial(port, 115200, timeout=1)
    except Exception as e:
        print(f"[ERROR] Could not open serial port {port}: {e}")
        return

    print(f"[INFO] Reading IR sensor states from {port} for {duration}s")
    print(f"{'Time (s)':>8} | {UNO_IR1_LABEL:>10} | {'ADC':>4} | {UNO_IR2_LABEL:>10} | {'ADC':>4}")
    print("-" * 56)

    start = time.time()
    ir1 = None
    ir2 = None
    ir1_adc = None
    ir2_adc = None

    # Combined single-line format (newer firmware).
    dual_pattern = re.compile(
        r"IR1:\s*(BLOCKED|CLEAR)\s*(?:ADC=|raw=)?\s*(\d+)?\s*\|\s*IR2:\s*(BLOCKED|CLEAR)\s*(?:ADC=|raw=)?\s*(\d+)?",
        re.IGNORECASE,
    )
    # Separate line format (legacy/new).
    pattern1 = re.compile(r"IR1.*?:\s*(BLOCKED|CLEAR)", re.IGNORECASE)
    pattern2 = re.compile(r"IR2.*?:\s*(BLOCKED|CLEAR)", re.IGNORECASE)
    adc1_pattern = re.compile(r"IR1.*?(?:ADC=|raw=)\s*(\d+)", re.IGNORECASE)
    adc2_pattern = re.compile(r"IR2.*?(?:ADC=|raw=)\s*(\d+)", re.IGNORECASE)

    try:
        while time.time() - start < duration:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue

            t = time.time() - start
            matched = False

            md = dual_pattern.search(line)
            if md:
                ir1 = md.group(1).upper()
                ir2 = md.group(3).upper()
                ir1_adc = int(md.group(2)) if md.group(2) else ir1_adc
                ir2_adc = int(md.group(4)) if md.group(4) else ir2_adc
                matched = True
            else:
                m1 = pattern1.search(line)
                m2 = pattern2.search(line)
                a1 = adc1_pattern.search(line)
                a2 = adc2_pattern.search(line)
                if m1:
                    ir1 = m1.group(1).upper()
                    matched = True
                if m2:
                    ir2 = m2.group(1).upper()
                    matched = True
                if a1:
                    ir1_adc = int(a1.group(1))
                if a2:
                    ir2_adc = int(a2.group(1))

            if matched:
                s1 = ir1 if ir1 is not None else "--"
                s2 = ir2 if ir2 is not None else "--"
                a1 = str(ir1_adc) if ir1_adc is not None else "--"
                a2 = str(ir2_adc) if ir2_adc is not None else "--"
                print(f"{t:8.1f} | {s1:>10} | {a1:>4} | {s2:>10} | {a2:>4}")

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    finally:
        try:
            ser.close()
        except Exception:
            pass


def read_from_gpio(duration=30, interval=0.5):
    if not GPIO_AVAILABLE:
        print("[ERROR] GPIO not available on this system")
        return

    print("[WARNING] GPIO mode is legacy digital mode. Uno analog A0/A1 is available via --mode serial.")

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SENSOR_1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(SENSOR_2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    except Exception as e:
        print(f"[ERROR] Failed to initialize GPIO: {e}")
        return

    print(f"[INFO] GPIO initialized (GPIO_AVAILABLE={GPIO_AVAILABLE})")
    print(f"Reading IR sensors on GPIO {SENSOR_1_PIN} and {SENSOR_2_PIN} for {duration}s")
    print(f"{'Time (s)':>8} | {'Sensor 1':>18} | {'Sensor 2':>18}")
    print("-" * 54)

    start = time.time()
    try:
        while time.time() - start < duration:
            elapsed = time.time() - start
            s1_state = GPIO.input(SENSOR_1_PIN)
            s2_state = GPIO.input(SENSOR_2_PIN)
            state_1 = "HIGH (no object)" if s1_state else "LOW (object detected)"
            state_2 = "HIGH (no object)" if s2_state else "LOW (object detected)"
            print(f"{elapsed:8.1f} | {state_1:>18} | {state_2:>18}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    finally:
        try:
            GPIO.cleanup()
            print("\n[INFO] GPIO cleaned up")
        except Exception as e:
            print(f"\n[WARNING] Error during cleanup: {e}")


def main():
    parser = argparse.ArgumentParser(description="IR sensor test utility (Uno A0/A1 over serial)")
    parser.add_argument("--mode", choices=["serial", "gpio"], default="serial")
    parser.add_argument("--port", default="auto", help="Arduino serial port or 'auto'")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    args = parser.parse_args()

    print("=" * 50)
    print("IR Sensor Test - Arduino / Raspberry Pi")
    print("=" * 50)

    if args.mode == "serial":
        port = autodetect_serial_port() if args.port.lower() == "auto" else args.port
        if not port:
            print("[ERROR] No serial port found for Arduino IR stream")
            sys.exit(1)
        read_from_serial(port, duration=args.duration)
    else:
        read_from_gpio(duration=args.duration)


if __name__ == "__main__":
    main()
