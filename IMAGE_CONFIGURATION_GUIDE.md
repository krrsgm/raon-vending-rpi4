# Image Configuration - Visual Guide

## UI Layout with Image Locations

### Header Logo Position

```
┌──────────────────────────────────────────────────────────────────┐
│  [LOGO HERE]  RAON Vending Machine                     [CART BTN] │  ← Header
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Search      │  ┌────────────────────────────────────────────┐   │
│  ────────    │  │  [PRODUCT IMAGE HERE]                      │   │
│              │  │                                             │   │
│  Categories: │  │  ┌──────────────────────────┐              │   │
│  • All       │  │  │ Coca Cola 12oz          │              │   │
│  • Beverages │  │  │ Refreshing Cola         │              │   │
│  • Snacks    │  │  │ ₱45.00                  │              │   │
│  • Candy     │  │  └──────────────────────────┘              │   │
│              │  └────────────────────────────────────────────┘   │
│              │                                                    │
│              │  [MORE PRODUCT CARDS...]                          │
│              │                                                    │
├──────────────┴────────────────────────────────────────────────────┤
│  🔧 SYSTEM STATUS                                                │
├────────────────────────────────────────────────────────────────────┤
│  © RAON Group Members: Alice | Bob | Charlie                     │
└────────────────────────────────────────────────────────────────────┘
```

---

## File Paths Quick Visual

### Header Logo

```
Your Computer
    ↓
C:\Users\ricar\OneDrive\Documents\
    ↓
raon-vending-rpi4\  (← This folder)
    ├─ main.py
    ├─ config.json
    └─ logo.png  (← Put logo here)
       
config.json:
"header_logo_path": "./logo.png"
```

### Product Images

```
Your Computer
    ↓
C:\Users\ricar\OneDrive\Documents\
    ↓
raon-vending-rpi4\
    ├─ main.py
    ├─ item_list.json
    └─ images\  (← Create this folder)
       ├─ coke.png
       ├─ pepsi.png
       ├─ chips.jpg
       └─ candy.png
       
item_list.json:
{
  "image": "./images/coke.png"
}
```

---

## Configuration Files Showing Image Locations

### config.json

```json
{
  "_comment": "RAON Vending Machine Configuration",
  "machine_name": "RAON Vending",
  "machine_subtitle": "Rapid Access Outlet for Electronic Necessities",
  
  ↓ ADD THIS LINE ↓
  "header_logo_path": "./logo.png",
  
  "currency_symbol": "₱",
  "always_fullscreen": true,
  "group_members": ["Alice", "Bob", "Charlie"],
  
  ...rest of config...
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
    
    ↓ ADD THIS FIELD ↓
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
  },
  {
    "id": 3,
    "slot": "A3",
    "name": "Lay's Chips",
    "description": "Salty Snack",
    "price": 25.00,
    "image": "./images/chips.jpg",
    "category": "Snacks",
    "quantity": 5
  }
]
```

---

## Step-by-Step Process Flow

```
START
  ↓
1. Find/create images
   - logo.png (200-400 x 80-120)
   - product images (200+ x 200+)
  ↓
2. Create images folder
   raon-vending-rpi4/images/
  ↓
3. Place images in folders
   logo.png → raon-vending-rpi4/
   products → raon-vending-rpi4/images/
  ↓
4. Edit config.json
   Add: "header_logo_path": "./logo.png"
  ↓
5. Edit item_list.json
   Add: "image": "./images/filename.png" to each item
  ↓
6. Run the app
   python3 main.py
  ↓
7. See your images!
   Logo in header, products on cards
  ↓
END
```

---

## Image Paths Explained

### What Does "./" Mean?

```
"./" = Current folder (where main.py is)

So:
"./logo.png"         = logo.png in same folder as main.py
"./images/coke.png"  = coke.png in images subfolder
```

### Path Examples in Context

```
Directory Structure:
raon-vending-rpi4/
├─ main.py (this is where "./" points)
├─ logo.png
└─ images/
   ├─ coke.png
   └─ pepsi.png

Correct Paths:
"image": "./logo.png"           ✅ Works
"image": "./images/coke.png"    ✅ Works
"image": "logo.png"             ⚠️ May not work
"image": "images/coke.png"      ⚠️ May not work
"image": "C:\...logo.png"        ✅ Works but not portable
```

---

## Complete Working Example

### Folder Structure
```
C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\
├─ main.py
├─ kiosk_app.py
├─ config.json
├─ item_list.json
├─ logo.png                ← Your company logo
└─ images/
   ├─ beverage1.png
   ├─ beverage2.png
   ├─ snack1.png
   ├─ snack2.png
   └─ candy.jpg
```

### config.json Entry
```json
{
  "machine_name": "RAON Vending",
  "header_logo_path": "./logo.png"
}
```

### item_list.json Entries
```json
[
  {
    "id": 1,
    "name": "Coca Cola",
    "price": 45.00,
    "image": "./images/beverage1.png"
  },
  {
    "id": 2,
    "name": "Pepsi",
    "price": 45.00,
    "image": "./images/beverage2.png"
  },
  {
    "id": 3,
    "name": "Lay's Chips",
    "price": 25.00,
    "image": "./images/snack1.png"
  },
  {
    "id": 4,
    "name": "Doritos",
    "price": 25.00,
    "image": "./images/snack2.png"
  },
  {
    "id": 5,
    "name": "Candy Bar",
    "price": 30.00,
    "image": "./images/candy.jpg"
  }
]
```

