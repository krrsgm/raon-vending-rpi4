#!/usr/bin/env python3
"""
Coin acceptor test utility.

Default mode is Arduino Uno serial (USB), since coin input is handled by
ArduinoUno_Bill_Forward.ino in this project.

Usage examples:
  python3 test_coin_acceptor.py
  python3 test_coin_acceptor.py --mode serial --port /dev/ttyACM0
  python3 test_coin_acceptor.py --mode gpio --gpio-pin 17
"""

import argparse
import time
import re


def _autodetect_port():
    try:
        import serial.tools.list_ports
    except Exception:
        return None
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        mfg = (p.manufacturer or "").lower()
        if any(k in desc or k in mfg for k in ("arduino", "ch340", "cp210", "usb serial", "silicon labs")):
            return p.device
    return ports[0].device if ports else None


def _resolve_port(port: str):
    return _autodetect_port() if port.lower() == "auto" else port


def run_serial_mode(port: str, baud: int):
    from coin_handler_esp32 import CoinAcceptorESP32

    selected_port = _resolve_port(port)
    coin = CoinAcceptorESP32(port=selected_port, baudrate=baud)
    print(f"[TEST] Serial mode started (port={port}, baud={baud})")
    print("[TEST] Insert coins. Press Ctrl+C to stop.")

    last = -1.0
    try:
        while True:
            total = float(coin.get_received_amount() or 0.0)
            if total != last:
                print(f"[COIN] Total received: PHP {total:.2f}")
                last = total
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[TEST] Stopping serial coin test...")
    finally:
        coin.cleanup()


def run_gpio_mode(gpio_pin: int):
    try:
        import RPi.GPIO as GPIO
    except Exception:
        GPIO = None

    from coin_handler import CoinAcceptor

    coin = CoinAcceptor(coin_pin=gpio_pin)
    print(f"[TEST] GPIO mode started (GPIO={gpio_pin})")
    print("[TEST] Insert coins. Press Ctrl+C to stop.")

    last = -1.0
    try:
        while True:
            total = float(coin.get_received_amount() or 0.0)
            if total != last:
                print(f"[COIN] Total received: PHP {total:.2f}")
                last = total
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[TEST] Stopping GPIO coin test...")
    finally:
        coin.cleanup()
        if GPIO is not None:
            try:
                GPIO.cleanup()
            except Exception:
                pass


def run_serial_debug_mode(port: str, baud: int):
    import serial

    selected_port = _resolve_port(port)
    if not selected_port:
        print("[DEBUG] No serial port found")
        return

    coin_line = re.compile(r"\[COIN\].*", re.IGNORECASE)
    balance_line = re.compile(r"BALANCE:\s*([-\d.]+)", re.IGNORECASE)
    bill_line = re.compile(r"BILL\s+INSERTED.*", re.IGNORECASE)

    print(f"[DEBUG] Serial debug mode started (port={selected_port}, baud={baud})")
    print("[DEBUG] Reading raw Arduino lines + polling GET_BALANCE every 1s. Ctrl+C to stop.")

    last_poll = 0.0
    try:
        with serial.Serial(selected_port, baudrate=baud, timeout=0.2) as ser:
            while True:
                now = time.time()
                if now - last_poll >= 1.0:
                    ser.write(b"GET_BALANCE\n")
                    ser.flush()
                    last_poll = now

                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue

                ts = time.strftime("%H:%M:%S")
                if coin_line.search(line):
                    print(f"[{ts}] [COIN_EVENT] {line}")
                elif balance_line.search(line):
                    print(f"[{ts}] [BALANCE] {line}")
                elif bill_line.search(line):
                    print(f"[{ts}] [BILL] {line}")
                else:
                    print(f"[{ts}] [RAW] {line}")
    except KeyboardInterrupt:
        print("\n[DEBUG] Stopping serial debug test...")


def main():
    parser = argparse.ArgumentParser(description="Coin acceptor test utility")
    parser.add_argument(
        "--mode",
        choices=["serial", "serial-debug", "gpio"],
        default="serial",
        help="Input mode: 'serial', 'serial-debug', or 'gpio'",
    )
    parser.add_argument(
        "--port",
        default="/dev/ttyACM0",
        help="Serial port for Arduino Uno coin stream (use 'auto' to auto-detect)",
    )
    parser.add_argument("--baud", type=int, default=115200, help="Serial baud rate")
    parser.add_argument("--gpio-pin", type=int, default=17, help="GPIO pin for gpio mode")
    args = parser.parse_args()

    if args.mode == "serial":
        run_serial_mode(args.port, args.baud)
    elif args.mode == "serial-debug":
        run_serial_debug_mode(args.port, args.baud)
    else:
        run_gpio_mode(args.gpio_pin)


if __name__ == "__main__":
    main()
