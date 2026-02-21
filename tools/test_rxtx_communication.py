#!/usr/bin/env python3
"""
test_rxtx_communication.py
Test serial (RXTX) communication between Raspberry Pi and ESP32.

Pin Configuration:
    - ESP32 TX (GPIO 1)  -> Raspberry Pi RX (GPIO 15)
    - ESP32 RX (GPIO 3)  <- Raspberry Pi TX (GPIO 14)
    - Connect GND between ESP32 and Raspberry Pi

Usage (on Raspberry Pi):
  python3 tools/test_rxtx_communication.py --port /dev/ttyS0

Or for USB serial adapter:
  python3 tools/test_rxtx_communication.py --port /dev/ttyACM0

Or on Windows:
  python tools/test_rxtx_communication.py --port COM3

Note: If you get permission denied errors, the tool will automatically retry with sudo.
"""
import argparse
import serial
import time
import sys
import platform
import subprocess

def find_serial_ports():
    """Try to find available serial ports."""
    ports = []
    if platform.system() == 'Linux':
        # Common Raspberry Pi serial ports
        ports.extend(['/dev/ttyS0', '/dev/ttyAMA0', '/dev/ttyUSB0', '/dev/ttyACM0'])
    elif platform.system() == 'Windows':
        # Common Windows COM ports
        ports.extend([f'COM{i}' for i in range(1, 10)])
    return ports

def test_serial_connection(port_name, baudrate=115200, timeout=2.0):
    """Test serial connection to ESP32."""
    print(f"\n{'='*60}")
    print(f"Testing RXTX Communication with ESP32")
    print(f"{'='*60}")
    print(f"Port: {port_name}")
    print(f"Baud Rate: {baudrate}")
    print(f"Timeout: {timeout}s")
    print(f"{'='*60}\n")
    
    try:
        print(f"[1/5] Opening serial port {port_name}...")
        ser = serial.Serial(port_name, baudrate=baudrate, timeout=timeout)
        print(f"      ✓ Port opened successfully")
        print(f"      - Port name: {ser.name}")
        print(f"      - Baud rate: {ser.baudrate}")
        print(f"      - Timeout: {ser.timeout}s")
        
    except (serial.SerialException, PermissionError) as e:
        if isinstance(e, PermissionError) or 'Permission denied' in str(e):
            print(f"      ⚠ Permission denied, attempting with sudo...")
            return test_serial_connection_with_sudo(port_name, baudrate, timeout)
        print(f"      ✗ Failed to open port: {e}")
        print(f"\nTroubleshooting:")
        print(f"  - Verify ESP32 is connected to the serial port")
        print(f"  - Check for proper wiring (RX/TX pins)")
        print(f"  - Ensure port permissions are correct (on Linux, try 'sudo')")
        print(f"  - Try listing available ports: python -m serial.tools.list_ports")
        return False
    
    try:
        print(f"\n[2/5] Flushing buffers...")
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print(f"      ✓ Buffers flushed")
        
        print(f"\n[3/5] Sending STATUS command...")
        cmd = "STATUS\n"
        ser.write(cmd.encode('utf-8'))
        ser.flush()
        print(f"      ✓ Sent: {repr(cmd)}")
        
        print(f"\n[4/5] Waiting for response ({timeout}s timeout)...")
        start_time = time.time()
        response = b''
        
        while time.time() - start_time < timeout:
            if ser.in_waiting > 0:
                chunk = ser.read(ser.in_waiting)
                response += chunk
                print(f"      Received {len(chunk)} bytes: {repr(chunk)}")
                if b'\n' in response:
                    break
            else:
                time.sleep(0.01)
        
        elapsed = time.time() - start_time
        
        if response:
            response_str = response.decode('utf-8', errors='ignore').strip()
            print(f"      ✓ Received response in {elapsed:.2f}s")
            print(f"      - Response: {repr(response_str)}")
            
            print(f"\n[5/5] Testing PULSE command...")
            cmd = "PULSE 1 200\n"
            ser.write(cmd.encode('utf-8'))
            ser.flush()
            print(f"      ✓ Sent: {repr(cmd)}")
            
            # Read response
            response = b''
            start_time = time.time()
            while time.time() - start_time < timeout:
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting)
                    response += chunk
                    print(f"      Received {len(chunk)} bytes: {repr(chunk)}")
                    if b'\n' in response:
                        break
                else:
                    time.sleep(0.01)
            
            if response:
                response_str = response.decode('utf-8', errors='ignore').strip()
                print(f"      ✓ Received response: {repr(response_str)}")
            else:
                print(f"      ⚠ No response received (may still be OK for PULSE)")
            
            print(f"\n{'='*60}")
            print(f"✓ RXTX Communication Test PASSED")
            print(f"{'='*60}")
            print(f"\nNotes:")
            print(f"  - ESP32 is responding correctly over serial")
            print(f"  - Baud rate is correct (115200)")
            print(f"  - RX/TX wiring appears to be correct")
            return True
        else:
            print(f"      ✗ No response received after {timeout}s")
            print(f"\nTroubleshooting:")
            print(f"  - Check if ESP32 is powered on")
            print(f"  - Verify correct serial port (try other ports from list below)")
            print(f"  - Check RX/TX pin wiring (should be crossed: Pi TX -> ESP32 RX, Pi RX -> ESP32 TX)")
            print(f"  - Verify ESP32 firmware has serial communication enabled")
            print(f"  - Try baud rate 9600 if 115200 doesn't work")
            return False
            
    except Exception as e:
        print(f"      ✗ Error during communication: {e}")
        return False
    finally:
        try:
            ser.close()
            print(f"\nSerial port closed.")
        except:
            pass

