Install helpers for Raspberry Pi

Files added:
- raon-vending.service — systemd unit to run the kiosk as a service
- 99-raon-serial.rules — udev rule to give dialout access and a stable symlink for common USB serial devices

How to install (on the Pi):

1. Copy files into place (run as root):

   sudo cp deploy/raon-vending.service /etc/systemd/system/raon-vending.service
   sudo cp deploy/99-raon-serial.rules /etc/udev/rules.d/99-raon-serial.rules

2. Reload udev rules and trigger:

   sudo udevadm control --reload-rules
   sudo udevadm trigger

3. Enable and start the systemd service:

   sudo systemctl daemon-reload
   sudo systemctl enable raon-vending
   sudo systemctl start raon-vending

4. Logs and troubleshooting:

   sudo journalctl -u raon-vending -f

Notes:
- Adjust the `User` and `WorkingDirectory` in the service file to match where you clone the repo on your Pi.
- The udev rule attempts to match common USB-serial vendor/product IDs (Arduino, CP210x, FTDI). If your board is a different clone, check `lsusb` and add a rule for that idVendor/idProduct.
- The repo already contains `setup-rpi4.sh` and `requirements-rpi4.txt` for package installation; run `setup-rpi4.sh` after cloning to prepare the Pi.

Web app background startup (web_app.py):

1. Install the web app service and startup script:

   sudo cp deploy/raon-web-app.service /etc/systemd/system/raon-web-app.service
   sudo cp deploy/start-web-app.sh /home/raon/raon-vending-rpi4/deploy/start-web-app.sh
   sudo chmod +x /home/raon/raon-vending-rpi4/deploy/start-web-app.sh

2. Reload systemd, enable and start:

   sudo systemctl daemon-reload
   sudo systemctl enable raon-web-app
   sudo systemctl restart raon-web-app

3. Check status/logs:

   sudo systemctl status raon-web-app --no-pager
   sudo journalctl -u raon-web-app -f

Notes:
- `start-web-app.sh` automatically prefers `/home/raon/raon-vending-rpi4/venv/bin/python3` and falls back to `/usr/bin/python3`.
- It waits for an IPv4 on one of `wlan0,ap0,uap0` before launching `web_app.py`.
- If you do not want the kiosk app (`raon-vending.service`) and web app together, disable the one you do not use.
