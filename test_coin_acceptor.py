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


def run_serial_mode(port: str, baud: int):
    from coin_handler_esp32 import CoinAcceptorESP32

    selected_port = None if port.lower() == "auto" else port
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


def main():
    parser = argparse.ArgumentParser(description="Coin acceptor test utility")
    parser.add_argument(
        "--mode",
        choices=["serial", "gpio"],
        default="serial",
        help="Input mode: 'serial' (Arduino Uno USB) or 'gpio' (Raspberry Pi GPIO)",
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
    else:
        run_gpio_mode(args.gpio_pin)


if __name__ == "__main__":
    main()
