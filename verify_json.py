import json

data = json.load(open('assigned_items.json'))

print(f'Total slots: {len(data)}')
print()

# Check Slot 1
slot1_terms = data[0]['terms']
print(f'Slot 1 structure:')
print(f'  - Term count: {len(slot1_terms)}')
print(f'  - Term 1 Code: {slot1_terms[0]["code"]}')
print(f'  - Term 2 Code: {slot1_terms[1]["code"]}')
print(f'  - Term 3 Code: {slot1_terms[2]["code"]}')
print()

# Check image paths
print(f'Sample image paths (Term 1):')
for i in [0, 8, 16, 32, 47]:
    slot_num = i + 1
    term_data = data[i]['terms'][0]
    if term_data:
        img = term_data.get('image', 'NO IMAGE')
        code = term_data.get('code', 'EMPTY')
        print(f'  Slot {slot_num:2d}: {code:10s} -> {img}')
    else:
        print(f'  Slot {slot_num:2d}: (EMPTY)')
print()

# Count populated slots
populated = 0
for slot in data:
    if slot['terms'][0]:
        populated += 1
print(f'Populated slots (Term 1): {populated}/48')
