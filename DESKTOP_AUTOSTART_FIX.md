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
sudo systemctl disable --now raon-web-app
```

What it does:
- Creates `~/.config/autostart/raon-vending.desktop`
- Creates `~/.config/autostart/raon-web-app.desktop`
- Launches `deploy/start-kiosk-wayland.sh` after desktop login
- Launches `deploy/start-web-app.sh` in a terminal after desktop login
- Avoids early-boot Wayland timing issues

After installing:

```bash
reboot
```
