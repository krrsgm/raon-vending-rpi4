"""Utilities for auto-detecting the Arduino Uno serial device."""

import os

try:
    from serial.tools import list_ports
except Exception:
    list_ports = None


def detect_arduino_serial_port(preferred_port=None):
    """Return best-effort serial port path for Arduino Uno, or None if not found."""
    if preferred_port:
        try:
            # Keep explicitly provided port if it exists or is a Windows COM port.
            if preferred_port.upper().startswith("COM") or os.path.exists(preferred_port):
                return preferred_port
        except Exception:
            pass

    if not list_ports:
        return None

    ports = list(list_ports.comports())
    if not ports:
        return None

    # Prioritize Arduino-like descriptors first.
    keywords = (
        "arduino",
        "uno",
        "ch340",
        "cp210",
        "usb serial",
        "silicon labs",
    )
    for p in ports:
        desc = f"{p.description or ''} {p.manufacturer or ''} {p.product or ''}".lower()
        if any(k in desc for k in keywords):
            return p.device

    # Then prefer common Linux USB serial patterns.
    for p in ports:
        dev = (p.device or "").lower()
        if "/dev/ttyacm" in dev or "/dev/ttyusb" in dev:
            return p.device

    # Fallback to first available serial device.
    return ports[0].device

