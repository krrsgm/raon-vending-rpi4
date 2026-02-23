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
