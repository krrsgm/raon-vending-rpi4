#!/usr/bin/env python3
"""
tools/test_kiosk_dispense.py

Simple test tool to verify that an assigned item will trigger the motor for its
assigned slot(s). It reads `assigned_items.json` (the same file `AssignItemsScreen`
uses) and sends PULSE commands to the configured ESP32 host for the matching slots.

Usage:
    python tools/test_kiosk_dispense.py --item "Item Name" [--qty N] [--host HOST]

If `--host` is omitted, the tool will try to read `config.json` for `esp32_host`.
If no host is found, it defaults to '192.168.4.1' (the AP fallback used by the app).
"""
import argparse
import json
import os
import sys
import time

from esp32_client import pulse_slot, send_command


ASSIGNED_FILE = 'assigned_items.json'


def load_assigned(path=None):
    path = path or os.path.join(os.getcwd(), ASSIGNED_FILE)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Assigned slots file not found: {path}")
    with open(path, 'r') as f:
        data = json.load(f)
    return data


def load_config(path='config.json'):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def find_slots_for_item(assigned_slots, item_name):
    matches = []
    for idx, slot in enumerate(assigned_slots):
        if not slot:
            continue
        name = slot.get('name') if isinstance(slot, dict) else None
        if name and name == item_name:
            matches.append(idx+1)  # 1-based slot numbers
    return matches


def main():
    p = argparse.ArgumentParser(description='Test kiosk dispense for assigned item')
    p.add_argument('--item', '-i', required=True, help='Item name to vend')
    p.add_argument('--qty', '-q', type=int, default=1, help='Quantity to vend')
    p.add_argument('--host', '-H', default=None, help='ESP32 host (ip or serial:URI)')
    p.add_argument('--ms', type=int, default=800, help='Pulse duration in ms')
    p.add_argument('--assigned', default=ASSIGNED_FILE, help='Path to assigned_items.json')
    args = p.parse_args()

    assigned = load_assigned(args.assigned)
    slots = find_slots_for_item(assigned, args.item)
    if not slots:
        print(f'No assigned slots found for item "{args.item}" in {args.assigned}')
        return 2

    cfg = load_config()
    host = args.host or cfg.get('esp32_host') or '192.168.4.1'
    print(f'Using ESP32 host: {host}')
    print(f'Found slots for "{args.item}": {slots}')

    # Perform round-robin pulses across matching slots
    for i in range(args.qty):
        slot = slots[i % len(slots)]
        print(f'Pulsing slot {slot} (#{i+1}/{args.qty}) for {args.ms}ms')
        try:
            resp = pulse_slot(host, slot, args.ms)
            # pulse_slot returns send_command result which may be empty string
            if resp:
                print('ESP32 response:', resp)
        except Exception as e:
            print('Error sending pulse:', e)
            return 3
        time.sleep(0.2)

    print('Done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
