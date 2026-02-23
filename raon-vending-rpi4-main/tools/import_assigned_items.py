"""
Import script: parse a product layout TXT and images folder to produce
`assigned_items.json` in the new per-term format used by `AssignItemsScreen`.

Usage:
    python tools/import_assigned_items.py --mapping "Product List Layout.txt" --images ./images --out assign_items.json

Assumptions:
- The mapping file uses headings like "Term 1", "Term 2", "Term 3".
- Rows are labelled "Row1", "Row2", ... and contain 8 items each (columns).
- Item lines look like: CODE - Name/Short - Description... - P123 or ₱123
- Image filenames should be named after the CODE (e.g. SS1.png) in the `images` folder.

If images are missing, the script leaves the `image` field empty.
"""
from __future__ import annotations
import argparse
import json
import os
import re
from typing import List, Dict, Optional

TERM_HEADING_RE = re.compile(r"^\s*Term\s*(\d+)", re.IGNORECASE)
ROW_HEADING_RE = re.compile(r"^\s*Row\s*(\d+)", re.IGNORECASE)

PRICE_RE = re.compile(r"[\d,.]+")


def parse_mapping_file(path: str, term_count: int = 3) -> List[List[List[str]]]:
    """Return terms -> rows -> list of raw item lines.

    Ensures there are `term_count` terms and 8 rows each. Missing entries become empty lists.
    """
    terms: List[List[List[str]]] = [[[] for _ in range(8)] for _ in range(term_count)]
    current_term = None
    current_row = None

    with open(path, encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if not line.strip():
                continue
            m = TERM_HEADING_RE.match(line)
            if m:
                n = int(m.group(1))
                if 1 <= n <= term_count:
                    current_term = n - 1
                    current_row = None
                else:
                    current_term = None
                continue
            m2 = ROW_HEADING_RE.match(line)
            if m2 and current_term is not None:
                r = int(m2.group(1))
                if 1 <= r <= 8:
                    current_row = r - 1
                else:
                    current_row = None
                continue
            # item line (indented or not)
            if current_term is None or current_row is None:
                continue
            item_line = line.strip()
            # ignore separators like dashes only
            if not item_line or set(item_line.strip()) == {'-'}:
                continue
            terms[current_term][current_row].append(item_line)
    return terms


def parse_item_line(line: str) -> Dict[str, Optional[str]]:
    # Try splitting by ' - ' segments (common in your file)
    parts = [p.strip() for p in line.split(' - ') if p.strip()]
    code = None
    name = None
    description = ''
    price = 0.0

    if len(parts) >= 3:
        code = parts[0]
        name = parts[1]
        # join middle parts except last as description
        description = ' - '.join(parts[2:-1]) if len(parts) > 3 else parts[2]
        last = parts[-1]
        m = PRICE_RE.search(last)
        if m:
            price_text = m.group(0).replace(',', '')
            try:
                price = float(price_text)
            except Exception:
                price = 0.0
    elif len(parts) == 2:
        code = parts[0]
        name = parts[1]
    elif len(parts) == 1:
        # maybe "CODE - Name: Desc" without separators; split by first colon
        s = parts[0]
        if ' - ' in line:
            left, right = line.split(' - ', 1)
            code = left.strip()
            name = right.strip()
        else:
            # fallback use entire line as name
            name = s

    if not code and name:
        # try to extract a short code like uppercase letters + digits at start
        m = re.match(r"^([A-Z0-9]{2,6})\b", name)
        if m:
            code = m.group(1)
    entry = {
        'code': code or '',
        'name': (f"{code} - {name}" if code and name else (name or code or '')),
        'category': '',
        'price': price,
        'quantity': 1,
        'image': '',
        'description': description or ''
    }
    return entry


def build_slots_from_terms(terms: List[List[List[str]]], images_dir: str) -> List[Dict]:
    # initialize empty wrapper per slot
    MAX_SLOTS = 8 * 8
    TERM_COUNT = len(terms)
    slots = [{'terms': [None] * TERM_COUNT} for _ in range(MAX_SLOTS)]

    for t_index, term in enumerate(terms):
        for row_index, row_items in enumerate(term):
            for col_index in range(8):
                slot_idx = row_index * 8 + col_index
                try:
                    raw_line = row_items[col_index]
                except Exception:
                    continue
                parsed = parse_item_line(raw_line)
                # guess image name by code
                code = parsed.get('code') or ''
                guess_files = [f"{code}.png", f"{code}.jpg", f"{code}.jpeg", f"{code}.gif", f"{code}.bmp"] if code else []
                img_path = ''
                for fn in guess_files:
                    candidate = os.path.join(images_dir, fn)
                    if os.path.exists(candidate):
                        # store relative path
                        img_path = os.path.relpath(candidate, os.path.dirname(os.path.abspath(__file__)))
                        break
                parsed['image'] = img_path
                slots[slot_idx]['terms'][t_index] = parsed
    return slots


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mapping', '-m', required=True, help='Mapping TXT file path')
    p.add_argument('--images', '-i', default='./images', help='Images folder')
    p.add_argument('--out', '-o', default=None, help='Output JSON (default: assigned_items.json next to mapping)')
    args = p.parse_args()

    mapping = args.mapping
    images = args.images
    out = args.out
    if not out:
        out = os.path.join(os.path.dirname(mapping), 'assigned_items.json')

    if not os.path.exists(mapping):
        print('Mapping file not found:', mapping)
        return

    terms = parse_mapping_file(mapping, term_count=3)
    slots = build_slots_from_terms(terms, images)

    with open(out, 'w', encoding='utf-8') as f:
        json.dump(slots, f, indent=2, ensure_ascii=False)

    print('Wrote', out)


if __name__ == '__main__':
    main()
