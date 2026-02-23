# ✅ Fullscreen & Autostart Setup - Complete Guide

## Current Status

✅ **Fullscreen Mode:** Already enabled in your code
```json
"always_fullscreen": true,
"allow_decorations_for_admin": false
```

✅ **No Window Decorations:** Configured in main.py
- No minimize button
- No maximize button  
- No close button
- No title bar
- No window controls

⏳ **Autostart:** Ready to enable on your Raspberry Pi

---

## Quick Setup (5 Minutes)

### On Your Raspberry Pi

Copy and paste these commands:

```bash
# 1. Copy service file to system directory
sudo cp ~/raon-vending-rpi4/raon-vending.service /etc/systemd/system/

# 2. Set permissions
sudo chmod 644 /etc/systemd/system/raon-vending.service

# 3. Enable service to run at boot
sudo systemctl daemon-reload
sudo systemctl enable raon-vending.service

# 4. Start it now (optional - for testing)
sudo systemctl start raon-vending.service

# 5. Check status
sudo systemctl status raon-vending.service
```

**That's it!** 🎉

---

## What Happens Now

### On Every Boot

1. Raspberry Pi starts
2. Desktop/display manager loads (Xfce, LXDE, etc.)
3. After 5-10 seconds: Vending machine app launches
4. Application takes full screen automatically
5. No window decorations visible
6. True kiosk mode experience

### If Application Crashes

Application automatically restarts within 10 seconds.

### View What's Happening

```bash
# Real-time logs
sudo journalctl -u raon-vending.service -f

# Last 30 lines
sudo journalctl -u raon-vending.service -n 30
```

---

## Fullscreen Details

### What User Sees

```
┌─────────────────────────────────────────┐
│                                         │
│    RAON Vending Machine                │
│                                         │
│  [Category Buttons]  [Products Grid]   │
│                                         │
│  [Cart Info]         [Payment Button]  │
│                                         │
│                                         │
└─────────────────────────────────────────┘

✓ Full screen edge to edge
✓ No taskbar
✓ No window controls
✓ No minimize/maximize/close buttons
✓ No title bar
✓ No menus or decorations
```

### How It Works (Technical)

**On Raspberry Pi (Linux):**
```python
self.attributes('-type', 'splash')  # Removes window decorations
self.attributes('-zoomed', '1')     # Maximizes window
```

**On Windows (for testing):**
```python
self.overrideredirect(True)         # Removes all decorations
```

---

## Control Methods

### Keyboard Navigation

| Key | Action |
|-----|--------|
| **Escape** | Return to Selection screen (or admin menu) |
| **Arrow Keys** | Navigate product grid |
| **Enter** | Select item |
| **Number Keys** | Quick navigation (if configured) |

### Mouse

- ✅ Click products to view details
- ✅ Click "Add to Cart" button
- ✅ Click category filters
- ✅ Click "Checkout" / "Payment" buttons

---

## Troubleshooting

### "Application doesn't appear after boot"

**Check if service is running:**
```bash
sudo systemctl status raon-vending.service
```

**Check logs for errors:**
```bash
sudo journalctl -u raon-vending.service -n 50
```

**Start manually to see errors:**
```bash
python3 ~/raon-vending-rpi4/main.py
```

### "Want to stop/pause application"

```bash
sudo systemctl stop raon-vending.service

# Then restart
sudo systemctl start raon-vending.service

# Or reboot
sudo reboot
```

### "Want to disable autostart temporarily"

```bash
sudo systemctl disable raon-vending.service
sudo reboot

# Re-enable later with
sudo systemctl enable raon-vending.service
```

### "Application exits unexpectedly"

The service will auto-restart within 10 seconds. Check:
```bash
sudo journalctl -u raon-vending.service -f
# Look for error messages
```

---

## Service Management

### Common Commands

```bash
# Start the application
sudo systemctl start raon-vending.service

# Stop the application
sudo systemctl stop raon-vending.service

# Restart the application
sudo systemctl restart raon-vending.service

# Check if it's running
sudo systemctl status raon-vending.service

# Enable autostart at boot
sudo systemctl enable raon-vending.service

# Disable autostart at boot
sudo systemctl disable raon-vending.service

# View logs in real-time
sudo journalctl -u raon-vending.service -f

# View last 100 lines of logs
sudo journalctl -u raon-vending.service -n 100

# View logs from the last hour
sudo journalctl -u raon-vending.service --since "1 hour ago"
```

---

## Advanced Configuration

### Customize Service Behavior

Edit `/etc/systemd/system/raon-vending.service`:

```bash
sudo nano /etc/systemd/system/raon-vending.service
```

**Key settings to adjust:**

```ini
# Restart policy
Restart=on-failure          # Restart if exits with error
RestartSec=10               # Wait 10 seconds before restart

# Logging
StandardOutput=journal      # Log to system journal
StandardError=journal

# User to run as
User=pi                     # User account to run as

# Working directory
WorkingDirectory=/home/pi/raon-vending-rpi4

# Environment variables
Environment="DISPLAY=:0"    # X11 display
Environment="XAUTHORITY=/home/pi/.Xauthority"
```

After editing:
```bash
sudo systemctl daemon-reload
sudo systemctl restart raon-vending.service
```

---

## Verification Checklist

After setup, verify:

- [ ] Application appears on screen after boot
- [ ] No window title bar visible
- [ ] No minimize/maximize/close buttons
- [ ] Full screen (no taskbar visible)
- [ ] Keyboard navigation works
- [ ] Mouse clicks work
- [ ] All features functional

---

## What's Installed on GitHub

1. **raon-vending.service** - Systemd service file
2. **main.py** - Already has fullscreen mode enabled
3. **config.json** - Fullscreen settings

---

## Summary

| Feature | Status | Details |
|---------|--------|---------|
| Fullscreen | ✅ Active | Always full screen, no decorations |
| Autostart | ✅ Ready | Copy service file and enable |
| Auto-restart | ✅ Built-in | Restarts within 10 seconds if crashed |
| Logging | ✅ Built-in | View with `journalctl` |
| Configuration | ✅ Easy | Edit config.json to customize |

---

## Next Steps

1. **Copy the service file:**
   ```bash
   sudo cp ~/raon-vending-rpi4/raon-vending.service /etc/systemd/system/
   ```

2. **Enable autostart:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable raon-vending.service
   ```

3. **Test it:**
   ```bash
   sudo systemctl start raon-vending.service
   ```

4. **Reboot to confirm:**
   ```bash
   sudo reboot
   ```

Done! Your kiosk is now ready for production. 🚀
