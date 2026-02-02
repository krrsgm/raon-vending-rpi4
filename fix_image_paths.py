#!/usr/bin/env python3
"""
Regenerate image paths in assigned_items.json to use the images/ directory format.
Converts paths like "Product List/Term 1/Row 1/SS1.png" to "images/SS1.png"
"""
import json
import os
import sys

def extract_code_from_filename(filename: str) -> str:
    """Extract product code from image filename (without extension)."""
    return os.path.splitext(filename)[0]

def get_available_images() -> dict:
    """Build a map of product code -> image filename."""
    images_dir = './images'
    code_to_image = {}
    
    if not os.path.isdir(images_dir):
        print(f"ERROR: {images_dir} directory not found")
        return code_to_image
    
    try:
        for filename in os.listdir(images_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                code = extract_code_from_filename(filename)
                # Prefer png over jpg
                if code not in code_to_image or filename.endswith('.png'):
                    code_to_image[code] = filename
    except Exception as e:
        print(f"Error reading images directory: {e}")
    
    return code_to_image

def fix_image_paths_in_json():
    """Fix image paths in assigned_items.json."""
    json_path = './assigned_items.json'
    
    if not os.path.exists(json_path):
        print(f"ERROR: {json_path} not found")
        return False
    
    # Load current JSON
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_path}: {e}")
        return False
    
    # Get available images
    code_to_image = get_available_images()
    print(f"Found {len(code_to_image)} unique product codes in images/")
    
    # Update image paths in JSON
    updated_count = 0
    unchanged_count = 0
    
    for slot_idx, slot_entry in enumerate(data):
        if not isinstance(slot_entry, dict) or 'terms' not in slot_entry:
            continue
        
        for term_idx, item in enumerate(slot_entry['terms']):
            if not isinstance(item, dict):
                continue
            
            code = item.get('code', '')
            if not code:
                continue
            
            # Find matching image
            if code in code_to_image:
                new_image_path = f"images/{code_to_image[code]}"
                old_image = item.get('image', '')
                if old_image != new_image_path:
                    item['image'] = new_image_path
                    updated_count += 1
                    print(f"  Slot {slot_idx}, Term {term_idx}: {code} -> {new_image_path}")
                else:
                    unchanged_count += 1
            else:
                # No matching image file
                if item.get('image'):
                    item['image'] = ''
                    updated_count += 1
                    print(f"  Slot {slot_idx}, Term {term_idx}: {code} -> (no image file)")
    
    # Write back
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Updated {updated_count} image paths, {unchanged_count} unchanged")
        return True
    except Exception as e:
        print(f"Error writing {json_path}: {e}")
        return False

if __name__ == '__main__':
    print("=" * 70)
    print("Regenerating image paths in assigned_items.json")
    print("=" * 70)
    print()
    
    success = fix_image_paths_in_json()
    
    if success:
        print("\n" + "=" * 70)
        print("SUCCESS: Image paths fixed!")
        print("=" * 70)
        sys.exit(0)
    else:
        print("\n" + "=" * 70)
        print("FAILED: Could not fix image paths")
        print("=" * 70)
        sys.exit(1)
