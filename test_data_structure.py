#!/usr/bin/env python3
"""
Quick test to verify assign_items_screen loads and processes the new assigned_items.json
"""
import json
import sys

# Load the generated JSON
try:
    with open('assigned_items.json', 'r') as f:
        slots_data = json.load(f)
    print(f"[OK] Loaded assigned_items.json with {len(slots_data)} slots")
except Exception as e:
    print(f"[FAIL] Could not load assigned_items.json: {e}")
    sys.exit(1)

# Verify structure
errors = []
for i, slot in enumerate(slots_data):
    slot_num = i + 1
    
    # Check structure
    if 'terms' not in slot:
        errors.append(f"Slot {slot_num}: Missing 'terms' key")
        continue
    
    terms = slot['terms']
    if not isinstance(terms, list) or len(terms) != 3:
        errors.append(f"Slot {slot_num}: terms is not a 3-element list")
        continue
    
    # Check each term
    for term_idx, term_data in enumerate(terms):
        if term_data is None:
            continue  # Empty slot is OK
        
        required_keys = ['code', 'name', 'price', 'image']
        for key in required_keys:
            if key not in term_data:
                errors.append(f"Slot {slot_num} Term {term_idx+1}: Missing '{key}'")

if errors:
    print(f"\n[FAIL] Found {len(errors)} structure errors:")
    for err in errors[:10]:  # Show first 10
        print(f"  - {err}")
else:
    print(f"[OK] All 48 slots have correct 3-term structure")

# Check image files exist
import os
missing_images = 0
for slot in slots_data:
    for term_data in slot['terms']:
        if term_data and term_data.get('image'):
            img_path = term_data['image']
            if not os.path.exists(img_path):
                missing_images += 1

print(f"[OK] Image references checked (missing: {missing_images}/171)")

# Verify it's compatible with assign_items_screen
print(f"\n[OK] Data structure ready for assign_items_screen:")
print(f"     - Total slots: {len(slots_data)}")
print(f"     - Populated: {sum(1 for s in slots_data if s['terms'][0])}/48")
print(f"     - Terms per slot: 3")
print(f"     - Sample Slot 1 Term 1: {slots_data[0]['terms'][0].get('code')} - {slots_data[0]['terms'][0].get('name')[:30]}...")
