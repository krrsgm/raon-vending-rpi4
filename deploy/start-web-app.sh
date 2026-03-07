#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

WIFI_INTERFACES_RAW="${WEB_WIFI_INTERFACES:-wlan0,ap0,uap0}"
IFS=',' read -r -a WIFI_INTERFACES <<< "$WIFI_INTERFACES_RAW"

wait_for_wifi_ip() {
  local tries=60
  local delay=1
  local iface
  local trimmed

  while [ "$tries" -gt 0 ]; do
    for iface in "${WIFI_INTERFACES[@]}"; do
      trimmed="$(echo "$iface" | xargs)"
      [ -z "$trimmed" ] && continue
      if ip -4 -o addr show dev "$trimmed" 2>/dev/null | grep -q ' inet '; then
        echo "Detected IPv4 on interface $trimmed"
        return 0
      fi
    done
    tries=$((tries - 1))
    sleep "$delay"
  done

  echo "No Wi-Fi/AP interface IPv4 detected after waiting. Starting web_app.py anyway."
  return 1
}

wait_for_wifi_ip || true

if [ -x "$REPO_DIR/venv/bin/python3" ]; then
  exec "$REPO_DIR/venv/bin/python3" "$REPO_DIR/web_app.py"
fi

exec /usr/bin/python3 "$REPO_DIR/web_app.py"