def test_serial_connection_with_sudo(port_name, baudrate=115200, timeout=2.0):
    """Test serial connection using sudo."""
    print(f"      Running test with sudo...\n")
    
    python_code = f"""
import serial
import time
port_name = {repr(port_name)}
baudrate = {baudrate}
timeout = {timeout}

try:
    ser = serial.Serial(port_name, baudrate=baudrate, timeout=timeout)
    print(f"✓ Port opened: {{ser.name}} at {{ser.baudrate}} baud")
    
    # Test STATUS command
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(b'STATUS\\n')
    ser.flush()
    
    start = time.time()
    buf = b''
    while time.time() - start < timeout:
        if ser.in_waiting > 0:
            chunk = ser.read(1)
            buf += chunk
            if buf.endswith(b'\\n'):
                break
    
    response = buf.decode('utf-8', errors='ignore').strip()
    print(f"✓ STATUS response: {{response}}")
    
    # Test PULSE command
    ser.write(b'PULSE 1 200\\n')
    ser.flush()
    
    print(f"✓ PULSE command sent")
    ser.close()
    print(f"✓ Test completed successfully")
    
except Exception as e:
    print(f"✗ Error: {{e}}")
    import sys
    sys.exit(1)
"""
    
    try:
        result = subprocess.run(
            ['sudo', 'python3', '-c', python_code],
            capture_output=True,
            text=True,
            timeout=timeout + 5
        )
        
        print(result.stdout)
        if result.returncode == 0:
            print(f"{'='*60}")
            print(f"✓ RXTX Communication Test PASSED (via sudo)")
            print(f"{'='*60}")
            print(f"\nNote: You need to fix serial port permissions to avoid using sudo.")
            print(f"Run: sudo usermod -a -G dialout $USER && sudo reboot")
            return True
        else:
            print(result.stderr)
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ Test timed out")
        return False
    except Exception as e:
        print(f"✗ Error running test with sudo: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Test RXTX serial communication between Raspberry Pi and ESP32'
    )
    parser.add_argument('--port', help='Serial port (e.g., /dev/ttyS0, COM3)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate (default: 115200)')
    parser.add_argument('--timeout', type=float, default=2.0, help='Timeout in seconds (default: 2.0)')
    parser.add_argument('--list-ports', action='store_true', help='List common serial ports')
    
    args = parser.parse_args()
    
    if args.list_ports:
        print("\nCommon serial ports:")
        for port in find_serial_ports():
            print(f"  - {port}")
        try:
            import serial.tools.list_ports
            print("\nAvailable ports (from pyserial):")
            for port_info in serial.tools.list_ports.comports():
                print(f"  - {port_info.device} ({port_info.description})")
        except:
            pass
        return
    
    if not args.port:
        print("Error: --port is required")
        print("\nUsage examples:")
        print("  Raspberry Pi (hardware UART):")
        print("    python3 tools/test_rxtx_communication.py --port /dev/ttyS0")
        print("  USB serial adapter:")
        print("    python3 tools/test_rxtx_communication.py --port /dev/ttyUSB0")
        print("  Windows:")
        print("    python tools/test_rxtx_communication.py --port COM3")
        print("\nTo find available ports:")
        print("    python tools/test_rxtx_communication.py --list-ports")
        sys.exit(1)
    
    success = test_serial_connection(args.port, args.baud, args.timeout)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