---

## Real-World Setup Example

### For Beverages Vending Machine

```
Folder Layout:
vending-machine/
├─ main.py
├─ config.json
├─ item_list.json
└─ images/
   ├─ coke.png
   ├─ pepsi.png
   ├─ sprite.png
   ├─ fanta_orange.png
   ├─ royal_orange.png
   ├─ mountain_dew.png
   ├─ iced_tea.png
   └─ water.png

config.json:
{
  "machine_name": "Beverage Station",
  "header_logo_path": "./images/coke.png"  (or your company logo)
}

item_list.json:
[
  {"id": 1, "name": "Coca Cola", "price": 50, "image": "./images/coke.png"},
  {"id": 2, "name": "Pepsi", "price": 50, "image": "./images/pepsi.png"},
  ...
]
```

---

## Organized Structure for Large Inventories

```
raon-vending-rpi4/
├─ main.py
├─ config.json
├─ item_list.json
└─ images/
   ├─ beverages/
   │  ├─ coke.png
   │  ├─ pepsi.png
   │  ├─ sprite.png
   │  └─ fanta.png
   ├─ snacks/
   │  ├─ chips.jpg
   │  ├─ cookies.jpg
   │  └─ popcorn.jpg
   ├─ candy/
   │  ├─ chocolate.jpg
   │  ├─ gummies.jpg
   │  └─ lollipop.jpg
   └─ logo.png

item_list.json:
[
  {"image": "./images/beverages/coke.png"},
  {"image": "./images/snacks/chips.jpg"},
  {"image": "./images/candy/chocolate.jpg"}
]
```

---

## What the System Does With Images

### When You Start the App

```
START app
  ↓
Load config.json
  ├─ Read: "header_logo_path": "./images/logo.png"
  └─ Try to load from disk
  ↓
Load item_list.json
  ├─ For each item, read "image" field
  └─ Try to load each image from disk
  ↓
Display on Screen
  ├─ Header logo appears if found
  ├─ Product images appear if found
  └─ Text placeholders if not found
  ↓
END
```

### How Images Are Displayed

```
Original Image File on Disk
  └─ 400×300 pixels (example)
  
  ↓ System loads with PIL (Python Image Library)
  
  ↓ System resizes to fit display area
  
Header Logo:
  └─ Resizes to header height (~80 pixels)
  └─ Maintains aspect ratio
  └─ Displays in top-left corner
  
Product Image:
  └─ Resizes to card height (150 pixels)
  └─ Maintains aspect ratio
  └─ Displays on product card
```

---

## Image File Size Reference

| Type | Typical Size | Recommended |
|------|--------------|-------------|
| Logo (PNG) | 50-100 KB | < 200 KB |
| Product (JPG) | 30-100 KB | < 150 KB |
| Product (PNG) | 100-300 KB | < 300 KB |

Smaller = faster loading
Larger = higher quality

---

## Troubleshooting Decision Tree

```
Images not showing?
  ├─ Check if config.json has "header_logo_path"?
  │  └─ NO → Add it: "header_logo_path": "./logo.png"
  │  └─ YES → Continue
  │
  ├─ Check if item_list.json has "image" fields?
  │  └─ NO → Add them: "image": "./images/item.png"
  │  └─ YES → Continue
  │
  ├─ Check if files exist in folder?
  │  └─ NO → Download/create images and place them
  │  └─ YES → Continue
  │
  ├─ Check if paths are correct?
  │  └─ NO → Fix paths to match file locations
  │  └─ YES → Continue
  │
  ├─ Check terminal for error messages?
  │  └─ YES → Error message tells you the problem
  │  └─ NO → Problem might be formatting
  │
  └─ Try running: python3 main.py
     └─ Watch console for error messages
     └─ Should show if images load successfully
```

---

## Summary Checklist

- [ ] Downloaded or created logo image
- [ ] Downloaded or created product images
- [ ] Created `images/` folder in project directory
- [ ] Placed logo in project root folder
- [ ] Placed product images in `images/` folder
- [ ] Added `"header_logo_path": "./logo.png"` to config.json
- [ ] Added `"image": "./images/..."` fields to each item in item_list.json
- [ ] Saved config.json
- [ ] Saved item_list.json
- [ ] Restarted the app
- [ ] Verified images appear on screen

---

## Quick Command Reference

### Check if files exist (Windows PowerShell)
```powershell
# Check logo
Test-Path "C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\logo.png"

# Check images folder
Test-Path "C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\images"

# List images
Get-ChildItem "C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\images"
```

### Check if files exist (Linux/Mac)
```bash
# Check logo
test -f ./logo.png && echo "Logo exists"

# Check images folder
test -d ./images && echo "Images folder exists"

# List images
ls -la ./images/
```

---

This visual guide should help you understand exactly where to put your images and how to configure them!
