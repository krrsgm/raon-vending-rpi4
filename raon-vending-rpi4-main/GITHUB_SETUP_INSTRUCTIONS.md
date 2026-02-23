# GitHub Setup Instructions

## Step 1: Create a GitHub Repository
1. Go to https://github.com/new
2. Name it: `raon-vending-rpi4` (or your preferred name)
3. Add description: "Raspberry Pi 4 Vending Machine Controller"
4. Choose Public or Private
5. Click "Create repository"

## Step 2: Push Your Code to GitHub

On your Windows machine, open PowerShell in your project folder and run:

```powershell
cd C:\Users\ricar\OneDrive\Documents\raon-vending-rpi4
git init
git add .
git commit -m "Initial commit: Vending machine application for Raspberry Pi 4"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/raon-vending-rpi4.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your actual GitHub username.

## Step 3: Download on Raspberry Pi

Now on your Raspberry Pi, you can simply:

```bash
cd ~/Desktop
git clone https://github.com/YOUR_USERNAME/raon-vending-rpi4.git
cd raon-vending-rpi4
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-rpi4.txt
python3 main.py
```

Or download as ZIP from the GitHub release page and extract it.

## Benefits
✅ Easy to download and update
✅ Version control for changes
✅ Share with team members
✅ Easy rollback if needed
✅ All files in one place
