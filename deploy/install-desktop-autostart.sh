#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_USER="${SUDO_USER:-$(whoami)}"
TARGET_HOME="$(eval echo "~$TARGET_USER")"
AUTOSTART_DIR="$TARGET_HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/raon-vending.desktop"
KIOSK_START="$REPO_DIR/deploy/start-kiosk-wayland.sh"

if [ ! -f "$REPO_DIR/main.py" ]; then
  echo "Repo path looks invalid: $REPO_DIR"
  exit 1
fi

if [ ! -f "$KIOSK_START" ]; then
  echo "Missing startup script: $KIOSK_START"
  exit 1
fi

mkdir -p "$AUTOSTART_DIR"
sed -i 's/\r$//' "$KIOSK_START"
chmod +x "$KIOSK_START"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=RAON Vending Kiosk
Comment=Start RAON vending kiosk on desktop login
Exec=/bin/bash $KIOSK_START
Path=$REPO_DIR
Terminal=false
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

chown "$TARGET_USER":"$TARGET_USER" "$DESKTOP_FILE" "$KIOSK_START" || true

echo
echo "Installed desktop autostart:"
echo "  $DESKTOP_FILE"
echo
echo "Recommended: disable the system service to avoid duplicate launches:"
echo "  sudo systemctl disable --now raon-vending"
echo
echo "Then reboot or log out and log back in."
