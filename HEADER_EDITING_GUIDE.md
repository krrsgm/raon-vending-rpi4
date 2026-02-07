# Header Editing & Customization Guide

## What's New

### 1. Header Now Shows Subtitle
The header now displays both the machine name AND subtitle, similar to how you can edit items in the cart.

**Before:**
```
┌─────────────────────────────────────────────┐
│ RAON                              [Cart]    │
│                                             │
└─────────────────────────────────────────────┘
```

**After:**
```
┌─────────────────────────────────────────────┐
│ [Logo or Text]  RAON                        │
│                 Rapid Access Outlet...  [Cart]
│                                             │
└─────────────────────────────────────────────┘
```

### 2. Easy Header Editing in Admin Panel
Click **"Kiosk Config"** button in the admin screen to edit:
- ✏️ Machine name
- ✏️ Machine subtitle  
- 🖼️ Header logo path
- 📏 Display diagonal size
- 📂 Item categories
- 👥 Group members

### 3. Logo Path Editor with Live Preview
- **Type/Paste path** → See preview update in real-time
- **Browse button** → Select logo file from disk
- **Preview button** → View full-size logo in popup
- **Placeholder** → Shows initials or text if no logo

---

## How to Edit Header

### Step 1: Open Admin Panel
Press your admin key/button to open the admin screen.

### Step 2: Click "Kiosk Config"
Button location: Top-right of "Manage Items" section

### Step 3: Edit Header Settings

#### Edit Machine Name
```
Machine Name: [RAON              ]
              ↓ This appears as title in header
```

#### Edit Machine Subtitle
```
Machine Subtitle: [Rapid Access Outlet for Electronic Necessities    ]
                  ↓ This appears below machine name
```

#### Edit Logo Path
Three options:

**Option A: Browse for Logo File**
```
Header Logo Path: [./logo.png] [Browse] [Preview]
                                  ↑
                              Click to select file
```

**Option B: Type Path Manually**
```
Header Logo Path: [./logo.png]
                  └─ Type or paste path here
                  └─ Preview updates automatically
```

**Option C: View Full Logo**
```
Logo Preview:  [Current logo thumbnail here]
               └─ Click [Preview] button for full size
```

### Step 4: Save Changes
Click **Save** button at bottom right.

---

## Features Explained

### Logo Placeholder
If no logo image is found:
- Shows machine name initials (e.g., "RAON" → "RAON")
- Or shows first 4 letters of name
- Displayed in a styled box to indicate it's a placeholder

### Real-Time Preview
As you type the path:
- Preview updates automatically
- Shows "[No logo selected]" if empty
- Shows "[File not found]" if path is invalid
- Shows "[Error: ...]" if image can't be loaded

### Preview Button
Click to see full-size logo in a popup window:
- Useful for verifying logo looks good
- Shows actual image quality
- Window sizes to match image dimensions

### Browse Button
Opens file dialog to select logo:
- Filters for image files (PNG, JPG, GIF, BMP)
- Converts absolute path to relative if possible
- Auto-updates preview when file selected

---

## Configuration Structure

### config.json Fields

```json
{
  "machine_name": "RAON",
  "machine_subtitle": "Rapid Access Outlet for Electronic Necessities",
  "header_logo_path": "./logo.png",
  "display_diagonal_inches": 13.3,
  "categories": ["Category 1", "Category 2"],
  "group_members": ["Member 1", "Member 2"]
}
```

All fields are optional:
- `machine_name` - Default: "RAON"
- `machine_subtitle` - Default: "RApid Access Outlet for Electronic Necessities"
- `header_logo_path` - Default: "" (empty = no logo)

---

## Logo File Specifications

### Recommended Specifications
```
Format:       PNG (best), JPG, GIF, BMP
Size:         300-600 pixels wide
Height:       100-150 pixels
Aspect Ratio: 3:1 or wider (landscape)
Color:        Any (will be scaled to fit)
```

### Path Options
```
Relative paths (recommended):
  ./logo.png                  ← Same folder as app
  ./images/logo.png          ← In images subfolder
  ../shared/logo.png         ← Parent folder

Absolute paths (Windows):
  C:\Users\Admin\logo.png
  C:\vending\logos\raon.png

Absolute paths (Raspberry Pi):
  /home/pi/logo.png
  /opt/vending/logos/raon.png
```

---

## How It Looks

### In Normal View (Kiosk Screen)
```
┌──────────────────────────────────────────────────┐
│ [🖼️ LOGO]  RAON                          [Cart] │
│            Rapid Access Outlet...               │
│                                                  │
│ [Product cards below...]                        │
└──────────────────────────────────────────────────┘
```

