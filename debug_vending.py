#!/usr/bin/env python3
"""
Debug script to check slot assignments and vending logic.
Run this to see what slots are assigned to items.
"""

import json

def load_assigned_items():
    """Load assigned items from JSON."""
    try:
        with open('assigned_items.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("ERROR: assigned_items.json not found")
        return None
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse assigned_items.json: {e}")
        return None

def analyze_slots():
    """Analyze slot assignments."""
    assigned = load_assigned_items()
    if not assigned:
        return
    
    print("=" * 70)
    print("SLOT ASSIGNMENT ANALYSIS")
    print("=" * 70)
    
    print(f"\nTotal assigned slots: {len(assigned)}\n")
    print(f"{'Slot':>5} | {'Item Name':>30} | {'Range':>10}")
    print("-" * 70)
    
    esp32_slots = []
    empty_slots = []
    
    for idx, slot in enumerate(assigned):
        slot_num = idx + 1
        
        if not slot:
            empty_slots.append(slot_num)
            print(f"{slot_num:>5} | {'[EMPTY]':>30} | {'1-48':>10}")
        elif isinstance(slot, dict):
            item_name = slot.get('name', '[UNKNOWN]')
            esp32_slots.append((slot_num, item_name))
            print(f"{slot_num:>5} | {item_name:>30} | {'ESP32 (1-48)':>10}")
        else:
            print(f"{slot_num:>5} | {'[INVALID]':>30} | {'?':>10}")
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"ESP32 slots (1-48):    {len(esp32_slots)} assigned")
    print(f"Empty slots:           {len(empty_slots)}")
    
    print("\n" + "=" * 70)
    print("VENDING TEST")
    print("=" * 70)
    
    print("\nTest vending an item from any assigned slot:")
    if esp32_slots:
        test_item = esp32_slots[0][1]
        print(f"  1. In the kiosk, select '{test_item}'")
        print(f"  2. Complete purchase")
        print(f"  3. Check logs for:")
        print(f"     - '[VEND] Pulse response'")
    else:
        print("\n⚠ Assign an item to a slot first, then test vending.")

if __name__ == '__main__':
    analyze_slots()
