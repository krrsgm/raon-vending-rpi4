#!/usr/bin/env python3
"""
Update assigned_items.json with correct image paths and detailed category/description info.
Reads from Product List folder structure to map images to products.
"""
import json
import os
import re

def get_product_code_from_filename(filename: str) -> str:
    """Extract product code from image filename."""
    return os.path.splitext(filename)[0]

def get_product_info_from_name(name: str) -> tuple:
    """Extract category and description from product name.
    
    Format: "CODE - CATEGORY: description"
    Returns: (category, description)
    """
    # Pattern: "CODE - CATEGORY: details"
    match = re.search(r'-\s*([^:]+?):\s*(.+?)$', name)
    if match:
        category = match.group(1).strip()
        description = match.group(2).strip()
        return category, description
    
    # Fallback: just extract category
    match = re.search(r'-\s*([^:]+?)$', name)
    if match:
        category = match.group(1).strip()
        return category, ""
    
    return "", ""

def scan_product_list_for_images(product_list_dir: str) -> dict:
    """Scan Product List structure and build a map of code -> {term -> image_path}."""
    code_to_images = {}
    
    for term_folder in ["Term 1", "Term 2", "Term 3"]:
        term_path = os.path.join(product_list_dir, term_folder)
        if not os.path.isdir(term_path):
            continue
        
        for row_folder in [f"Row {i}" for i in range(1, 9)]:
            row_path = os.path.join(term_path, row_folder)
            if not os.path.isdir(row_path):
                continue
            
            try:
                for filename in os.listdir(row_path):
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        code = get_product_code_from_filename(filename)
                        if code not in code_to_images:
                            code_to_images[code] = {}
                        # Store the path relative to project root
                        rel_path = os.path.relpath(os.path.join(row_path, filename), '.')
                        code_to_images[code][term_folder] = rel_path
            except Exception as e:
                print(f"Error reading {row_path}: {e}")
    
    return code_to_images

def create_category_mapping() -> dict:
    """Create a mapping of product codes to meaningful categories and descriptions."""
    # Based on product codes in the electronic components domain
    category_map = {
        # Sensors
        'SS1': ('Sensors', 'IR Sensor, Photodiode, PIR Sensor'),
        
        # Basic Discrete Components
        'JMM': ('Wiring', 'Jumper Wires (Male to Male)'),
        'JFF': ('Wiring', 'Jumper Wires (Female to Female)'),
        'JMF': ('Wiring', 'Jumper Wires (Male to Female)'),
        'SW': ('Wiring', 'Solid Wires'),
        'SW2': ('Wiring', 'Stranded Wires'),
        'FC': ('Chemical', 'Ferric Chloride for PCB etching'),
        'SD': ('Soldering', 'Solder Bundle with Lead and Paste'),
        
        # Passive Components
        'BB': ('Prototyping', 'Breadboard'),
        'R': ('Resistors', 'Resistor Assortment'),
        'C': ('Capacitors', 'Capacitor Assortment'),
        'D': ('Diodes', 'Diode Assortment'),
        'L': ('Inductors', 'Inductor Assortment'),
        
        # Active Components
        'TR': ('Transistors', 'Transistor Assortment'),
        'AMP': ('Amplifiers', 'Amplifier IC'),
        'IC': ('Integrated Circuits', 'Logic IC'),
        'MUX': ('Multiplexers', 'Multiplexer IC'),
        'PSU': ('Power Supply', 'Power Supply Components'),
        
        # Connectors & Switches
        'PB': ('Switches', 'Push Buttons'),
        'AC': ('Connectors', 'Alligator Clips'),
        
        # Arduino & Microcontrollers
        'ARD': ('Microcontrollers', 'Arduino UNO'),
        'LED': ('Displays', 'LED Components'),
    }
    
    return category_map

def update_assigned_items_with_images_and_info():
    """Update assigned_items.json with correct images and category/description info."""
    json_path = './assigned_items.json'
    product_list_dir = './Product List'
    
    if not os.path.exists(json_path):
        print(f"ERROR: {json_path} not found")
        return
    
    if not os.path.isdir(product_list_dir):
        print(f"ERROR: {product_list_dir} directory not found")
        return
    
    # Load current JSON
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_path}: {e}")
        return
    
    # Scan for available images
    code_to_images = scan_product_list_for_images(product_list_dir)
    print(f"Found images for {len(code_to_images)} product codes")
    
    # Get category mapping
    category_map = create_category_mapping()
    
    # Update JSON
    updated_count = 0
    term_map = {'Term 1': 0, 'Term 2': 1, 'Term 3': 2}
    
    for slot_idx, slot_entry in enumerate(data):
        if not isinstance(slot_entry, dict) or 'terms' not in slot_entry:
            continue
        
        for term_idx, item in enumerate(slot_entry['terms']):
            if not isinstance(item, dict):
                continue
            
            code = item.get('code', '')
            name = item.get('name', '')
            
            if not code:
                continue
            
            # Update image path from Product List if available
            if code in code_to_images:
                for term_name, img_path in code_to_images[code].items():
                    if term_name in term_map and term_map[term_name] == term_idx:
                        # Normalize to forward slashes
                        img_path = img_path.replace('\\', '/')
                        item['image'] = img_path
                        updated_count += 1
                        break
            
            # Update category and description from product name
            if not item.get('category') or item.get('category') == '':
                # Try to extract from name first
                cat, desc = get_product_info_from_name(name)
                if cat:
                    item['category'] = cat
                    if desc:
                        item['description'] = desc
            
            # Fallback to category map if name extraction didn't work
            if not item.get('category') or item.get('category') == '':
                # Try fuzzy matching
                for code_prefix, (cat, desc) in category_map.items():
                    if code.upper().startswith(code_prefix.upper()):
                        item['category'] = cat
                        if not item.get('description') or item.get('description') == 'P0':
                            item['description'] = desc
                        break
    
    # Write back
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print(f"[OK] Updated {updated_count} image paths in {json_path}")
    except Exception as e:
        print(f"Error writing {json_path}: {e}")

if __name__ == '__main__':
    update_assigned_items_with_images_and_info()
