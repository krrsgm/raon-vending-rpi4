#!/usr/bin/env python3
"""Simple CLI tool to test coin hopper relay and dispense commands.

Usage examples:
  python tools/coin_hopper_tester.py --port COM3 --denom 1 --count 3 --mode relay
  python tools/coin_hopper_tester.py --port /dev/ttyUSB0 --denom 5 --count 2 --mode dispense

Features:
- Connects to `CoinHopper` controller in this repo
- Supports 'relay' mode: toggles COIN_OPEN/COIN_CLOSE for a denomination to exercise the hopper relay
- Supports 'dispense' mode: sends DISPENSE_DENOM to request specific coins
- Can poll COIN_STATUS between operations to verify state
- Has a `--simulate` option to run without hardware
"""
import argparse
import time
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from coin_hopper import CoinHopper


def parse_args():
    p = argparse.ArgumentParser(description="Coin hopper tester: toggle relays or request coin dispense")
    p.add_argument("--port", default=None, help="Serial port for coin hopper (e.g. COM3 or /dev/ttyUSB0)")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--denom", type=int, choices=[1,5], default=1, help="Coin denomination to test")
    p.add_argument("--count", type=int, default=1, help="Number of coins or relay pulses to test")
    p.add_argument("--mode", choices=["relay","dispense"], default="relay", help="Test mode: 'relay' toggles hopper open/close; 'dispense' requests dispensing")
    p.add_argument("--interval", type=float, default=0.6, help="Seconds between relay on/off cycles or between dispense requests")
    p.add_argument("--simulate", action="store_true", help="Run in simulation mode (no serial) to validate logic)")
    p.add_argument("--stay-open", action="store_true", help="Keep serial connection open after test (for manual monitoring)")
    return p.parse_args()


def simulate_cycle(denom, count, interval):
    print(f"[SIM] Simulating {count} cycles for {denom}-peso hopper with {interval}s interval")
    for i in range(count):
        print(f"[SIM] Cycle {i+1}: OPEN {denom}")
        time.sleep(interval)
        print(f"[SIM] Cycle {i+1}: CLOSE {denom}")
        time.sleep(interval)
    print("[SIM] Done")


def relay_test(hopper: CoinHopper, denom: int, count: int, interval: float):
    """Toggle hopper open/close for specified denom and verify status."""
    for i in range(count):
        print(f"[{i+1}/{count}] Opening hopper for {denom}-peso")
        resp = hopper.send_command(f"OPEN {denom}")
        print("  ->", resp)
        time.sleep(interval)
        status = hopper.get_status()
        print("  status:", status)

        print(f"[{i+1}/{count}] Closing hopper for {denom}-peso")
        resp2 = hopper.send_command(f"CLOSE {denom}")
        print("  ->", resp2)
        time.sleep(interval)
        status2 = hopper.get_status()
        print("  status:", status2)


def dispense_test(hopper: CoinHopper, denom: int, count: int, interval: float):
    """Request DISPENSE_DENOM and poll status."""
    pulse_one = 0
    pulse_five = 0

    def on_hopper(msg: str):
        nonlocal pulse_one, pulse_five
        print("  [HOPPER]", msg)
        u = (msg or "").upper()
        m1 = re.search(r'PULSE\s+ONE\s+(\d+)', u)
        m5 = re.search(r'PULSE\s+FIVE\s+(\d+)', u)
        if m1:
            pulse_one = max(pulse_one, int(m1.group(1)))
        if m5:
            pulse_five = max(pulse_five, int(m5.group(1)))

    print(f"Requesting {count} coin(s) of {denom}-peso using DISPENSE_DENOM")
    success, dispensed, msg = hopper.dispense_coins(denom, count, timeout_ms=15000, callback=on_hopper)
    print("Result:", success, dispensed, msg)
    print(f"Sensor pulses seen (pin11=ONE, pin12=FIVE): pin11={pulse_one}, pin12={pulse_five}")
    # Give hardware a moment then poll status
    time.sleep(interval)
    print("COIN_STATUS ->", hopper.get_status())


def main():
    args = parse_args()

    if args.simulate:
        simulate_cycle(args.denom, args.count, args.interval)
        return

    # Create coin hopper instance
    port = args.port
    if not port:
        print("No port specified. Attempting auto-detect...")
    hopper = CoinHopper(serial_port=port or '', baudrate=args.baud, auto_detect=True)
    if not hopper.connect():
        print("Failed to connect to coin hopper. Use --simulate to run without hardware.")
        return

    try:
        if args.mode == 'relay':
            relay_test(hopper, args.denom, args.count, args.interval)
        else:
            dispense_test(hopper, args.denom, args.count, args.interval)
    finally:
        if args.stay_open:
            print("Leaving serial connection open (--stay-open). Press Ctrl+C to exit.")
            try:
                while True:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                pass
        hopper.disconnect()


if __name__ == '__main__':
    main()