### In Admin Config Window
```
┌─── Kiosk Configuration ──────────────────────────┐
│                                                  │
│ Machine Name:         [RAON                   ] │
│ Machine Subtitle:     [Rapid Access Outlet... ] │
│                                                  │
│ Header Logo Path:     [./logo.png] [Browse][Pre]│
│                                                  │
│ Logo Preview:                                   │
│ ┌────────────────────────────────────────────┐  │
│ │ [Logo thumbnail appears here]              │  │
│ └────────────────────────────────────────────┘  │
│                                                  │
│ Display diagonal (in)  [13.3]                   │
│ Categories (one per):  [All categories here]    │
│ Group Members (one):   [All members here]       │
│                                                  │
│                              [Save] [Cancel]    │
└──────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Logo Not Showing
**Problem:** Logo appears as placeholder text
**Solutions:**
1. Check logo file exists at the path
2. Use relative path: `./logo.png`
3. Verify file is valid image (PNG/JPG/GIF/BMP)
4. Try absolute path: `/full/path/to/logo.png`

### Path Shows as Invalid
**Problem:** Preview shows "[File not found]"
**Solutions:**
1. Click Browse button instead of typing
2. Use forward slashes: `./images/logo.png` (not backslashes)
3. Put logo file in same folder as app
4. Check file name spelling and case

### Preview Doesn't Update
**Problem:** Changes not reflecting in real-time
**Solutions:**
1. Make sure cursor is still in path field
2. Try clicking elsewhere then back
3. Type slowly to let preview update
4. Use Browse button instead

### Cannot Save Changes
**Problem:** Save button doesn't work
**Solutions:**
1. Check all required fields are filled
2. Make sure display diagonal is a number
3. Try using relative paths
4. Check file permissions in config folder

---

## Example: Change Branding

### Scenario: Rebranding as "TechVend"

**Step 1:** Create new logo image
- Save as `techvend_logo.png`
- Size: 300x100 pixels

**Step 2:** Place logo in project folder
```
raon-vending-rpi4/
├─ techvend_logo.png    ← New logo here
├─ main.py
├─ kiosk_app.py
└─ ...
```

**Step 3:** Open Admin Panel
- Press admin key
- Click "Kiosk Config" button

**Step 4:** Update header
```
Machine Name:    "TechVend"
Subtitle:        "Technology Vending Solutions"
Logo Path:       "./techvend_logo.png"
```

**Step 5:** Click Browse
- Select `techvend_logo.png`
- See preview update
- Click Preview to verify

**Step 6:** Save
- Click Save button
- Restart app to see changes

**Result:**
```
┌────────────────────────────────────────┐
│ [TechVend Logo] TechVend     [Cart]   │
│                 Technology Vending...  │
└────────────────────────────────────────┘
```

---

## Key Differences: Items vs Header

Both are now similarly editable!

| Aspect | Items | Header |
|--------|-------|--------|
| **Edit Location** | Admin → Assign Slots or Manage Items | Admin → Kiosk Config |
| **Image/Logo** | Item images | Header logo |
| **Browse** | N/A (paths only) | Browse button ✓ |
| **Preview** | In cards | Real-time + preview button |
| **Path Type** | Relative paths | Relative or absolute |
| **Easy to Use** | ✓ Yes | ✓ Yes |

---

## Files Modified

| File | Changes |
|------|---------|
| `kiosk_app.py` | Added subtitle display in header |
| `admin_screen.py` | Added logo preview UI and preview methods |
| `config.example.json` | Added machine_name and machine_subtitle fields |

---

## Configuration Examples

### Example 1: Simple Setup
```json
{
  "machine_name": "SnackVend",
  "machine_subtitle": "Quick Snack & Beverage Station",
  "header_logo_path": "./snack_logo.png"
}
```

### Example 2: Corporate
```json
{
  "machine_name": "Corp Tech Center",
  "machine_subtitle": "Employee Vending & Service Hub",
  "header_logo_path": "./corporate_logo.png"
}
```

### Example 3: Campus
```json
{
  "machine_name": "Campus Store",
  "machine_subtitle": "University Vending & Retail",
  "header_logo_path": "./images/campus_badge.png"
}
```

---

## Summary

✅ **Header now shows subtitle** - Full branding support
✅ **Logo editing with preview** - See changes before saving
✅ **Browse button** - Easy file selection
✅ **Real-time preview** - Immediate feedback
✅ **Configuration in admin panel** - Same as item editing
✅ **Similar to item editing** - Consistent user experience

**Everything is ready to customize your vending machine header!**
