"""
esp32_client.py
Helper functions to send commands to the ESP32 vending controller (TCP text commands).

Usage example from kiosk code:
    from esp32_client import pulse_slot
    pulse_slot('192.168.1.100', 12, 800)

The module sends a single-line command and reads a single-line response.
"""
import socket
import sys
import time
try:
    import serial
except Exception:
    serial = None

DEFAULT_PORT = 5000


def send_command(host, cmd, port=DEFAULT_PORT, timeout=2.0):
    """Send a command string to ESP32 and return response (strip newlines)."""
    # If host is a serial URI like 'serial:/dev/ttyUSB0' use UART transport
    if isinstance(host, str) and host.startswith('serial:'):
        if serial is None:
            raise RuntimeError('pyserial is required for serial transport but is not installed')
        port_name = host.split(':', 1)[1]
        # Open/close per command to keep simple and stateless
        try:
            with serial.Serial(port_name, baudrate=115200, timeout=timeout) as ser:
                ser.write((cmd.strip() + '\n').encode('utf-8'))
                # small pause to let device respond
                time.sleep(0.01)
                try:
                    line = ser.readline()
                    if not line:
                        return ''
                    return line.decode('utf-8', errors='ignore').strip()
                except Exception:
                    return ''
        except Exception:
            raise

    # Default: TCP transport
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            s.sendall((cmd.strip() + "\n").encode('utf-8'))
            # Attempt to read a line; the server may or may not respond
            s.settimeout(timeout)
            try:
                resp = s.recv(1024)
                if not resp:
                    return ''
                return resp.decode('utf-8', errors='ignore').strip()
            except socket.timeout:
                return ''
    except Exception as e:
        raise


def pulse_slot(host, slot, ms=800, port=DEFAULT_PORT):
    """Pulse a slot number (1-based) for ms milliseconds."""
    cmd = f"PULSE {int(slot)} {int(ms)}"
    return send_command(host, cmd, port=port)


def open_slot(host, slot, port=DEFAULT_PORT):
    return send_command(host, f"OPEN {int(slot)}", port=port)


def close_slot(host, slot, port=DEFAULT_PORT):
    return send_command(host, f"CLOSE {int(slot)}", port=port)


def status(host, port=DEFAULT_PORT):
    return send_command(host, "STATUS", port=port)


if __name__ == '__main__':
    # simple CLI
    if len(sys.argv) < 3:
        print('Usage: esp32_client.py <host> <cmd> [args...]')
        print('Commands: pulse <slot> <ms> | open <slot> | close <slot> | status')
        sys.exit(1)
    host = sys.argv[1]
    cmd = sys.argv[2].lower()
    try:
        if cmd == 'pulse':
            slot = int(sys.argv[3])
            ms = int(sys.argv[4]) if len(sys.argv) > 4 else 800
            print(pulse_slot(host, slot, ms))
        elif cmd == 'open':
            slot = int(sys.argv[3])
            print(open_slot(host, slot))
        elif cmd == 'close':
            slot = int(sys.argv[3])
            print(close_slot(host, slot))
        elif cmd == 'status':
            print(status(host))
        else:
            print('Unknown command')
    except Exception as e:
        print('Error:', e)
        sys.exit(2)
