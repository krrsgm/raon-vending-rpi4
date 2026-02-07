# GitHub Repository Setup Guide

This guide will help you create a new GitHub repository with all RPi4-optimized code.

## Prerequisites

- GitHub account
- Git installed on your development machine
- Access to the current THESIS directory

## Steps to Create Repository

### 1. Create New Repository on GitHub

1. Go to https://github.com/new
2. Repository name: `raon-vending-rpi4`
3. Description: "Raspberry Pi 4 Vending Machine Kiosk - Coin/Bill Payment, Touchscreen UI"
4. Visibility: Public (or Private as needed)
5. **Do NOT** initialize with README, gitignore, or license (we have these)
6. Click "Create repository"

### 2. Initialize Local Git Repository

```bash
cd /path/to/THESIS
git init
git add .
git commit -m "Initial commit: Raspberry Pi 4 optimized vending machine kiosk"
```

### 3. Connect to GitHub

```bash
# Replace USERNAME and REPO with your GitHub username and repo name
git remote add origin https://github.com/USERNAME/raon-vending-rpi4.git
git branch -M main
git push -u origin main
```

### 4. Create Additional Branches (Optional)

```bash
# Development branch for new features
git checkout -b develop
git push -u origin develop

# Release/staging branch
git checkout -b staging
git push -u origin staging

# Return to main
git checkout main
```

## Repository Structure

The repository should contain:

```
raon-vending-rpi4/
├── .github/
│   └── workflows/
│       ├── test.yml           # CI/CD tests
│       └── setup-docs.yml     # Documentation automation
├── docs/
│   ├── INSTALLATION.md        # Detailed installation guide
│   ├── HARDWARE_SETUP.md      # Hardware wiring diagrams
│   ├── GPIO_PINOUT.md         # Complete GPIO reference
│   ├── TROUBLESHOOTING.md     # Common issues and solutions
│   └── API.md                 # Code API reference
├── scripts/
│   ├── setup-rpi4.sh          # Automated setup
│   ├── install-deps.sh        # Dependency installation
│   └── run-kiosk.sh           # Launch kiosk mode
├── config/
│   ├── config.example.json    # Example configuration
│   └── pins.json              # GPIO pin definitions
├── src/
│   ├── __init__.py
│   ├── main.py               # Entry point
│   ├── ui/
│   │   ├── kiosk_app.py
│   │   ├── screens/
│   │   │   ├── selection_screen.py
│   │   │   ├── item_screen.py
│   │   │   ├── cart_screen.py
│   │   │   ├── admin_screen.py
│   │   │   └── assign_items_screen.py
│   ├── hardware/
│   │   ├── coin_handler.py
│   │   ├── coin_hopper.py
│   │   ├── bill_acceptor.py
│   │   ├── dht11_handler.py
│   │   └── esp32_client.py
│   ├── core/
│   │   ├── payment_handler.py
│   │   ├── fix_paths.py
│   │   └── rpi_gpio_mock.py
│   └── utils/
│       ├── simulate_coin.py
│       └── test_coin_acceptor.py
├── tests/
│   ├── test_coin.py
│   ├── test_bill.py
│   ├── test_sensors.py
│   └── test_payment.py
├── .gitignore               # Git ignore file
├── .github/
├── LICENSE                  # License file (MIT, GPL, etc.)
├── README.md               # Main README
├── README-RPi4.md          # RPi4-specific README
├── requirements.txt         # Core dependencies
├── requirements-rpi4.txt    # RPi4 dependencies
├── setup-rpi4.sh           # Setup script
├── CHANGELOG.md             # Version history
├── CONTRIBUTING.md         # Contribution guidelines
└── setup.py                # Python package setup (optional)
```

## Create .gitignore

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Raspberry Pi specific
/venv-rpi4/
*.log

# Application data
config.json
item_list.json
assigned_items.json
*.db

# Testing
.pytest_cache/
.coverage
htmlcov/

# Temporary
*.tmp
*.bak
EOF
git add .gitignore
git commit -m "Add gitignore"
```

## Create LICENSE

```bash
# MIT License example
cat > LICENSE << 'EOF'
MIT License

Copyright (c) 2025 [Your Name/Organization]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
EOF
git add LICENSE
git commit -m "Add MIT License"
```

## Setup GitHub Actions (Optional but Recommended)

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, '3.10', 3.11]
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest black
    - name: Lint with black
      run: black --check .
    - name: Test with pytest
      run: pytest tests/
```

## Push to GitHub

```bash
git push -u origin main
```

## Create Release/Tags

```bash
# Tag a release
git tag -a v1.0.0 -m "Initial release for Raspberry Pi 4"
git push origin v1.0.0

# Create release on GitHub (or via web interface)
```

## Repository Documentation

Create these additional documentation files:

1. **INSTALLATION.md** - Step-by-step installation
2. **HARDWARE_SETUP.md** - Wiring diagrams and schematics
3. **GPIO_PINOUT.md** - Complete GPIO reference table
4. **TROUBLESHOOTING.md** - Common issues and solutions
5. **API.md** - Developer API documentation
6. **CONTRIBUTING.md** - How to contribute

## Set Repository Topics

Go to GitHub repository settings and add topics:
- `raspberry-pi`
- `rpi4`
- `vending-machine`
- `kiosk`
- `payment`
- `tkinter`
- `gpio`
- `iot`

## Collaborate

Share the repository URL with your team:
```
https://github.com/USERNAME/raon-vending-rpi4
```

## Keep It Updated

Regular maintenance:

```bash
# Pull latest changes from GitHub
git pull origin main

# Make changes and commit
git add .
git commit -m "Description of changes"

# Push to GitHub
git push origin main
```

---

For more information on GitHub workflows and best practices, see:
- https://docs.github.com/en/get-started
- https://github.com/github/gitignore
