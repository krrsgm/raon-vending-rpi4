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
import subprocess
import os
try:
    import serial
except Exception:
    serial = None
import logging

# Enable simple logging for diagnostics. Consumer can configure logging as needed.
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# Persistent TCP connections cache: host -> socket
_tcp_sockets = {}

def _close_tcp(host, port=None):
    """Close and remove cached TCP socket for host:port key.

    Accepts `port=None` and resolves to `DEFAULT_PORT` at runtime so
    the function can be defined before `DEFAULT_PORT` is declared.
    """
    if port is None:
        port = DEFAULT_PORT
    key = f"{host}:{port}"
    s = _tcp_sockets.pop(key, None)
    if s:
        try:
            s.close()
        except Exception:
            pass

def _open_tcp(host, port, timeout):
    """Open and cache a TCP connection to host:port."""
    key = f"{host}:{port}"
    s = _tcp_sockets.get(key)
    if s:
        try:
            # Verify socket is still alive by checking if it's open
            s.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
            return s
        except (OSError, socket.error):
            # Socket is dead, remove from cache
            _tcp_sockets.pop(key, None)
    logging.info(f"Opening TCP connection to {host}:{port}")
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        # set a read timeout; callers may change this temporarily
        s.settimeout(timeout)
        _tcp_sockets[key] = s
        return s
    except Exception as e:
        logging.error(f"Failed to open TCP connection: {e}")
        _tcp_sockets.pop(key, None)
        raise

DEFAULT_PORT = 5000

