#!/usr/bin/env bash
set -euo pipefail

# One-shot installer for boot autostart services:
# - raon-vending.service (main.py kiosk UI)
# - raon-web-app.service (web_app.py background server)

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  echo "Run with sudo:"
  echo "  sudo bash deploy/install-autostart-services.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

TARGET_USER="${SUDO_USER:-raon}"
TARGET_HOME="$(eval echo "~$TARGET_USER")"

if [ -z "$TARGET_HOME" ] || [ ! -d "$TARGET_HOME" ]; then
  echo "Could not resolve home directory for user: $TARGET_USER"
  exit 1
fi

if [ ! -f "$REPO_DIR/main.py" ] || [ ! -f "$REPO_DIR/web_app.py" ]; then
  echo "Repo path looks invalid: $REPO_DIR"
  exit 1
fi

KIOSK_START="$REPO_DIR/deploy/start-kiosk-wayland.sh"
WEB_START="$REPO_DIR/deploy/start-web-app.sh"

if [ ! -f "$KIOSK_START" ] || [ ! -f "$WEB_START" ]; then
  echo "Missing startup scripts in deploy/:"
  echo "  $KIOSK_START"
  echo "  $WEB_START"
  exit 1
fi

# Normalize CRLF to LF to avoid /bin/bash ^M failures.
sed -i 's/\r$//' "$KIOSK_START" "$WEB_START"
chmod +x "$KIOSK_START" "$WEB_START"
chown "$TARGET_USER":"$TARGET_USER" "$KIOSK_START" "$WEB_START" || true

cat > /etc/systemd/system/raon-vending.service <<EOF
[Unit]
Description=RAON Vending Machine Kiosk - Automatic Startup
After=network.target display-manager.service graphical.target

[Service]
Type=simple
User=$TARGET_USER
Group=$TARGET_USER
Environment="DISPLAY=:0"
Environment="XAUTHORITY=$TARGET_HOME/.Xauthority"
WorkingDirectory=$REPO_DIR
ExecStart=/bin/bash $KIOSK_START
Restart=on-failure
RestartSec=5
KillMode=process
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=graphical.target
EOF

cat > /etc/systemd/system/raon-web-app.service <<EOF
[Unit]
Description=RAON Web App (Flask) - Automatic Startup
Wants=network-online.target
After=network-online.target hostapd.service dnsmasq.service

[Service]
Type=simple
User=$TARGET_USER
Group=$TARGET_USER
WorkingDirectory=$REPO_DIR
Environment="PYTHONUNBUFFERED=1"
Environment="WEB_DYNAMIC_IP=true"
Environment="WEB_WIFI_INTERFACES=wlan0,ap0,uap0"
ExecStart=/bin/bash $WEB_START
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable raon-vending raon-web-app
systemctl restart raon-vending raon-web-app

echo
echo "Installed and restarted services:"
echo "  - raon-vending (main.py kiosk)"
echo "  - raon-web-app (web_app.py)"
echo
echo "Check status:"
echo "  sudo systemctl status raon-vending --no-pager -l"
echo "  sudo systemctl status raon-web-app --no-pager -l"
