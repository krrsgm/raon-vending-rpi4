# Raspberry Pi 4 Wayland Autorun (Landscape + Kiosk)

This setup rotates HDMI output and starts `main.py` automatically:

```bash
wlr-randr --output HDMI-A-1 --transform 270
```

## Files added/updated in this repo
- `deploy/start-kiosk-wayland.sh`
- `raon-vending.service`
- `deploy/raon-vending.service`

## Install on Raspberry Pi

```bash
cd ~/raon-vending-rpi4
sudo cp raon-vending.service /etc/systemd/system/raon-vending.service
sudo systemctl daemon-reload
sudo systemctl enable raon-vending.service
sudo systemctl restart raon-vending.service
```

## Verify

```bash
sudo systemctl status raon-vending.service
sudo journalctl -u raon-vending.service -f
```

## Notes
- The startup script retries `wlr-randr` while the Wayland session comes up, then launches `main.py`.
- `main.py` is started from the boot shell script (`deploy/start-kiosk-wayland.sh`) on every boot.
- The startup script also stops common Raspberry Pi desktop panels (`wf-panel-pi` / `lxpanel`) for taskbar-free kiosk boot.
- `main.py` no longer forces `xrandr -o right`, so the service rotation is not overridden.
- If your repo path is not `/home/raon/raon-vending-rpi4`, update `WorkingDirectory` and `ExecStart` in the service file accordingly.
