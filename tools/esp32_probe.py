#!/usr/bin/env python3
"""
tools/esp32_probe.py
Quickly probe common serial device nodes and the default AP TCP host (192.168.4.1:5000)
for an ESP32 vending controller that speaks the simple text commands (STATUS/PULSE).

Usage (on the machine running the kiosk):
    python3 tools/esp32_probe.py

This script will:
 - Enumerate common serial device names (/dev/ttyUSB*, /dev/ttyACM* on Linux; COM ports on Windows)
 - Attempt to open each port at 115200 baud and send a "STATUS\n" command
 - Attempt a TCP connection to 192.168.4.1:5000 and send "STATUS\n"

Output is printed to stdout.

Note: Requires `pyserial` for serial probing. Install with `pip3 install pyserial`.
"""

import sys
import socket
import time
import platform

try:
    import serial
    import serial.tools.list_ports
except Exception:
    serial = None

DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 1.0
TCP_HOSTS = ["192.168.4.1"]
TCP_PORT = 5000


def probe_tcp(host, port=TCP_PORT, timeout=1.0):
    print(f"Probing TCP {host}:{port}...", end=' ')
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.sendall(b"STATUS\n")
            s.settimeout(timeout)
            try:
                resp = s.recv(1024)
                if resp:
                    print("OK ->", resp.decode('utf-8', errors='ignore').strip())
                else:
                    print("No response")
            except socket.timeout:
                print("Timed out waiting for response")
    except Exception as e:
        print("Error:", e)


def probe_serial_port(port_name, baud=DEFAULT_BAUD, timeout=DEFAULT_TIMEOUT):
    print(f"Probing serial {port_name} @ {baud}...", end=' ')
    if serial is None:
        print("pyserial not installed")
        return
    try:
        with serial.Serial(port_name, baudrate=baud, timeout=timeout) as ser:
            # flush any startup text
            time.sleep(0.05)
            ser.reset_input_buffer()
            ser.write(b"STATUS\n")
            # short wait for device to respond
            start = time.time()
            line = b""
            while time.time() - start < timeout:
                chunk = ser.readline()
                if chunk:
                    line = chunk
                    break
            if line:
                print("OK ->", line.decode('utf-8', errors='ignore').strip())
            else:
                print("No response (check device, baud, or permissions)")
    except Exception as e:
        print("Error:", e)


def list_serial_candidates():
    candidates = []
    sys_platform = platform.system()
    if sys_platform == 'Windows':
        # Use pyserial to list COM ports if available
        if serial is not None:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            candidates.extend(ports)
        else:
            # fallback common range
            candidates.extend([f"COM{i}" for i in range(1, 21)])
    else:
        # Linux / macOS
        # try pyserial list first
        if serial is not None:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            candidates.extend(ports)
        # add common device nodes
        common = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyS0"]
        for p in common:
            if p not in candidates:
                candidates.append(p)
    return candidates


def main():
    print("ESP32 probe utility\n")
    # Probe TCP hosts first
    for h in TCP_HOSTS:
        probe_tcp(h, TCP_PORT, timeout=DEFAULT_TIMEOUT)

    # Probe serial candidates
    candidates = list_serial_candidates()
    print("\nSerial candidates:")
    for p in candidates:
        probe_serial_port(p)

    print("\nProbe complete. If you see a responding port, update your `config.json` with\n`\"esp32_host\": \"serial:/dev/ttyUSB0\"` (or the responding device).\nIf no ports respond, check that the ESP32 is powered, connected over USB, has the vending firmware loaded, and that you have permission to access the serial device (add your user to 'dialout' on Linux).")

if __name__ == '__main__':
    main()
