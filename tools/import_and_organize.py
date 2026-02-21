"""
Updated import script: parse explicit Slot N: format from Product List Layout.txt
and generate per-term assigned_items.json with correct slot positioning.

This script handles:
- Explicit slot numbering (Slot 1, Slot 17, etc.)
- Per-term, per-row layout
- Image mapping by product code
- Correct slot positioning in 64-slot grid

Usage:
    python tools/import_and_organize.py --mapping "Product List Layout.txt" --product-list "./Product List"
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
from typing import List, Dict, Optional, Tuple

TERM_HEADING_RE = re.compile(r"^\s*Term\s*(\d+)", re.IGNORECASE)
ROW_HEADING_RE = re.compile(r"^\s*Row\s*(\d+)", re.IGNORECASE)
SLOT_RE = re.compile(r"Slot\s*(\d+)\s*:", re.IGNORECASE)
PRICE_RE = re.compile(r"[\d,.]+")


def ensure_images_dir(images_dir: str) -> None:
    """Create images directory if it doesn't exist."""
    os.makedirs(images_dir, exist_ok=True)


def copy_images_from_product_list(product_list_dir: str, images_dir: str, slot_data: Dict[int, list]) -> None:
    """Copy images from Product List/Term*/Row*/ to flat images/ folder."""
    ensure_images_dir(images_dir)
    
    for slot_num, terms_list in slot_data.items():
        # terms_list is [term0_item, term1_item, term2_item]
        for item_dict in terms_list:
            if not item_dict or not item_dict.get('code'):
                continue
            
            code = item_dict['code']
            
            # Try to find image in Product List folders
            for term_folder_name in ["Term 1", "Term 2", "Term 3"]:
                term_folder = os.path.join(product_list_dir, term_folder_name)
                if not os.path.isdir(term_folder):
                    continue
                
                for row_folder_name in [f"Row {r+1}" for r in range(8)]:
                    row_folder = os.path.join(term_folder, row_folder_name)
                    if not os.path.isdir(row_folder):
                        continue
                    
                    # Look for image files in this folder
                    try:
                        images_in_row = [f for f in os.listdir(row_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
                    except Exception:
                        continue
                    
                    for img_file in images_in_row:
                        src = os.path.join(row_folder, img_file)
                        ext = os.path.splitext(img_file)[1]
                        dst_name = f"{code}{ext}"
                        dst = os.path.join(images_dir, dst_name)
                        
                        # Copy if not already there
                        if not os.path.exists(dst):
                            try:
                                shutil.copy2(src, dst)
                                print(f"Copied {src} -> {dst}")
                                break  # Found and copied
                            except Exception as e:
                                print(f"Error copying {src}: {e}")
                    else:
                        continue
                    break


def parse_mapping_file(path: str, term_count: int = 3) -> Dict[int, Dict[str, Optional[Dict]]]:
    """
    Parse explicit Slot N: format.
    Returns: dict of slot_idx -> {term_idx -> item_data}
    """
    slot_to_terms = {}  # slot_idx -> [term0_data, term1_data, term2_data]
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
            
            # Look for "Slot N:" pattern
            if current_term is None or current_row is None:
                continue
            
            slot_match = SLOT_RE.search(line)
            if not slot_match:
                continue
            
            slot_num = int(slot_match.group(1))
            if not (1 <= slot_num <= 64):
                continue
            
            # Extract item data after "Slot N:"
            item_line = line[slot_match.end():].strip()
            if not item_line or set(item_line.strip()) == {'-'}:
                continue
            
            parsed = parse_item_line(item_line)
            
            # Store in correct slot and term
            if slot_num not in slot_to_terms:
                slot_to_terms[slot_num] = [None] * term_count
            
            slot_to_terms[slot_num][current_term] = parsed

    return slot_to_terms


def parse_item_line(line: str) -> Dict[str, Optional[str]]:
    """Parse a single item line into structured data."""
    parts = [p.strip() for p in line.split(' - ') if p.strip()]
    code = None
    name = None
    description = ''
    price = 0.0

    if len(parts) >= 3:
        code = parts[0]
        name = parts[1]
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
        s = parts[0]
        if ' - ' in line:
            left, right = line.split(' - ', 1)
            code = left.strip()
            name = right.strip()
        else:
            name = s

    if not code and name:
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


def build_slots_from_slot_data(slot_data: Dict[int, Dict], images_dir: str) -> List[Dict]:
    """Build the 64-slot structure with per-term data and images."""
    MAX_SLOTS = 64
    TERM_COUNT = 3
    slots = [{'terms': [None] * TERM_COUNT} for _ in range(MAX_SLOTS)]

    for slot_num, terms_list in slot_data.items():
        slot_idx = slot_num - 1  # 0-based indexing
        if 0 <= slot_idx < MAX_SLOTS:
            for term_idx in range(TERM_COUNT):
                if term_idx < len(terms_list) and terms_list[term_idx]:
                    item = terms_list[term_idx]
                    # Look up image
                    code = item.get('code', '')
                    if code:
                        for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                            img_path = os.path.join('images', f"{code}{ext}")
                            if os.path.exists(os.path.join(images_dir, f"{code}{ext}")):
                                item['image'] = img_path
                                break
                    slots[slot_idx]['terms'][term_idx] = item

    return slots


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mapping', '-m', required=True, help='Mapping TXT file path')
    p.add_argument('--product-list', '-p', required=True, help='Product List folder path')
    p.add_argument('--images', '-i', default='./images', help='Output images folder')
    p.add_argument('--out', '-o', default=None, help='Output JSON')
    args = p.parse_args()

    mapping = args.mapping
    product_list = args.product_list
    images = args.images
    out = args.out
    if not out:
        out = os.path.join(os.path.dirname(mapping) or '.', 'assigned_items.json')

    if not os.path.exists(mapping):
        print('Mapping file not found:', mapping)
        return
    if not os.path.isdir(product_list):
        print('Product List folder not found:', product_list)
        return

    print(f"Parsing mapping file (explicit slot format): {mapping}")
    slot_data = parse_mapping_file(mapping, term_count=3)
    
    print(f"Copying and organizing images from: {product_list}")
    copy_images_from_product_list(product_list, images, slot_data)
    
    print(f"Building slot assignments...")
    slots = build_slots_from_slot_data(slot_data, images)

    print(f"Writing output to: {out}")
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(slots, f, indent=2, ensure_ascii=False)

    print(f'[OK] Done! Wrote {out}')
    print(f'[OK] Populated slots with explicit slot mapping')


if __name__ == '__main__':
    main()
