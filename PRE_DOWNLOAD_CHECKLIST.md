# Pre-Download Checklist

## What's Included in the GitHub Zip

When you download the zip from GitHub, you get:

✅ All Python code files  
✅ Configuration examples  
✅ Documentation  
✅ Setup instructions  

## What You Need to Add

Before running the app for the first time, ensure you have:

- [ ] **`assigned_items.json`** - Product slot definitions
- [ ] **`images/` folder** - Product images
- [ ] **`config.json`** - Configuration settings (or use defaults)

## Where to Put These Files

### Option 1: Project Root (Recommended)
Place them in the same folder as `main.py`:
```
raon-vending-rpi4/
├── main.py
├── assigned_items.json      ← Place here
├── images/                  ← Place here
├── config.json             ← Place here
└── other_files...
```

### Option 2: Home Directory
Place them in your home directory:
```
~/
├── assigned_items.json      ← Or place here
├── images/                  ← Or place here
├── config.json             ← Or place here
└── raon-vending-rpi4/
    ├── main.py
    └── other_files...
```

### Option 3: Mixed
Some in home, some in project root - **the app will find them!**

## Quick Setup

```bash
# 1. Extract the zip
unzip raon-vending-rpi4-main.zip
cd raon-vending-rpi4

# 2. Copy your data files
cp /path/to/assigned_items.json .
cp -r /path/to/images .
cp /path/to/config.json .

# 3. Run
python3 main.py
```

## Verification

Before running, verify you have everything:

```bash
# Check project root
ls -la | grep assigned_items.json
ls -la | grep images
ls -la | grep config.json

# Should show files/directories

# Then run
python3 main.py
```

## If Files Are Missing

The app will:
- ✅ Search your home directory
- ✅ Search the project root
- ✅ Search the current directory
- ✅ Use defaults if config.json is missing

But **product images require the `images/` folder** to be in at least one of these locations.

## No Configuration Needed

The app automatically finds files in the right locations.  
You don't need to edit any paths or configuration.  
Just make sure the files exist somewhere!

---

**Ready to download?** Make sure you have the data files above, and you're all set! 🚀
