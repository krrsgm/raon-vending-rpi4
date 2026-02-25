#!/usr/bin/env python3
"""
IR Sensor Test - compatible with ESP32 or Raspberry Pi

Behavior:
- If an ESP32 is detected via serial (auto-detect), the script reads lines
  from the ESP32 and parses IR sensor states printed by the ESP32 firmware.
- Otherwise it falls back to direct GPIO reads on Raspberry Pi pins.

ESP32 output format expected (examples):
  IR1 (GPIO34): BLOCKED
  IR2 (GPIO35): CLEAR
"""

import time
import sys
import re

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
    # allow running on non-RPi machines
    try:
        from rpi_gpio_mock import GPIO as GPIO
        GPIO_AVAILABLE = True
    except Exception:
        GPIO_AVAILABLE = False

# Raspberry Pi sensor pins (legacy)
SENSOR_1_PIN = 24
SENSOR_2_PIN = 25

# ESP32 pins (for reference)
ESP32_IR1_LABEL = "IR1"
ESP32_IR2_LABEL = "IR2"


def autodetect_esp32_port():
    if not SERIAL_AVAILABLE:
        return None
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        mfg = (p.manufacturer or "").lower()
        if any(k in desc or k in mfg for k in ("esp32", "arduino", "cp210", "ch340", "silicon labs")):
            return p.device
    return ports[0].device if ports else None


def read_from_esp32(port, duration=30):
    """Read IR status lines from ESP32 serial and print a simple table."""
    try:
        ser = serial.Serial(port, 115200, timeout=1)
    except Exception as e:
        print(f"[ERROR] Could not open serial port {port}: {e}")
        return

    print(f"✓ Reading IR sensor states from ESP32 on {port} for {duration}s")
    print(f"{'Time (s)':>8} | {'IR1 (GPIO34)':>15} | {'IR2 (GPIO35)':>15}")
    print('-' * 48)

    start = time.time()
    ir1 = None
    ir2 = None
    pattern1 = re.compile(r"IR1.*?:\s*(BLOCKED|CLEAR)", re.IGNORECASE)
    pattern2 = re.compile(r"IR2.*?:\s*(BLOCKED|CLEAR)", re.IGNORECASE)

    try:
        while time.time() - start < duration:
            line = ser.readline().decode(errors='ignore').strip()
            if not line:
                continue
            t = time.time() - start
            m1 = pattern1.search(line)
            m2 = pattern2.search(line)
            if m1:
                ir1 = m1.group(1).upper()
            if m2:
                ir2 = m2.group(1).upper()

            # Print current snapshot whenever we get a line containing IR info
            if m1 or m2:
                s1 = ir1 if ir1 is not None else "--"
                s2 = ir2 if ir2 is not None else "--"
                print(f"{t:8.1f} | {s1:>15} | {s2:>15}")

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    finally:
        try:
            ser.close()
        except:
            pass


def read_from_gpio(duration=30, interval=0.5):
    if not GPIO_AVAILABLE:
        print("[ERROR] GPIO not available on this system")
        return

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SENSOR_1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(SENSOR_2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    except Exception as e:
        print(f"[ERROR] Failed to initialize GPIO: {e}")
        return

    print(f"✓ GPIO initialized (GPIO_AVAILABLE={GPIO_AVAILABLE})")
    print(f"Reading IR sensors on GPIO {SENSOR_1_PIN} and {SENSOR_2_PIN} for {duration}s")
    print(f"{'Time (s)':>8} | {'Sensor 1':>18} | {'Sensor 2':>18}")
    print('-' * 54)

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
            print("\n✓ GPIO cleaned up")
        except Exception as e:
            print(f"\n[WARNING] Error during cleanup: {e}")


def main():
    print("=" * 50)
    print("IR Sensor Test - ESP32 / Raspberry Pi Compatible")
    print("=" * 50)

    # Prefer ESP32 serial if available
    port = autodetect_esp32_port() if SERIAL_AVAILABLE else None
    if port:
        read_from_esp32(port, duration=30)
    else:
        read_from_gpio(duration=30)


if __name__ == "__main__":
    main()
