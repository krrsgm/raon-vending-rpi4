#!/usr/bin/env python3
"""
tools/auto_change_dispenser.py

Usage:
    python tools/auto_change_dispenser.py <required_amount>

Starts a payment session for the specified required amount (pesos).
Listens for coin and bill events via existing `PaymentHandler` and when the
collected amount reaches or exceeds the required amount it stops the session
and dispenses change using the configured coin hoppers (1-peso and 5-peso).

This tool is intended to run on the Raspberry Pi where GPIO and serial
connections are available.
"""
import time
import json
import sys
import signal

from payment_handler import PaymentHandler


def load_config(path='config.json'):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    if len(sys.argv) < 2:
        print('Usage: python tools/auto_change_dispenser.py <required_amount>')
        return 2

    required_amount = float(sys.argv[1])
    config = load_config()

    # Instantiate PaymentHandler using config values where helpful
    ph = PaymentHandler(config)

    stop_flag = {'stop': False}

    def signal_handler(sig, frame):
        print('Interrupted, stopping session...')
        stop_flag['stop'] = True

    signal.signal(signal.SIGINT, signal_handler)

    # Callback from PaymentHandler to receive live updates
    def on_payment_update(amount):
        print(f'Payment update: received = ₱{amount:.2f} (required ₱{required_amount:.2f})')
        if amount >= required_amount:
            print('Required amount reached; finalizing payment...')
            stop_flag['stop'] = True

    ph.start_payment_session(required_amount=required_amount, on_payment_update=on_payment_update)
    print(f'Started payment session; waiting for ₱{required_amount:.2f}...')

    # Wait for stop flag (either enough money or Ctrl-C)
    try:
        while not stop_flag['stop']:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass

    print('Stopping payment session and dispensing change if needed...')
    total_received, change_amount, change_status = ph.stop_payment_session(required_amount=required_amount)
    print(f'Total received: ₱{total_received:.2f}')
    print(f'Change dispensed: ₱{change_amount} — {change_status}')

    ph.cleanup()
    return 0


if __name__ == '__main__':
    sys.exit(main())
