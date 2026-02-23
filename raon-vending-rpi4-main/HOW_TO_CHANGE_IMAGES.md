# How to Change Logo and Item Images

## Overview

Your vending machine system supports both a **header logo** and **item product images**. This guide explains how to add and change them.

---

## Part 1: Header Logo (Top of Screen)

### What Is It?

The header logo appears in the top-left corner of your vending machine display. It's the branding area.

### Where Is It Now?

- **Current**: Shows machine name text (e.g., "RAON") if no image is configured
- **Location**: Top-left of the blue header bar
- **Size**: Automatically resizes to fit the header height

### How to Change It

#### Step 1: Prepare Your Logo Image

1. **Get a logo image** in JPG or PNG format
2. **Size recommendations**:
   - Width: 200-400 pixels
   - Height: 80-120 pixels
   - Format: PNG (with transparency) or JPG
   - Aspect ratio: 2-3:1 (wider than tall)

3. **Place it in your project folder**:
   - Put your logo file in the vending machine directory
   - Example: `c:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\logo.png`

#### Step 2: Update config.json

Add this line to your `config.json`:

```json
{
  "machine_name": "RAON Vending",
  "machine_subtitle": "Rapid Access Outlet for Electronic Necessities",
  "header_logo_path": "./logo.png",
  
  "currency_symbol": "₱",
  ...
}
```

**Important**: Use `./` for files in the same directory as main.py

#### Step 3: Valid Logo Paths

```json
{
  "header_logo_path": "./logo.png"                    // Same folder as main.py
}
```

```json
{
  "header_logo_path": "/absolute/path/to/logo.png"   // Absolute path
}
```

```json
{
  "header_logo_path": "./images/logo.png"             // Subfolder
}
```

#### Step 4: Restart and Test

1. Save your `config.json`
2. Restart the vending machine application
3. The logo should appear in the header

### What Happens If:

| Scenario | Result |
|----------|--------|
| No `header_logo_path` configured | Shows machine name initials |
| File path doesn't exist | Shows machine name as fallback |
| Image can't be loaded | Shows text placeholder |
| Image too small | Automatically enlarged |
| Image too large | Automatically shrunk |

---

## Part 2: Item Product Images

### What Is It?

Each item in your vending machine can have a product image displayed on its card. The image shows what the item looks like.

### Where Are They?

- **Location**: Product card (above item name)
- **Size**: 150 pixels tall, width scales to maintain aspect ratio
- **Shown on**: Item selection screen

### How to Add Item Images

#### Step 1: Prepare Product Images

1. **Get images for each item** (JPG or PNG)
2. **Size recommendations**:
   - Height: 150 pixels minimum
   - Width: Any (will be automatically resized)
   - Format: PNG or JPG
   - Aspect ratio: Any (maintains ratio)

3. **Create an images folder**:
   ```
   project-folder/
   ├── main.py
   ├── kiosk_app.py
   ├── config.json
   ├── item_list.json
   └── images/
       ├── soda.png
       ├── chips.jpg
       ├── candy.png
       └── ...
   ```

#### Step 2: Add Images to item_list.json

Your `item_list.json` file should have an "image" field for each item:

```json
[
  {
    "id": 1,
    "slot": "A1",
    "name": "Coca Cola",
    "description": "12oz Can - Refreshing Cola",
    "price": 45.00,
    "image": "./images/soda.png",
    "category": "Beverages"
  },
  {
    "id": 2,
    "slot": "A2", 
    "name": "Lay's Chips",
    "description": "Classic Flavored Snack",
    "price": 25.00,
    "image": "./images/chips.jpg",
    "category": "Snacks"
  },
  {
    "id": 3,
    "slot": "A3",
    "name": "Candy Bar",
    "description": "Chocolate Goodness",
    "price": 30.00,
    "image": "./images/candy.png",
    "category": "Candy"
  }
]
```

#### Step 3: Verify Image Paths

```json
{
  "image": "./images/product.png"              // Relative path
}
```

```json
{
  "image": "/absolute/path/to/product.png"    // Absolute path
}
```

```json
{
  "image": ""                                  // Empty = no image
}
```

#### Step 4: Test

1. Save `item_list.json`
2. Restart the application
3. Product images should appear on the item cards

---

## Image Path Configuration

### Relative Paths (Recommended)

```
Project Folder
├── main.py (current working directory)
├── config.json
├── item_list.json
├── logo.png              → Use "./logo.png"
└── images/
    ├── item1.png         → Use "./images/item1.png"
    └── item2.jpg         → Use "./images/item2.jpg"
```

### Absolute Paths

```
Windows:  "C:\\Users\\username\\project\\images\\logo.png"
Linux:    "/home/username/project/images/logo.png"
```

---

## Complete Example Configuration

### config.json
```json
{
  "machine_name": "RAON Vending",
  "machine_subtitle": "Rapid Access Outlet for Electronic Necessities",
  "header_logo_path": "./logo.png",
  "currency_symbol": "₱",
  "always_fullscreen": true,
  "group_members": ["Alice", "Bob", "Charlie"]
}
```

### item_list.json
```json
[
  {
    "id": 1,
    "slot": "A1",
    "name": "Coca Cola",
    "description": "12oz Can",
    "price": 45.00,
    "image": "./images/coke.png",
    "category": "Beverages",
    "quantity": 10
  },
  {
    "id": 2,
    "slot": "A2",
    "name": "Pepsi",
    "description": "12oz Can",
    "price": 45.00,
    "image": "./images/pepsi.png",
    "category": "Beverages",
    "quantity": 8
  }
]
```

