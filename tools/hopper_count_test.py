"""
Test script to count coins by running a hopper until coins stop (idle 2s).
It reads the coin sensor total, drives the hopper relay, and optionally
updates coin_change_stock in config.json.

Usage:
    python tools/hopper_count_test.py --denom 1
    python tools/hopper_count_test.py --denom 5 --update
"""

import argparse
import json
import os
import time
import platform

from arduino_serial_utils import detect_arduino_serial_port
from coin_hopper import CoinHopper
from dht22_handler import get_shared_serial_reader
from fix_paths import get_absolute_path

IDLE_TIMEOUT_SEC = 2.0
POLL_INTERVAL_SEC = 0.2


def load_config():
    path = get_absolute_path("config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f), path


def choose_ports(cfg):
    hw = cfg.get("hardware", {}) if isinstance(cfg, dict) else {}
    hopper_port = (
        hw.get("coin_hopper", {}).get("serial_port")
        or hw.get("bill_acceptor", {}).get("serial_port")
        or hw.get("coin_acceptor", {}).get("serial_port")
    )
    reader_port = (
        hw.get("coin_acceptor", {}).get("serial_port")
        or hw.get("bill_acceptor", {}).get("serial_port")
        or hopper_port
    )
    # On Windows, ignore /dev paths if present
    if platform.system() != "Linux":
        if hopper_port and hopper_port.startswith("/dev/"):
            hopper_port = None
        if reader_port and reader_port.startswith("/dev/"):
            reader_port = None
    if not hopper_port:
        hopper_port = detect_arduino_serial_port()
    if not reader_port:
        reader_port = detect_arduino_serial_port()
    return hopper_port, reader_port


def ensure_reader(port, baud=115200):
    try:
        return get_shared_serial_reader(port, baud)
    except Exception as e:
        print(f"[hopper-count] Failed to start reader on {port}: {e}")
        return None


def ensure_hopper(port, baud=115200):
    try:
        hopper = CoinHopper(serial_port=port, baudrate=baud)
        if hopper.connect():
            return hopper
        print(f"[hopper-count] Hopper connect failed on {port}")
    except Exception as e:
        print(f"[hopper-count] Hopper error on {port}: {e}")
    return None


def count_coins(denom, reader, hopper):
    # Turn relays on and open hopper
    try:
        hopper.ensure_relays_off()
        hopper.send_command("RELAY_ON")
    except Exception:
        pass
    if not hopper.open_hopper(denom):
        raise RuntimeError("Failed to open hopper")

    try:
        last_total = float(reader.get_coin_total() or 0.0)
    except Exception:
        last_total = 0.0
    start_total = last_total
    last_coin_ts = time.time()
    total_count = 0

    while True:
        time.sleep(POLL_INTERVAL_SEC)
        try:
            total = float(reader.get_coin_total() or last_total)
        except Exception:
            total = last_total
        delta = total - last_total
        last_total = total
        if delta > 0:
            coins = int(round(delta / float(denom)))
            if coins > 0:
                total_count += coins
                last_coin_ts = time.time()
                print(f"[hopper-count] +{coins} (total {total_count})")
        if (time.time() - last_coin_ts) >= IDLE_TIMEOUT_SEC:
            break
    # Close hopper/relays
    try:
        hopper.close_hopper(denom)
        hopper.ensure_relays_off()
    except Exception:
        pass
    return total_count, last_total - start_total


def update_config(cfg_path, cfg, denom, count):
    coin_cfg = cfg.setdefault("coin_change_stock", {})
    key = "one_peso" if denom == 1 else "five_peso"
    entry = coin_cfg.setdefault(key, {})
    entry["count"] = max(0, int(count))
    entry.setdefault("low_threshold", 20)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)
    print(f"[hopper-count] Updated config coin_change_stock.{key}.count = {count}")


def main():
    parser = argparse.ArgumentParser(description="Count hopper coins via coin sensor.")
    parser.add_argument("--denom", type=int, choices=[1, 5], required=True, help="Denomination to count (1 or 5)")
    parser.add_argument(
        "--no-update",
        action="store_true",
        help="Do not write the counted value into config (default is to update coin_change_stock)",
    )
    args = parser.parse_args()

    cfg, cfg_path = load_config()
    hopper_port, reader_port = choose_ports(cfg)
    print(f"[hopper-count] reader={reader_port} hopper={hopper_port}")

    reader = ensure_reader(reader_port)
    if not reader or not getattr(reader, "connected", False):
        raise SystemExit("Coin sensor reader not connected.")
    hopper = ensure_hopper(hopper_port)
    if not hopper:
        raise SystemExit("Hopper not connected.")

    try:
        count, _ = count_coins(args.denom, reader, hopper)
        print(f"[hopper-count] Counted {count} coin(s) of P{args.denom}")
        if not args.no_update:
            update_config(cfg_path, cfg, args.denom, count)
    finally:
        try:
            hopper.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