def _open_serial_with_sudo(port_name, baudrate, timeout, cmd, retries=1):
    """Attempt to open serial port with sudo if permission is denied."""
    # Build a Python command to run with sudo
    python_code = f"""
import serial
import time
import sys
port_name = {repr(port_name)}
baudrate = {baudrate}
timeout = {timeout}
cmd = {repr(cmd)}

try:
    with serial.Serial(port_name, baudrate=baudrate, timeout=timeout) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.05)
        cmd_bytes = (cmd.strip() + '\\n').encode('utf-8')
        ser.write(cmd_bytes)
        ser.flush()
        time.sleep(0.05)
        start = time.time()
        buf = b''
        while time.time() - start < timeout:
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting)
                if chunk:
                    buf += chunk
                    if b'\\n' in buf:
                        break
            else:
                time.sleep(0.01)
        if buf:
            print(buf.decode('utf-8', errors='ignore').strip())
        sys.exit(0)
except Exception as e:
    print(f"ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
    
    try:
        # Try to run with sudo
        result = subprocess.run(
            ['sudo', 'python3', '-c', python_code],
            capture_output=True,
            text=True,
            timeout=timeout + 2
        )
        
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip()
        else:
            raise Exception(f"sudo command failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"sudo serial command timed out after {timeout}s")
    except Exception as e:
        raise Exception(f"Failed to execute with sudo: {e}")


def send_command(host, cmd, port=DEFAULT_PORT, timeout=2.0, retries=3, use_persistent_tcp=True):
    """Send a command string to ESP32 and return response (strip newlines).

    Adds simple retry/backoff logic and more robust read handling for both TCP
    and serial transports to reduce intermittent "timed out" failures.
    """
    # If host is a serial URI like 'serial:/dev/ttyUSB0' use UART transport
    if isinstance(host, str) and host.startswith('serial:'):
        if serial is None:
            raise RuntimeError('pyserial is required for serial transport but is not installed')
        port_name = host.split(':', 1)[1]
        logging.info(f"Using SERIAL transport: {port_name} @ 115200 baud")
        # Open/close per command to keep simple and stateless. Try a few times.
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                with serial.Serial(port_name, baudrate=115200, timeout=timeout) as ser:
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    
                    # Add small delay to ensure serial port is ready
                    time.sleep(0.05)
                    
                    cmd_bytes = (cmd.strip() + '\n').encode('utf-8')
                    logging.debug(f"Sending to serial: {cmd_bytes}")
                    ser.write(cmd_bytes)
                    ser.flush()
                    
                    # Add a small delay to let ESP32 process and send response
                    time.sleep(0.05)
                    
                    # wait up to `timeout` seconds for a response
                    start = time.time()
                    buf = b''
                    while time.time() - start < timeout:
                        # Use in_waiting to check if data is available
                        if ser.in_waiting > 0:
                            # Read all available bytes at once (like test_rxtx_communication.py does)
                            chunk = ser.read(ser.in_waiting)
                            if chunk:
                                buf += chunk
                                logging.debug(f"Received {len(chunk)} bytes: {repr(chunk)}")
                                # Stop if we got a newline (complete line)
                                if b'\n' in buf:
                                    break
                        else:
                            time.sleep(0.01)  # Small sleep to avoid busy-wait
                    
                    if not buf:
                        # no response this attempt
                        last_exc = TimeoutError(f'serial read timeout after {timeout}s on attempt {attempt}/{retries}')
                        logging.warning(f"Serial timeout on {port_name}, attempt {attempt}/{retries}")
                        # small backoff before retrying
                        time.sleep(0.1)
                        continue
                    
                    response = buf.decode('utf-8', errors='ignore').strip()
                    logging.info(f"Serial response: {response}")
                    return response
            except (serial.SerialException, PermissionError) as e:
                # Serial port error (port not found, permission denied, etc.)
                if isinstance(e, PermissionError) or 'Permission denied' in str(e):
                    logging.warning(f"Permission denied on {port_name}, attempting with sudo...")
                    try:
                        response = _open_serial_with_sudo(port_name, 115200, timeout, cmd, retries=1)
                        logging.info(f"Serial response (via sudo): {response}")
                        return response
                    except Exception as sudo_err:
                        logging.error(f"Sudo attempt also failed: {sudo_err}")
                        last_exc = sudo_err
                else:
                    last_exc = e
                    logging.error(f"Serial port error on {port_name}: {e}")
                    raise  # Don't retry serial port errors, they're usually permanent
            except Exception as e:
                last_exc = e
                logging.warning(f"Serial attempt {attempt} failed: {e}")
                # small backoff before retrying
                time.sleep(0.05)
                continue
        # exhausted retries
        logging.error(f"CRITICAL: Serial communication failed after {retries} attempts: {last_exc}")
        raise last_exc

    # Default: TCP transport
    # Default: TCP transport with retries and robust read-until-newline
    last_exc = None
    key = f"{host}:{port}"
    for attempt in range(1, retries + 1):
        try:
            if use_persistent_tcp:
                # try to reuse an existing socket (open if needed)
                try:
                    s = _open_tcp(host, port, timeout)
                except Exception as e:
                    logging.warning(f"Persistent TCP open failed: {e}")
                    # fall back to ephemeral connect below
                    s = None

                if s:
                    try:
                        # ensure socket timeout
                        s.settimeout(timeout)
                        s.sendall((cmd.strip() + "\n").encode('utf-8'))
                        # read until newline or timeout
                        resp_buf = b''
                        start = time.time()
                        while time.time() - start < timeout:
                            try:
                                chunk = s.recv(512)
                            except socket.timeout:
                                break
                            if not chunk:
                                break
                            resp_buf += chunk
                            if b'\n' in resp_buf:
                                break
                        if not resp_buf:
                            # treat as timeout for this attempt
                            last_exc = TimeoutError(f'TCP read timeout after {timeout}s')
                            # close and retry (reconnect next attempt)
                            logging.info("No TCP response, closing persistent socket and retrying")
                            _close_tcp(host, port)  # Close socket to clean up resource
                            time.sleep(0.05)
                            continue
                        line = resp_buf.split(b'\n', 1)[0]
                        return line.decode('utf-8', errors='ignore').strip()
                    except Exception as e:
                        last_exc = e
                        logging.warning(f"Persistent TCP operation failed: {e}")
                        _close_tcp(host, port)  # Close socket to clean up resource
                        time.sleep(0.05)
                        continue

            # fallback ephemeral TCP connect (works even if persistent failed)
            with socket.create_connection((host, port), timeout=timeout) as s2:
                s2.sendall((cmd.strip() + "\n").encode('utf-8'))
                s2.settimeout(timeout)
                resp_buf = b''
                start = time.time()
                while time.time() - start < timeout:
                    try:
                        chunk = s2.recv(512)
                    except socket.timeout:
                        break
                    if not chunk:
                        break
                    resp_buf += chunk
                    if b'\n' in resp_buf:
                        break
                if not resp_buf:
                    last_exc = TimeoutError(f'TCP read timeout after {timeout}s')
                    time.sleep(0.05)
                    continue
                line = resp_buf.split(b'\n', 1)[0]
                return line.decode('utf-8', errors='ignore').strip()
        except Exception as e:
            last_exc = e
            logging.warning(f"TCP attempt {attempt} failed: {e}")
            time.sleep(0.05)
            continue
    # If TCP failed, try USB/serial ports automatically (useful when ESP32 is
    # connected over USB CDC instead of network). This will scan common serial
    # devices and try the "serial:/..." transport.
    if serial is not None:
        logging.info("TCP failed, attempting serial port scan as fallback")
        # Try to discover candidate ports using pyserial's tools if available
        ports = []
        try:
            import serial.tools.list_ports as list_ports
            for p in list_ports.comports():
                ports.append(p.device)
        except Exception:
            # Fallback heuristics
            if os.name == 'nt':
                ports = [f'COM{i}' for i in range(1, 21)]
            else:
                # common device names on Linux
                ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyS0']

        for p in ports:
            try:
                logging.info(f"Trying serial port fallback: {p}")
                resp = send_command(f'serial:{p}', cmd, timeout=timeout, retries=1)
                logging.info(f"Serial fallback succeeded on {p}")
                return resp
            except Exception as e:
                logging.debug(f"Serial port {p} failed: {e}")
                continue

    # exhausted all transports
    raise last_exc


def pulse_slot(host, slot, ms=800, port=DEFAULT_PORT, timeout=2.0):
    """Pulse a slot number (1-based) for ms milliseconds."""
    cmd = f"PULSE {int(slot)} {int(ms)}"
    return send_command(host, cmd, port=port, timeout=timeout)


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
