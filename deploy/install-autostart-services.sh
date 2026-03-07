#!/usr/bin/env bash
set -euo pipefail

# One-shot installer for boot autostart service:
# - raon-vending.service (main.py kiosk UI)

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

if [ ! -f "$REPO_DIR/main.py" ]; then
  echo "Repo path looks invalid: $REPO_DIR"
  exit 1
fi

KIOSK_START="$REPO_DIR/deploy/start-kiosk-wayland.sh"

if [ ! -f "$KIOSK_START" ]; then
  echo "Missing startup scripts in deploy/:"
  echo "  $KIOSK_START"
  exit 1
fi

# Normalize CRLF to LF to avoid /bin/bash ^M failures.
sed -i 's/\r$//' "$KIOSK_START"
chmod +x "$KIOSK_START"
chown "$TARGET_USER":"$TARGET_USER" "$KIOSK_START" || true

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

systemctl daemon-reload
systemctl enable raon-vending
systemctl restart raon-vending

# Cleanup old web app service if it exists from previous setup.
if systemctl list-unit-files | grep -q '^raon-web-app\.service'; then
  systemctl disable --now raon-web-app || true
  rm -f /etc/systemd/system/raon-web-app.service
  systemctl daemon-reload
fi

echo
echo "Installed and restarted service:"
echo "  - raon-vending (main.py kiosk)"
echo
echo "Check status:"
echo "  sudo systemctl status raon-vending --no-pager -l"
