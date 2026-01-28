# Vending Machine UI

This repository contains a Tkinter-based kiosk UI for a vending machine used in a thesis project.

Contents
- `main.py` - Application entry point
- `kiosk_app.py` - Kiosk UI and item display
- `admin_screen.py` - Admin interface for adding items and categories
- `item_screen.py`, `cart_screen.py` - Item details and cart handling
- `rpi_gpio_mock.py` - Mock GPIO interface for desktop development

Quick start (Windows)
1. Create and activate a virtual environment (optional but recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run the app:

```powershell
python main.py
```

Notes
- The UI uses Tkinter (standard library) and Pillow for image handling. On Raspberry Pi, install the real `RPi.GPIO` package on the device; `rpi_gpio_mock.py` lets you run locally on Windows.
- Configuration is stored in `config.json` (created automatically on first run if missing).

License
This project is licensed under the MIT License - see `LICENSE` for details.
