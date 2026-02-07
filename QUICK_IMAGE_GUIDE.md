# Change Images - Quick Start (5 Minutes)

## TL;DR - Just Give Me The Steps!

### Change Header Logo

**Step 1**: Save your logo as `logo.png` in this folder:
```
C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\
```

**Step 2**: Open `config.json` and add this line:
```json
"header_logo_path": "./logo.png"
```

**Step 3**: Save and run:
```bash
python3 main.py
```

✅ Done! Logo appears in header.

---

### Change Product Images

**Step 1**: Create `images` folder:
```
C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\images\
```

**Step 2**: Put product images in it:
```
images\
├─ coke.png
├─ pepsi.png
├─ chips.jpg
└─ ...
```

**Step 3**: Open `item_list.json` and add image paths:
```json
[
  {
    "id": 1,
    "name": "Coca Cola",
    "price": 45.00,
    "image": "./images/coke.png"
  },
  {
    "id": 2,
    "name": "Pepsi",
    "price": 45.00,
    "image": "./images/pepsi.png"
  }
]
```

**Step 4**: Save and run:
```bash
python3 main.py
```

✅ Done! Product images appear on cards.

---

## Image Size Recommendations

| What | Size | Format |
|------|------|--------|
| Logo | 300×100 px | PNG or JPG |
| Products | 200×200 px | PNG or JPG |

---

## Where to Get Images?

### Free Logo Designs
- Canva.com - Easy online editor
- Looka.com - AI logo generator
- Freepik.com - Download templates

### Free Product Images
- Unsplash.com
- Pexels.com
- Pixabay.com
- Stock photos of common products

### Using AI to Generate
- DALL-E
- Midjourney
- Stable Diffusion
- Leonardo.ai

---

## Example: Complete Setup in 5 Minutes

### Your Task: Add 3 Products

1. **Download/prepare images**
   - coke.png ✓
   - pepsi.png ✓
   - sprite.png ✓

2. **Create folder and place images**
   ```
   raon-vending-rpi4\
   ├─ logo.png
   └─ images\
      ├─ coke.png
      ├─ pepsi.png
      └─ sprite.png
   ```

3. **Edit config.json** (add 1 line)
   ```json
   "header_logo_path": "./logo.png"
   ```

4. **Edit item_list.json** (add image paths)
   ```json
   [
     {"name": "Coke", "price": 45, "image": "./images/coke.png"},
     {"name": "Pepsi", "price": 45, "image": "./images/pepsi.png"},
     {"name": "Sprite", "price": 45, "image": "./images/sprite.png"}
   ]
   ```

5. **Run it**
   ```bash
   python3 main.py
   ```

⏱️ **Total time: ~5 minutes**

---

## Exact File Paths

### For Logo
```
C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\logo.png
                                                      ^^^^^^^
                                                      This file
```

### For Products
```
C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\images\coke.png
                                                      ^^^^^^  ^^^^^^^
                                                      folder  file
```

---

## What If It Doesn't Work?

### Logo not showing?
Check these in order:
1. File `logo.png` exists in `raon-vending-rpi4\`? 
   → If NO, save it there
2. Line added to config.json?
   → If NO, add: `"header_logo_path": "./logo.png"`
3. Typo in path?
   → Check spelling exactly

### Product images not showing?
Check these in order:
1. Folder `images\` exists?
   → If NO, create it
2. Images in folder?
   → If NO, move them there
3. `"image": "./images/..."` in item_list.json?
   → If NO, add it for each item
4. Filename matches exactly?
   → Check capitalization and spelling

---

## Real File Locations (Copy-Paste Ready)

### Create Images Folder
```powershell
mkdir "C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\images"
```

### Check Files Exist
```powershell
# Check logo
Test-Path "C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\logo.png"

# Check images
dir "C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4\images"
```

---

## Config JSON - Exact Code to Add

Find this in config.json:
```json
{
  "machine_name": "RAON",
  ...
}
```

Add this line after machine_name:
```json
{
  "machine_name": "RAON",
  "header_logo_path": "./logo.png",
  ...
}
```

---

## Item List JSON - Exact Code to Add

Find each item:
```json
{
  "id": 1,
  "name": "Coca Cola",
  "price": 45.00
}
```

Add image field:
```json
{
  "id": 1,
  "name": "Coca Cola",
  "price": 45.00,
  "image": "./images/coke.png"
}
```

Do this for EVERY item.

---

## Testing Your Images

Run this and watch the output:
```bash
python3 main.py
```

Look for these messages:
```
✓ Loading images...        → Good
Error loading image...     → Problem
```

If error, it will tell you what's wrong!

---

## Common Mistakes (Don't Do These!)

| ❌ Wrong | ✅ Right |
|---------|---------|
| `images\logo.png` | `./images/logo.png` |
| `"image": "logo"` | `"image": "./images/logo.png"` |
| No images folder | Create `images\` folder |
| Missing "image" field | Add to every item |
| `c:\full\path` | `./images/file` |
| LOGO.PNG (uppercase) | logo.png (lowercase, match exactly) |

---

## One More Time - The 3 Simple Steps

### 1️⃣ Put Images in Folders
```
Logo:     raon-vending-rpi4\logo.png
Products: raon-vending-rpi4\images\item1.png
          raon-vending-rpi4\images\item2.png
```

### 2️⃣ Edit config.json
```json
"header_logo_path": "./logo.png"
```

### 3️⃣ Edit item_list.json
```json
"image": "./images/item1.png"
```

---

## Still Stuck?

1. **Check terminal output** - It tells you the problem
2. **Check file paths** - Make sure files actually exist
3. **Check JSON syntax** - Use a JSON validator online
4. **Review IMAGE_CONFIGURATION_GUIDE.md** - More detailed help
5. **Review HOW_TO_CHANGE_IMAGES.md** - Complete reference

---

## Files You Need to Edit

| File | What to Do |
|------|-----------|
| `config.json` | Add: `"header_logo_path": "./logo.png"` |
| `item_list.json` | Add: `"image": "./images/..."` to each item |
| (No code changes needed!) | Just data files! |

---

## Success Looks Like This

Before:
```
Header: RAON (text only)
Cards: No Image (placeholders)
```

After:
```
Header: 🎨 (Your logo here!)
Cards: 📸 (Product photos here!)
```

---

## You're Ready! 🚀

Time to make your vending machine beautiful! 

Questions? Check the detailed guides:
- **HOW_TO_CHANGE_IMAGES.md** - Step-by-step guide
- **IMAGE_CONFIGURATION_GUIDE.md** - Visual examples
