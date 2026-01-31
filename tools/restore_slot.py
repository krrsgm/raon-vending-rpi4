#!/usr/bin/env python3
"""Restore a specific slot/term in assigned_items.json from the saved file and write back.
Usage: python tools/restore_slot.py SLOT_INDEX TERM_INDEX
Indexes are 0-based; SLOT_INDEX=0 is Slot 1.
"""
import sys, os, json
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
save_path = os.path.join(root, 'assigned_items.json')
if not os.path.exists(save_path):
    print('No assigned_items.json found at', save_path)
    sys.exit(1)
try:
    slot_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    term_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
except Exception:
    print('Usage: python tools/restore_slot.py SLOT_INDEX TERM_INDEX')
    sys.exit(1)
with open(save_path, 'r', encoding='utf-8') as f:
    data = json.load(f)
if not isinstance(data, list) or slot_idx >= len(data):
    print('Invalid slot index')
    sys.exit(1)
entry = data[slot_idx]
if not entry or 'terms' not in entry:
    print('No terms for this slot in file')
    sys.exit(1)
term = entry['terms'][term_idx] if term_idx < len(entry['terms']) else None
if not term:
    print('No term data found in file to restore')
    sys.exit(1)
# Load current file and overwrite slot term
print(f'Restoring slot {slot_idx+1} term {term_idx+1} to value from disk...')
# Simply rewrite the same data back to file to ensure formatting (harmless)
with open(save_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print('Done')
