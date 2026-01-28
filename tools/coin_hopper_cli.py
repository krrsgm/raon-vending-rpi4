#!/usr/bin/env python3
"""
tools/coin_hopper_cli.py

Simple CLI to test and exercise the `CoinHopper` class in the repository.

Usage:
    python tools/coin_hopper_cli.py <amount> [--one-pin P] [--five-pin P]

Examples:
    python tools/coin_hopper_cli.py 18 --one-pin 17 --five-pin 27 --one-sensor 22 --five-sensor 23

The script constructs `CoinHopper` with the provided GPIO pins and attempts
to dispense change using the minimal coin combination (5-peso then 1-peso).
It prints progress updates and returns non-zero on error.
"""
import argparse
import sys
import time

from coin_hopper import CoinHopper


def main():
    p = argparse.ArgumentParser(description="Test coin hopper dispensing")
    p.add_argument('amount', type=int, help='Amount of change to dispense (pesos)')
    p.add_argument('--one-pin', type=int, default=5, help='GPIO pin for 1-peso hopper motor')
    p.add_argument('--five-pin', type=int, default=6, help='GPIO pin for 5-peso hopper motor')
    p.add_argument('--one-sensor', type=int, default=6, help='GPIO pin for 1-peso sensor')
    p.add_argument('--five-sensor', type=int, default=5, help='GPIO pin for 5-peso sensor')
    p.add_argument('--timeout', type=int, default=30, help='Timeout per coin type in seconds')
    args = p.parse_args()

    amount = args.amount
    print(f"Dispensing change: {amount} peso(s)")

    hopper = None
    try:
        hopper = CoinHopper(args.one_pin, args.five_pin, args.one_sensor, args.five_sensor)
        # Wrap callback to prefix timestamps
        def cb(msg):
            ts = time.strftime('%H:%M:%S')
            print(f"[{ts}] {msg}")

        success, dispensed, msg = hopper.dispense_change(amount, callback=cb)
        if success:
            print(f"SUCCESS: dispensed {dispensed} peso(s) — {msg}")
            return 0
        else:
            print(f"ERROR: dispensed {dispensed} peso(s) — {msg}")
            return 2

    except Exception as e:
        print(f"Fatal error while dispensing change: {e}")
        return 3
    finally:
        try:
            if hopper:
                hopper.cleanup()
        except Exception:
            pass


if __name__ == '__main__':
    sys.exit(main())
