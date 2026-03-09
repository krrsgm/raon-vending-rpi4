#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

# Ensure Wayland runtime variables are available when started by systemd.
if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi

wait_for_graphical_session() {
  local max_attempts=60
  local attempt=0

  while [ "$attempt" -lt "$max_attempts" ]; do
    if [ -d "$XDG_RUNTIME_DIR" ]; then
      if [ -S "$XDG_RUNTIME_DIR/wayland-0" ] || [ -S "$XDG_RUNTIME_DIR/wayland-1" ]; then
        return 0
      fi
    fi

    if [ -S /tmp/.X11-unix/X0 ] || [ -f "${XAUTHORITY:-}" ]; then
      return 0
    fi

    attempt=$((attempt + 1))
    sleep 1
  done

  echo "Graphical session was not ready after ${max_attempts}s" >&2
  return 1
}

wait_for_graphical_session

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

# Keep touchscreen orientation in sync with portrait display rotation.
# Rotation mapping here matches 270 degrees (clockwise) output transform.
apply_touch_rotation_x11() {
  if ! command -v xinput >/dev/null 2>&1; then
    return 0
  fi

  local touch_matrix="0 1 0 -1 0 1 0 0 1"
  local calib_matrix="0 1 0 -1 0 1"
  local device_found=1

  while IFS= read -r device; do
    [ -z "$device" ] && continue
    device_found=0
    xinput set-prop "$device" "Coordinate Transformation Matrix" $touch_matrix >/dev/null 2>&1 || true
    xinput set-prop "$device" "libinput Calibration Matrix" $calib_matrix >/dev/null 2>&1 || true
  done < <(
    xinput --list --name-only 2>/dev/null | grep -Ei "touch|touchscreen|goodix|elan|ft5x06|waveshare|egalax" || true
  )

  return $device_found
}

# Retry touch rotation because touch devices can appear a bit later than display init.
for _ in $(seq 1 12); do
  if apply_touch_rotation_x11; then
    break
  fi
  sleep 1
done

# Hide desktop taskbar/panel for kiosk mode (Wayland and X11 variants).
for _ in $(seq 1 10); do
  pkill -x wf-panel-pi >/dev/null 2>&1 || true
  pkill -x lxpanel >/dev/null 2>&1 || true
  sleep 0.5
done

exec /usr/bin/python3 "$REPO_DIR/main.py"
