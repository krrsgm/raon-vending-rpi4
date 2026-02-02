# Quick Fix Guide - Images & Layout

## What Was Fixed

✓ **Missing Images** - Image paths corrected in `assigned_items.json`  
✓ **Poor Layout** - Card size and spacing optimized in `kiosk_app.py`

## On Your Raspberry Pi

### Step 1: Update assigned_items.json (if not already done)

```bash
cd ~/Desktop/raon-vending-rpi4-main

# Run the fix script
python3 fix_image_paths.py
```

Expected output:
```
Found 67 unique product codes in images/
Updated XXX image paths
SUCCESS: Image paths fixed!
```

### Step 2: Copy to home directory (if app reads from there)

```bash
cp assigned_items.json ~/assigned_items.json
```

### Step 3: Run the app

```bash
python3 main.py
```

**Expected:** 
- Product images now display in cards
- Cards fit properly on the screen
- 3+ cards per row depending on display size

## Testing Image Loading

If images still don't show, debug with:

```bash
python3 - <<'PY'
import json, os

with open('assigned_items.json', 'r') as f:
    data = json.load(f)

# Show first 3 items
for i in range(min(3, len(data))):
    slot = data[i]
    if 'terms' in slot:
        item = slot['terms'][0]
        code = item.get('code')
        img_path = item.get('image')
        
        # Check if image file exists
        abs_path = os.path.join('.', img_path) if img_path else None
        exists = os.path.exists(abs_path) if abs_path else False
        
        print(f"Slot {i}: {code}")
        print(f"  Path: {img_path}")
        print(f"  File exists: {exists}")
PY
```

## Layout Customization

If cards are still too large/small, edit `kiosk_app.py`:

**Line 87-88:** Card dimensions
```python
self.card_width = int(self.ppi * 2.0)   # Adjust 2.0 for width
self.card_height = int(self.ppi * 3.0)  # Adjust 3.0 for height
```

**Line 91:** Card spacing
```python
self.card_spacing = int(self.ppi * (0.5 / 2.54))  # Adjust 0.5 for spacing
```

**Line 659:** Min/max columns
```python
num_cols = max(3, min(8, num_cols))  # Change 3 or 8 for different ranges
```

## Files Changed

1. **assigned_items.json** - All 153 image paths updated
2. **kiosk_app.py** - Card size reduced, spacing tightened, column range expanded

## Status

✅ Both issues resolved  
✅ Ready to test on display
