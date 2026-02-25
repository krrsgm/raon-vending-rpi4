import re
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
LAYOUT = BASE / 'Product List Layout.txt'
OUT = BASE / 'assigned_items.json'
MAX_SLOTS = 48
TERM_COUNT = 3

if not LAYOUT.exists():
    print('Layout file not found:', LAYOUT)
    raise SystemExit(1)

text = LAYOUT.read_text(encoding='utf-8')
lines = [l.strip() for l in text.splitlines() if l.strip()]

# Find term sections
term_indices = {}
for i, line in enumerate(lines):
    m = re.match(r'^Term\s*(\d+)', line, re.IGNORECASE)
    if m:
        term_indices[int(m.group(1))] = i

# Append EOF index
sorted_terms = sorted(term_indices.items())
term_ranges = {}
for idx, (term_num, start_i) in enumerate(sorted_terms):
    if idx+1 < len(sorted_terms):
        end_i = sorted_terms[idx+1][1]
    else:
        end_i = len(lines)
    term_ranges[term_num] = (start_i+1, end_i)

# Initialize slots
slots = [{'terms':[None]*TERM_COUNT} for _ in range(MAX_SLOTS)]

slot_re = re.compile(r'Slot\s*(\d+):\s*(.+)', re.IGNORECASE)
price_re = re.compile(r'[₱P\s]*([0-9]+(?:\.[0-9]+)?)')

for term_num, (si, ei) in term_ranges.items():
    term_idx = term_num - 1
    for line in lines[si:ei]:
        m = slot_re.match(line)
        if not m:
            continue
        slot_no = int(m.group(1))
        if slot_no < 1 or slot_no > MAX_SLOTS:
            continue
        rest = m.group(2).strip()
        # Try to split price from end
        price = None
        price_match = re.search(r'(?:-|–)\s*[₱P]?\s*([0-9]+(?:\.[0-9]+)?)\s*$', rest)
        if price_match:
            price = float(price_match.group(1))
            rest = rest[:price_match.start()].strip()
        else:
            # Look for trailing P### or ₱###
            pm = re.search(r'[₱P]\s*([0-9]+(?:\.[0-9]+)?)', rest)
            if pm:
                price = float(pm.group(1))
                rest = rest[:pm.start()].strip()

        # Split code (first token before '-') and name
        parts = [p.strip() for p in re.split(r'\s-\s|:\s', rest) if p.strip()]
        code = parts[0].split()[0] if parts else ''
        name = rest
        category = None
        if len(parts) >= 2:
            name = parts[0] + ' - ' + ' - '.join(parts[1:])
        # Build item dict
        item = {
            'code': code or None,
            'name': name,
            'category': category or None,
            'price': price if price is not None else 0.0,
            'quantity': 1,
            'image': f"images/{code}.png" if code else None,
            'description': f"P{price}" if price is not None else ''
        }
        slots[slot_no-1]['terms'][term_idx] = item

# Write output
with OUT.open('w', encoding='utf-8') as f:
    json.dump(slots, f, indent=2, ensure_ascii=False)
print('Wrote', OUT)
