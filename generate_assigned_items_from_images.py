#!/usr/bin/env python3
"""Generate a minimal assigned_items.json from images/ when none exists.

Creates 48 slot entries each with a single term populated from available images.
This is a convenience helper for initial Pi setup when `assigned_items.json` is missing.
"""
import os
import json

IMAGES_DIR = 'images'
OUT_FILE = 'assigned_items.json'
SLOTS = 48

def gather_images():
    if not os.path.isdir(IMAGES_DIR):
        print(f"ERROR: {IMAGES_DIR} directory not found in {os.getcwd()}")
        return []
    imgs = [f for f in sorted(os.listdir(IMAGES_DIR)) if f.lower().endswith(('.png','.jpg','.jpeg','.gif','.bmp'))]
    return imgs

def build_slots(image_files):
    slots = []
    # Round-robin assign images to slots
    for i in range(SLOTS):
        img = image_files[i % len(image_files)] if image_files else None
        code = os.path.splitext(img)[0] if img else f"ITEM{i+1:02d}"
        
        # Create 3 terms per slot (academic year: Term 1, 2, 3)
        terms = []
        for term_idx in range(3):
            term_entry = {
                "code": code,
                "name": code,
                "category": "Uncategorized",
                "price": 0.0,
                "quantity": 1,
                "image": f"{IMAGES_DIR}/{img}" if img else "",
                "description": ""
            }
            terms.append(term_entry)
        
        entry = {"terms": terms}
        slots.append(entry)
    return slots

if __name__ == '__main__':
    images = gather_images()
    if not images:
        print("No images found — cannot generate assigned_items.json automatically.")
        raise SystemExit(1)

    slots = build_slots(images)
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(slots, f, indent=2)

    print(f"Generated {OUT_FILE} with {len(slots)} slots using {len(images)} images.")
    print("You can copy this file to ~/assigned_items.json if desired:")
    print("  cp assigned_items.json ~/assigned_items.json")