### Folder Structure
```
raon-vending-rpi4/
├── main.py
├── kiosk_app.py
├── config.json
├── item_list.json
├── logo.png                 (Header logo)
└── images/
    ├── coke.png
    ├── pepsi.png
    ├── chips.png
    └── candy.jpg
```

---

## Image Quality Tips

### Logo Guidelines
- **Format**: PNG (allows transparency) or JPG
- **Size**: 200-400 × 80-120 pixels
- **DPI**: 72 DPI is fine
- **Transparency**: PNG with transparency looks best

**Good**: 300×100 PNG with logo on transparent background
**Avoid**: Very large files (> 500KB per image)

### Product Image Guidelines
- **Format**: PNG or JPG
- **Height**: 150+ pixels (taller is better for quality)
- **Size**: 200×150 to 400×300 pixels
- **Background**: White or transparent works best
- **Quality**: Clear, recognizable product photo

**Good**: 200×200 JPG of product on white background
**Avoid**: Very low resolution, unclear images

---

## Troubleshooting

### Header Logo Not Showing

**Issue**: Logo text appears instead of image

**Solutions**:
1. Check file exists: `./logo.png` relative to `main.py`
2. Verify path in config.json (no typos)
3. Check file format (PNG or JPG only)
4. Check image isn't corrupted - try opening in image viewer
5. Check terminal for error message
6. Try absolute path instead of relative

**Error Message**: "Error loading header logo..."
- File path is wrong or file doesn't exist
- Image format not supported
- File is corrupted

### Product Images Not Showing

**Issue**: "No Image" appears on product cards

**Solutions**:
1. Check `item_list.json` has "image" field for each item
2. Verify image file exists at the path
3. Use `./images/` prefix (relative path)
4. Check image file format (PNG or JPG)
5. Verify no typos in filename
6. Check terminal for error messages

**Error Message**: "Error loading image..."
- File path is wrong
- Image format not supported
- File is corrupted

### Images Look Blurry

**Solution**: Use higher resolution images
- Logo: At least 400×150 pixels
- Products: At least 200×200 pixels

### Images Don't Resize Properly

**Solution**: Check image aspect ratio
- System automatically maintains aspect ratio
- Tall images scale down height
- Wide images scale down width

---

## File Format Support

| Format | Support | Notes |
|--------|---------|-------|
| PNG | ✅ Yes | Best for logos (supports transparency) |
| JPG | ✅ Yes | Good for product photos |
| GIF | ❌ No | Not supported |
| BMP | ❌ No | Not supported |
| SVG | ❌ No | Not supported |

---

## Advanced: Image Caching

The system caches images in memory to avoid reloading them repeatedly. This:
- ✅ Improves performance
- ✅ Reduces CPU usage
- ✅ Faster scrolling
- ❌ Uses more RAM (acceptable)

No configuration needed - it's automatic.

---

## Quick Reference

### Change Logo
1. Save image as `logo.png` in project folder
2. Add to config.json: `"header_logo_path": "./logo.png"`
3. Restart app

### Change Product Images
1. Create `images/` folder
2. Add images: `images/item1.png`, `images/item2.png`, etc.
3. Update `item_list.json` with image paths: `"image": "./images/item1.png"`
4. Restart app

### Valid Image Paths
```
"./logo.png"                    ✅ Same folder
"./images/logo.png"             ✅ Subfolder
"/absolute/path/logo.png"       ✅ Absolute path
"logo.png"                      ⚠️  May not work
"images\logo.png"               ❌ Use forward slash
"images/logo.png"               ✅ Correct
```

---

## Image File Locations

### Recommended Folder Structure
```
raon-vending-rpi4/
├── main.py                    (Start here)
├── config.json
├── item_list.json
├── logo.png                   (Header logo)
└── images/                    (Product images)
    ├── beverages/
    │   ├── coke.png
    │   └── pepsi.png
    ├── snacks/
    │   ├── chips.png
    │   └── popcorn.png
    └── candy/
        ├── candy_bar.png
        └── gummies.png
```

Use the same format in item_list.json:
```json
{
  "image": "./images/beverages/coke.png"
}
```

---

## Step-by-Step Example

### 1. Get Your Images
- Download logo.png (400×120 pixels)
- Download product images (200×200 pixels each)

### 2. Create Folder Structure
```
C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\
├── logo.png
└── images/
    ├── coke.png
    ├── pepsi.png
    └── sprite.png
```

### 3. Update config.json
```json
{
  "header_logo_path": "./logo.png"
}
```

### 4. Update item_list.json
```json
[
  {"id": 1, "name": "Coke", "price": 45, "image": "./images/coke.png"},
  {"id": 2, "name": "Pepsi", "price": 45, "image": "./images/pepsi.png"},
  {"id": 3, "name": "Sprite", "price": 45, "image": "./images/sprite.png"}
]
```

### 5. Run the App
```bash
python3 main.py
```

✅ Done! Your images should now appear.

---

## Support

If images still don't show:
1. Check the **terminal output** for error messages
2. Verify paths with Windows Explorer or file manager
3. Try opening images in an image viewer first
4. Make sure working directory is correct (cd to project folder)
5. Review the **Troubleshooting** section above
