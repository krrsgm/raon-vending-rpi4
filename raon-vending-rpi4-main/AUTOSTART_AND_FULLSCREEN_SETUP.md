# Auto-Start and Fullscreen Kiosk Setup Guide

## Overview

The RAON vending machine system is now configured to:
- **Auto-start** automatically when the Raspberry Pi powers on
- **Run in fullscreen mode** without window decorations (no exit, minimize, or maximize buttons)
- **Stay on display** continuously

## Changes Made

### 1. Application Changes (main.py)

**Fullscreen Mode:**
- Application starts in fullscreen by default
- Window decorations removed (no title bar, borders, buttons)
- On Raspberry Pi: Uses splash window type (`-type splash`)
- On Windows: Uses override redirect (`overrideredirect(True)`)

**Before:**
```python
self.is_fullscreen = False  # Started in windowed mode
```

**After:**
```python
self.is_fullscreen = True   # Starts in fullscreen mode
```

### 2. Systemd Service Changes (deploy/raon-vending.service)

**Key improvements:**
- Changed target from `multi-user.target` to `graphical.target`
- Added environment variables for display
- Better restart on failure handling
- Proper kill mode for graceful shutdown

## Installation Steps for Raspberry Pi

### Step 1: Copy the Service File

```bash
sudo cp /home/pi/raon-vending/deploy/raon-vending.service /etc/systemd/system/
```

### Step 2: Set Proper Permissions

```bash
sudo chmod 644 /etc/systemd/system/raon-vending.service
```

### Step 3: Reload Systemd

```bash
sudo systemctl daemon-reload
```

### Step 4: Enable Auto-Start

```bash
sudo systemctl enable raon-vending
```

### Step 5: Start the Service

```bash
sudo systemctl start raon-vending
```

### Step 6: Verify It's Running

```bash
sudo systemctl status raon-vending
```

## Testing the Setup

### Test 1: Verify Service Starts

```bash
sudo systemctl restart raon-vending
```

You should see the fullscreen kiosk app appear within a few seconds.

### Test 2: Check Service Logs

```bash
sudo journalctl -u raon-vending -f
```

This shows real-time logs. Press `Ctrl+C` to exit.

### Test 3: Verify Auto-Boot

```bash
sudo reboot
```

After reboot, the kiosk should automatically start in fullscreen.

## Fullscreen Mode Details

### What Happens in Fullscreen

- ✅ Application takes up entire screen
- ✅ No window title bar visible
- ✅ No minimize/maximize/close buttons
- ✅ Full access to all kiosk functionality
- ✅ Still responsive to keyboard input

### Exiting Fullscreen (Admin Only)

Users can still press:
- **Escape key** - Returns to selection/admin screen
- **Admin key combo** - Access admin panel

### Disabling Fullscreen (Development Only)

To run in windowed mode for testing:

1. Edit `main.py` line 60:
```python
self.is_fullscreen = False  # Change to False for windowed mode
```

2. Restart the application

## Troubleshooting

### Issue: Service doesn't start automatically after reboot

**Solution:**
```bash
# Check if service is enabled
sudo systemctl is-enabled raon-vending

# If not enabled, enable it
sudo systemctl enable raon-vending

# Verify status
sudo systemctl status raon-vending
```

### Issue: Display shows "Active (running)" but app not visible

**Solution:**
```bash
# Check if display is set correctly
echo $DISPLAY

# Manually start with display
DISPLAY=:0 /usr/bin/python3 /home/pi/raon-vending/main.py
```

### Issue: App starts but shows window controls/title bar

**Solution:**
Verify these settings in `main.py`:
- `self.is_fullscreen = True`
- Linux: `self.attributes('-type', 'splash')`
- Windows: `self.overrideredirect(True)`

### Issue: Service keeps restarting

**Solution:**
Check logs for errors:
```bash
sudo journalctl -u raon-vending -n 50 -p err
```

## Managing the Service

### Stop the Service

```bash
sudo systemctl stop raon-vending
```

### Restart the Service

```bash
sudo systemctl restart raon-vending
```

### Disable Auto-Start

```bash
sudo systemctl disable raon-vending
```

### View Service Status

```bash
sudo systemctl status raon-vending
```

### View Recent Logs

```bash
sudo journalctl -u raon-vending -n 100
```

## Important Notes

### Multi-User Considerations

- Service runs as `pi` user (edit service file to change)
- Only one instance can display on the screen at a time
- If display manager is running, it may interfere

### Display Variables

The service sets:
- `DISPLAY=:0` - Primary display
- `XAUTHORITY=/home/pi/.Xauthority` - X11 authentication

Adjust these if using different display configuration.

### Keyboard Input

Even in fullscreen with no decorations:
- All keyboard inputs work normally
- Escape key still functions for navigation
- Admin panel remains accessible

### Log Location

Service logs are stored in systemd journal:
```bash
sudo journalctl -u raon-vending
```

## Configuration

### To Change User (if needed)

Edit `/etc/systemd/system/raon-vending.service`:
```ini
User=your_username
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart raon-vending
```

### To Change Working Directory

Edit `/etc/systemd/system/raon-vending.service`:
```ini
WorkingDirectory=/new/path/to/raon-vending
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart raon-vending
```

## Summary

Your RAON vending machine is now set up to:

✅ **Auto-start** on Raspberry Pi boot
✅ **Run fullscreen** immediately
✅ **Hide all window controls** (clean kiosk look)
✅ **Auto-restart** if the app crashes
✅ **Stay on screen** continuously

The system will provide a professional, uninterrupted kiosk experience!
