Desktop Autostart Fix

Use this if the kiosk does not start on boot, but it does start after:

```bash
sudo systemctl restart raon-vending
```

That behavior usually means the system service is starting before the Raspberry Pi desktop session is ready.

Install desktop-session autostart instead:

```bash
cd /home/raon/raon-vending-rpi4
bash deploy/install-desktop-autostart.sh
sudo systemctl disable --now raon-vending
```

What it does:
- Creates `~/.config/autostart/raon-vending.desktop`
- Launches `deploy/start-kiosk-wayland.sh` after desktop login
- Avoids early-boot Wayland timing issues

After installing:

```bash
reboot
```
