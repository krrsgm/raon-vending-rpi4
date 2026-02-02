# Setup Instructions - Directory Structure

This application is designed to work from **any location** without requiring specific path configurations.

## Quick Start

1. **Extract the zip file** anywhere on your system
2. **Copy the data files** to your working directory (see below)
3. **Run the application:**
   ```bash
   cd raon-vending-rpi4
   python3 main.py
   ```

## Directory Structure

### Required Directories and Files

The application needs the following data files. These can be located in **any of these places**:

1. **Home directory** (`~/`) - highest priority
2. **Project root** (where `main.py` is)
3. **Current working directory**

### Essential Files

```
assigned_items.json      - Product slot assignments and data
images/                  - Product images directory
config.json             - Configuration settings
```

### Example Directory Layout

#### Option A: Files in Project Root (Recommended)
```
raon-vending-rpi4/
├── main.py
├── kiosk_app.py
├── fix_paths.py
├── assigned_items.json    ← HERE
├── config.json           ← HERE
├── images/               ← HERE
│   ├── SS1.png
│   ├── FC.png
│   └── ...
└── other_files...
```

#### Option B: Files in Home Directory (Also Works)
```
~/
├── raon-vending-rpi4/
│   ├── main.py
│   ├── kiosk_app.py
│   └── ...
├── assigned_items.json    ← HERE
├── config.json           ← HERE
├── images/               ← HERE
│   ├── SS1.png
│   ├── FC.png
│   └── ...
└── other_files...
```

## Setup on Raspberry Pi

### Step 1: Extract and Navigate
```bash
# Extract the zip file (or git clone)
unzip raon-vending-rpi4-main.zip
cd raon-vending-rpi4
```

### Step 2: Copy Data Files (if not already in project root)
```bash
# If your assigned_items.json and images/ are elsewhere:
cp /path/to/assigned_items.json .
cp -r /path/to/images ./
cp /path/to/config.json .
```

### Step 3: Verify Structure
```bash
ls -la
# Should show: assigned_items.json, config.json, images/, main.py, etc.
```

### Step 4: Run
```bash
python3 main.py
```

## How the App Finds Files

The app uses intelligent path resolution to find files in this order:

1. **Home directory** (`~/`)
2. **Project root** (where the code is)
3. **Current working directory**
4. **Fallback** to project root if not found elsewhere

This means:
- ✅ You can run from any directory
- ✅ You can store data files in home directory
- ✅ You can store data files in the project directory
- ✅ You can have multiple copies running from different locations

## File Locations Reference

| File | Default Location | Searchable In |
|------|---|---|
| `main.py` | Project root | Project root only |
| `assigned_items.json` | Project root | Home, Project root, CWD |
| `images/` | Project root | Home, Project root, CWD |
| `config.json` | Project root | Home, Project root, CWD |
| Product images | `images/SS1.png` | Home/images/, Project root/images/, CWD/images/ |

## Troubleshooting

### "assigned_items.json not found"
Make sure you have copied `assigned_items.json` to one of these locations:
```bash
# Option 1: Home directory
cp assigned_items.json ~/

# Option 2: Project root
cp assigned_items.json ~/raon-vending-rpi4/

# Option 3: Current working directory
cp assigned_items.json .
```

### "Image not found" when running
Make sure the `images/` directory exists in one of these locations:
```bash
# Option 1: Home directory
cp -r images ~/

# Option 2: Project root (recommended)
cp -r images ~/raon-vending-rpi4/

# Option 3: Current working directory
cp -r images .
```

### Different Machines with Different Data
You can run the same code on different machines with different data files:

**Machine 1 (Kiosk Display):**
```bash
# Only needs code
cd ~/kiosk-display/raon-vending-rpi4
python3 main.py  # Uses ~/images and ~/assigned_items.json
```

**Machine 2 (Admin Device):**
```bash
# Only needs code
cd ~/admin/raon-vending-rpi4
python3 main.py  # Uses ~/images and ~/assigned_items.json
```

Both can run with different data without conflicts!

## For GitHub Downloads

When you download this project as a zip file:

1. Extract anywhere
2. Place `assigned_items.json` in the project root or home directory
3. Place `images/` folder in the project root or home directory
4. Place `config.json` in the project root or home directory
5. Run: `python3 main.py`

That's it! No path configuration needed.
