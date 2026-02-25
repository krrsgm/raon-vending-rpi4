import serial
try:
    from serial.tools import list_ports
except Exception:
    list_ports = None

import threading
import time
from queue import Queue
import re

class CoinHopper:
    """Controls coin hoppers for dispensing change via Arduino serial interface.
    
    Communicates with arduino_bill_forward.ino to control:
    - 1 peso coin hopper
    - 5 peso coin hopper
    
    Commands sent to Arduino:
    - DISPENSE_AMOUNT <amount> [timeout_ms] : Auto-calculate and dispense coins
    - DISPENSE_DENOM <denom> <count> [timeout_ms] : Dispense exact coin count
    - COIN_OPEN <denom> : Open hopper manually
    - COIN_CLOSE <denom> : Close hopper manually
    - COIN_STATUS : Check hopper status
    - RELAY_ON : Turn on relays
    - RELAY_OFF : Turn off relays
    """
    
    def __init__(self, serial_port='/dev/ttyUSB0', baudrate=115200, timeout=2.0, auto_detect=True):
        """Initialize coin hopper controller via serial.
        
        Args:
            serial_port: Serial port connected to arduino_bill_forward
            baudrate: Serial communication speed (default 115200)
            timeout: Serial read timeout in seconds
            auto_detect: Automatically detect USB serial port if connection fails
        """
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.timeout = timeout
        self.auto_detect = auto_detect
        self.serial_conn = None
        self.is_running = False
        self.read_thread = None
        self.response_queue = Queue()
        self._lock = threading.Lock()
    
    def _choose_stopbits_for_port(self, port_name: str):
        """Determine appropriate stopbits based on port name.
        
        Args:
            port_name: Serial port name/path
            
        Returns:
            serial.STOPBITS_ONE or serial.STOPBITS_TWO
        """
        if not port_name:
            return serial.STOPBITS_TWO
        if 'ttyACM' in port_name or 'ttyUSB' in port_name or 'COM' in port_name:
            return serial.STOPBITS_ONE
        return serial.STOPBITS_TWO
    
    def _auto_find_usb_serial(self):
        """Automatically find USB serial port.
        
        Returns:
            Port path if found, None otherwise
        """
        ports = []
        try:
            if list_ports:
                for p in list_ports.comports():
                    ports.append((p.device, p.description))
            else:
                import glob
                for path in glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'):
                    ports.append((path, 'tty'))
        except Exception:
            return None

        # Prioritize known Arduino/microcontroller chip signatures
        for dev, desc in ports:
            d = (desc or '').lower()
            if 'arduino' in d or 'cp210' in d or 'ftdi' in d or 'ch340' in d or 'usb serial' in d:
                return dev
        
        # If no recognized device, return first available USB port
        if ports:
            return ports[0][0]
        return None
        
    def connect(self):
        """Connect to Arduino via serial port.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            stopbits = self._choose_stopbits_for_port(self.serial_port)
            self.serial_conn = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                stopbits=stopbits,
                parity=serial.PARITY_NONE,
                timeout=self.timeout
            )
            self.is_running = True
            print(f"[CoinHopper] Connected to {self.serial_port} @ {self.baudrate} baud")
            return True
        except Exception as e:
            print(f"[CoinHopper] Failed to connect to {self.serial_port}: {e}")
            
            # Try auto-detection if enabled
            if self.auto_detect:
                print("[CoinHopper] Attempting auto-detection of USB serial port...")
                autodetected = self._auto_find_usb_serial()
                if autodetected:
                    try:
                        stopbits = self._choose_stopbits_for_port(autodetected)
                        self.serial_conn = serial.Serial(
                            port=autodetected,
                            baudrate=self.baudrate,
                            bytesize=serial.EIGHTBITS,
                            stopbits=stopbits,
                            parity=serial.PARITY_NONE,
                            timeout=self.timeout
                        )
                        self.is_running = True
                        self.serial_port = autodetected  # Update the port for future reference
                        print(f"[CoinHopper] Auto-detected and connected to {autodetected}")
                        return True
                    except Exception as e2:
                        print(f"[CoinHopper] Auto-detection connection failed: {e2}")
            
            return False

    def send_command(self, cmd):
        """Send command to Arduino and wait for response.
        
        Args:
            cmd: Command string (without newline)
            
        Returns:
            Response from Arduino or None on timeout
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            print("[CoinHopper] Serial connection not open")
            return None
            
        try:
            with self._lock:
                # Clear any stale data
                self.serial_conn.reset_input_buffer()
                self.serial_conn.reset_output_buffer()
                
                # Send command
                self.serial_conn.write((cmd.strip() + '\n').encode('utf-8'))
                self.serial_conn.flush()
                
                # Use readline() for robust newline handling
                start = time.time()
                while time.time() - start < self.timeout:
                    if self.serial_conn.in_waiting:
                        try:
                            response = self.serial_conn.readline()
                            if response:
                                return response.decode('utf-8', errors='ignore').strip()
                        except Exception as e:
                            print(f"[CoinHopper] Error reading line: {e}")
                            return None
                    time.sleep(0.01)  # Small sleep to avoid busy-waiting
                
                print(f"[CoinHopper] No response to command: {cmd}")
                return None
        except Exception as e:
            print(f"[CoinHopper] Error sending command: {e}")
            return None

    def calculate_change(self, amount):
        """Calculate optimal coin combination for change.
        
        Args:
            amount: Amount of change needed in pesos
            
        Returns:
            Tuple of (num_five_peso, num_one_peso) coins needed
        """
        # Use as many 5 peso coins as possible, then ones for remainder
        num_five = amount // 5
        remainder = amount % 5
        num_one = remainder
        
        return (num_five, num_one)

    def dispense_change(self, amount, timeout_ms=30000, callback=None):
        """Dispense specified amount of change using only 5- and 1-peso coins.
        
        Args:
            amount: Amount to dispense in pesos
            timeout_ms: Timeout for dispensing in milliseconds (per denomination)
            callback: Optional function to call with status updates
            
        Returns:
            Tuple of (success, dispensed_amount, error_message)
        """
        if amount <= 0:
            return (True, 0, "No change needed")
        
        if not self.serial_conn or not self.serial_conn.is_open:
            return (False, 0, "Serial connection not open")
        
        try:
            num_five, num_one = self.calculate_change(int(amount))
            if callback:
                callback(f"Change plan: {num_five} x ₱5, {num_one} x ₱1")
            
            dispensed_total = 0
            
            if num_five > 0:
                if callback:
                    callback(f"Dispensing ₱5 coins: {num_five}")
                ok, dispensed, msg = self.dispense_coins(5, num_five, timeout_ms=timeout_ms, callback=callback)
                if not ok:
                    return (False, dispensed_total + dispensed * 5, f"Failed to dispense ₱5 coins: {msg}")
                dispensed_total += dispensed * 5
            
            if num_one > 0:
                if callback:
                    callback(f"Dispensing ₱1 coins: {num_one}")
                ok, dispensed, msg = self.dispense_coins(1, num_one, timeout_ms=timeout_ms, callback=callback)
                if not ok:
                    return (False, dispensed_total + dispensed, f"Failed to dispense ₱1 coins: {msg}")
                dispensed_total += dispensed
            
            return (True, dispensed_total, "Change dispensed successfully")
                
        except Exception as e:
            error_msg = f"Error dispensing change: {str(e)}"
            print(f"[CoinHopper] {error_msg}")
            return (False, 0, error_msg)

    def dispense_coins(self, denomination, count, timeout_ms=30000, callback=None):
        """Dispense specific denomination and count.
        
        Args:
            denomination: 1 or 5 (peso coins)
            count: Number of coins to dispense
            timeout_ms: Timeout for dispensing in milliseconds
            callback: Optional function to call with status updates
            
        Returns:
            Tuple of (success, dispensed_count, error_message)
        """
        if denomination not in (1, 5):
            return (False, 0, f"Invalid denomination: {denomination}")
        
        if count <= 0:
            return (False, 0, "Count must be greater than 0")
        
        if not self.serial_conn or not self.serial_conn.is_open:
            return (False, 0, "Serial connection not open")
        
        try:
            cmd = f"DISPENSE_DENOM {denomination} {count} {timeout_ms}"
            if callback:
                callback(f"Sending: {cmd}")
            
            response = self.send_command(cmd)
            
            if not response:
                return (False, 0, "No response from Arduino")
            
            if "OK" in response or "DONE" in response:
                if callback:
                    callback(f"Dispensing complete: {response}")
                return (True, count, f"Dispensed {count} {denomination}-peso coins")
            elif "ERR" in response or "TIMEOUT" in response:
                match = re.search(r'dispensed:(\d+)', response)
                dispensed = int(match.group(1)) if match else 0
                return (False, dispensed, f"Dispensing failed: {response}")
            else:
                # Unknown response - log it and return failure
                print(f"[CoinHopper] Unknown DISPENSE_DENOM response: {response}")
                return (False, 0, f"Unknown response from coin hopper: {response}")
                
        except Exception as e:
            error_msg = f"Error dispensing coins: {str(e)}"
            print(f"[CoinHopper] {error_msg}")
            return (False, 0, error_msg)

    def get_status(self):
        """Get current hopper status.
        
        Returns:
            Status string from Arduino or None on error
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            return None
        
        response = self.send_command("COIN_STATUS")
        return response

    def open_hopper(self, denomination):
        """Manually open a hopper.
        
        Args:
            denomination: 1 or 5
            
        Returns:
            True if successful, False otherwise
        """
        if denomination not in (1, 5):
            return False
        
        response = self.send_command(f"COIN_OPEN {denomination}")
        return response and "OK" in response

    def close_hopper(self, denomination):
        """Manually close a hopper.
        
        Args:
            denomination: 1 or 5
            
        Returns:
            True if successful, False otherwise
        """
        if denomination not in (1, 5):
            return False
        
        response = self.send_command(f"COIN_CLOSE {denomination}")
        return response and "OK" in response

    def disconnect(self):
        """Close serial connection."""
        try:
            self.is_running = False
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
                print("[CoinHopper] Serial connection closed")
        except Exception as e:
            print(f"[CoinHopper] Error during disconnect: {e}")
    
    def cleanup(self):
        """Alias for disconnect for compatibility."""
        self.disconnect()
