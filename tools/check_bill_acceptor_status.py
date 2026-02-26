#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from payment_handler import PaymentHandler


def main():
    parser = argparse.ArgumentParser(description="Check bill acceptor status (Arduino serial)")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Bill acceptor serial port")
    parser.add_argument("--baud", type=int, default=115200, help="Bill acceptor baud rate")
    args = parser.parse_args()

    config = {}
    ph = PaymentHandler(
        config,
        coin_port=args.port,
        coin_baud=args.baud,
        bill_port=args.port,
        bill_baud=args.baud,
        bill_esp32_mode=False,
        use_gpio_coin=False,
        coin_hopper_port=args.port,
        coin_hopper_baud=args.baud,
    )

    ba = ph.bill_acceptor
    if not ba:
        print("PaymentHandler.bill_acceptor is None (not connected)")
    else:
        print("PaymentHandler.bill_acceptor object exists")
        ser = getattr(ba, "serial_conn", None)
        print("serial_conn:", ser)
        try:
            print("received_amount:", ba.get_received_amount())
        except Exception as e:
            print("Error reading received_amount:", e)
    ph.cleanup()


if __name__ == "__main__":
    main()
