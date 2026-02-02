#!/usr/bin/env python3
"""Debug script to check image paths and resolution on Pi."""

import os
import sys
import json
import platform
from fix_paths import get_absolute_path, find_file_in_search_paths

# Load the assigned items
assigned_file = get_absolute_path('assigned_items.json')
print(f"✓ Assigned items file: {assigned_file}")
print(f"  Exists: {os.path.exists(assigned_file)}")

with open(assigned_file, 'r') as f:
    items = json.load(f)

# Check first 5 items
print(f"\n📋 Checking first 5 items from assigned_items.json:")
for idx, slot in enumerate(items[:5]):
    if slot and slot.get('terms'):
        item = slot['terms'][0]  # First term
        image_path = item.get('image', '')
        print(f"\n  Slot {idx+1}: {item.get('code')}")
        print(f"    JSON path: {image_path}")
        
        # Try to resolve it
        resolved = get_absolute_path(image_path)
        print(f"    Resolved to: {resolved}")
        print(f"    Exists: {os.path.exists(resolved)}")
        
        # Try alternate paths
        if not os.path.exists(resolved):
            print(f"    ⚠️  Not found! Trying alternatives:")
            
            # Try direct
            if os.path.exists(image_path):
                print(f"      ✓ Found at: {image_path}")
            
            # Try in images/
            alt1 = f"images/{os.path.basename(image_path)}"
            if os.path.exists(alt1):
                print(f"      ✓ Found at: {alt1}")
            
            alt2 = get_absolute_path(alt1)
            if os.path.exists(alt2):
                print(f"      ✓ Found at: {alt2}")

# Check images directory
print(f"\n📁 Images directory check:")
images_dir = get_absolute_path('images')
print(f"  Looking for: {images_dir}")
print(f"  Exists: {os.path.exists(images_dir)}")

if os.path.exists(images_dir):
    images = os.listdir(images_dir)
    print(f"  Found {len(images)} images:")
    for img in sorted(images)[:10]:
        print(f"    - {img}")
    if len(images) > 10:
        print(f"    ... and {len(images) - 10} more")

# Check current working directory
print(f"\n🔍 Path context:")
print(f"  platform.machine(): {platform.machine()}")
print(f"  os.getcwd(): {os.getcwd()}")
print(f"  sys.argv[0]: {sys.argv[0]}")
print(f"  __file__: {__file__}")

# Check search paths used by get_absolute_path
print(f"\n🔎 Search paths that get_absolute_path uses:")
search_paths = [
    os.path.expanduser('~'),
    os.path.dirname(os.path.abspath(__file__)),
    os.getcwd()
]
for i, path in enumerate(search_paths, 1):
    print(f"  {i}. {path}")
    print(f"     Exists: {os.path.exists(path)}")
    if os.path.exists(path):
        images_check = os.path.join(path, 'images')
        print(f"     Has images/: {os.path.exists(images_check)}")
