"""Coin hopper tester CLI (replaces old interactive test script)

This tool provides two simple modes to validate coin hopper relay behavior
and dispensing commands:

- relay: toggles `COIN_OPEN` / `COIN_CLOSE` for a denomination to exercise the relay
- dispense: issues `DISPENSE_DENOM` and reports the result

It supports `--simulate` for dry runs without hardware, and auto-detects USB
serial ports when `--port` is not provided.
"""

import argparse
import time
import sys
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
        resp = hopper.send_command(f"COIN_OPEN {denom}")
        print("  ->", resp)
        time.sleep(interval)
        status = hopper.get_status()
        print("  status:", status)

        print(f"[{i+1}/{count}] Closing hopper for {denom}-peso")
        resp2 = hopper.send_command(f"COIN_CLOSE {denom}")
        print("  ->", resp2)
        time.sleep(interval)
        status2 = hopper.get_status()
        print("  status:", status2)


def dispense_test(hopper: CoinHopper, denom: int, count: int, interval: float):
    """Request DISPENSE_DENOM and poll status."""
    print(f"Requesting {count} coin(s) of {denom}-peso using DISPENSE_DENOM")
    success, dispensed, msg = hopper.dispense_coins(denom, count, timeout_ms=15000)
    print("Result:", success, dispensed, msg)
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
        hopper.disconnect()


if __name__ == '__main__':
    main()
