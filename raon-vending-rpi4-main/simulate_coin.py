"""Small helper to simulate coin pulses for testing (uses the mock GPIO).

Usage (from project root):
    python src/simulate_coin.py --pin 17 --count 3 --delay 0.2

This will trigger the registered callback for `pin` 3 times with 0.2s delay.
"""
import argparse
import time
import sys

sys.path.insert(0, '')  # ensure project root is on path so rpi_gpio_mock can be imported
try:
    import rpi_gpio_mock as gpio_mock
except Exception:
    print("rpi_gpio_mock not available. This helper is useful when running on desktop for testing.")
    raise


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--pin', type=int, default=17)
    p.add_argument('--count', type=int, default=1)
    p.add_argument('--delay', type=float, default=0.1)
    args = p.parse_args()

    for i in range(args.count):
        print(f"Simulating pulse {i+1}/{args.count} on pin {args.pin}")
        gpio_mock.simulate_pulse(args.pin)
        time.sleep(args.delay)


if __name__ == '__main__':
    main()
