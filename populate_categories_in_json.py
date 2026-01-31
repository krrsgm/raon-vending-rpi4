#!/usr/bin/env python3
"""
Extract category information from product names and populate category field in assigned_items.json.
Product names typically follow the pattern: "CODE - CATEGORY: item details"
"""
import json
import re
import os

def extract_category_from_name(name: str) -> str:
    """Extract category from product name."""
    # Pattern: "CODE - CATEGORY: details" or "CODE - CATEGORY"
    match = re.search(r'-\s*([^:]+?)(?::|$)', name)
    if match:
        category = match.group(1).strip()
        return category
    return ""

def populate_categories():
    """Extract and populate category field in assigned_items.json."""
    json_path = './assigned_items.json'
    
    if not os.path.exists(json_path):
        print(f"ERROR: {json_path} not found")
        return
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_path}: {e}")
        return
    
    # Extract categories from names
    updated_count = 0
    unique_categories = set()
    
    for slot_idx, slot_entry in enumerate(data):
        if not isinstance(slot_entry, dict) or 'terms' not in slot_entry:
            continue
        
        for term_idx, item in enumerate(slot_entry['terms']):
            if not isinstance(item, dict):
                continue
            
            name = item.get('name', '')
            if not name or item.get('category'):
                # Skip if already has category or no name
                continue
            
            category = extract_category_from_name(name)
            if category:
                item['category'] = category
                unique_categories.add(category)
                updated_count += 1
    
    # Write back
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[OK] Updated {updated_count} category fields in {json_path}")
        print(f"[OK] Found {len(unique_categories)} unique categories:")
        for cat in sorted(unique_categories):
            print(f"  - {cat}")
    except Exception as e:
        print(f"Error writing {json_path}: {e}")

if __name__ == '__main__':
    populate_categories()
