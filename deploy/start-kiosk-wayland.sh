#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

# Ensure Wayland runtime variables are available when started by systemd.
if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi

if [ -z "${WAYLAND_DISPLAY:-}" ]; then
  for socket in wayland-1 wayland-0; do
    if [ -S "$XDG_RUNTIME_DIR/$socket" ]; then
      export WAYLAND_DISPLAY="$socket"
      break
    fi
  done
fi

# Try rotating display before launching the kiosk app.
if command -v wlr-randr >/dev/null 2>&1; then
  for _ in $(seq 1 15); do
    if [ -n "${WAYLAND_DISPLAY:-}" ] && wlr-randr --output HDMI-A-1 --transform 270; then
      break
    fi
    sleep 1
  done
fi

# Hide desktop taskbar/panel for kiosk mode (Wayland and X11 variants).
for _ in $(seq 1 10); do
  pkill -x wf-panel-pi >/dev/null 2>&1 || true
  pkill -x lxpanel >/dev/null 2>&1 || true
  sleep 0.5
done

exec /usr/bin/python3 "$REPO_DIR/main.py"
