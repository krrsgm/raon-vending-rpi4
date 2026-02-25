"""
ESP32 Coin Acceptor Handler
Communicates with the coin acceptor integrated in vending_controller.ino via USB Serial.
Compatible with the same interface as the original coin_handler.py
"""

import serial
try:
    from serial.tools import list_ports
except Exception:
    list_ports = None

import threading
import time
from queue import Queue
import logging

logger = logging.getLogger(__name__)


class CoinAcceptorESP32:
    """
    ESP32-based coin acceptor that communicates via USB Serial at 115200 baud.
    Provides the same interface as the Raspberry Pi GPIO-based CoinAcceptor.
    """
    
    COIN_VALUES = {
        1: {'value': 1.0, 'description': 'Old 1 Peso Coin'},
        2: {'value': 1.0, 'description': 'New 1 Peso Coin'},
        3: {'value': 5.0, 'description': 'Old 5 Peso Coin'},
        4: {'value': 5.0, 'description': 'New 5 Peso Coin'},
        5: {'value': 10.0, 'description': 'Old 10 Peso Coin'},
        6: {'value': 10.0, 'description': 'New 10 Peso Coin'}
    }
    
    def __init__(self, port=None, baudrate=115200, timeout=1.0, shared_reader=None):
        """
        Initialize ESP32 coin acceptor
        
        Args:
            port (str): Serial port (e.g., '/dev/ttyUSB0' or 'COM3'). If None, auto-detect.
            baudrate (int): Baud rate (default 115200)
            timeout (float): Serial timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.is_running = False
        self.read_thread = None
        self.received_amount = 0.0
        self.coin_queue = Queue()
        self._lock = threading.Lock()
        self._last_status_time = 0
        self._status_interval = 2.0  # Poll balance every 2 seconds
        self._shared_reader = shared_reader

        if self._shared_reader:
            try:
                self._shared_reader.add_coin_callback(self._on_shared_coin)
                self.received_amount = float(self._shared_reader.get_coin_total() or 0.0)
            except Exception:
                pass
        else:
            self.connect()
            self.start()
    
    def _choose_stopbits_for_port(self, port_name: str):
        if not port_name:
            return serial.STOPBITS_TWO
        if 'ttyACM' in port_name or 'ttyUSB' in port_name or 'COM' in port_name:
            return serial.STOPBITS_ONE
        return serial.STOPBITS_TWO
    
    def _auto_find_usb_serial(self):
        """Auto-detect available USB serial ports"""
        if not list_ports:
            return None
        
        for port_info in list_ports.comports():
            if 'USB' in port_info.description or 'ACM' in port_info.device:
                logger.info(f"[CoinAcceptor] Found USB port: {port_info.device}")
                return port_info.device
        return None
    
    def connect(self):
        """Connect to ESP32 serial port"""
        port_to_try = self.port
        
        if not port_to_try:
            port_to_try = self._auto_find_usb_serial()
            if not port_to_try:
                logger.warning("[CoinAcceptor] No USB serial port found. Coin acceptor disabled.")
                return False
        
        try:
            stopbits = self._choose_stopbits_for_port(port_to_try)
            self.serial_conn = serial.Serial(
                port=port_to_try,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                stopbits=stopbits,
                parity=serial.PARITY_NONE,
                timeout=self.timeout,
            )
            logger.info(f"[CoinAcceptor] Connected to ESP32 at {port_to_try} @ {self.baudrate} baud")
            return True
        except Exception as e:
            logger.error(f"[CoinAcceptor] Failed to connect to {port_to_try}: {e}")
            return False
    
    def start(self):
        """Start the serial read thread"""
        if not self.serial_conn:
            logger.warning("[CoinAcceptor] Serial connection not available. Cannot start.")
            return
        
        self.is_running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        logger.info("[CoinAcceptor] Started read thread")
    
    def _read_loop(self):
        """Background thread that reads serial data and parses coin events"""
        buffer = ""
        
        while self.is_running and self.serial_conn:
            try:
                # Poll for balance periodically
                current_time = time.time()
                if (current_time - self._last_status_time) > self._status_interval:
                    self._last_status_time = current_time
                    try:
                        self.serial_conn.write(b"GET_BALANCE\n")
                    except Exception as e:
                        logger.debug(f"[CoinAcceptor] Error polling balance: {e}")
                
                # Read available data
                if self.serial_conn.in_waiting:
                    try:
                        byte = self.serial_conn.read(1)
                        if not byte:
                            continue
                        
                        char = byte.decode('utf-8', errors='ignore')
                        
                        if char == '\n':
                            line = buffer.strip()
                            buffer = ""
                            
                            if line:
                                self._process_line(line)
                        elif char not in ('\r', '\x00'):
                            buffer += char
                            if len(buffer) > 256:
                                buffer = buffer[-256:]
                    except Exception as e:
                        logger.debug(f"[CoinAcceptor] Error reading serial: {e}")
                else:
                    time.sleep(0.01)
            
            except Exception as e:
                logger.error(f"[CoinAcceptor] Read loop error: {e}")
                time.sleep(0.1)
    
    def _process_line(self, line: str):
        """Parse a line from ESP32 coin acceptor"""
        line = line.strip()
        
        # Parse BALANCE response
        if "BALANCE:" in line:
            try:
                amount_str = line.split("BALANCE:")[1].split()[0]
                amount = float(amount_str.replace("₱", ""))
                with self._lock:
                    self.received_amount = amount
                logger.debug(f"[CoinAcceptor] Balance updated: ₱{amount:.2f}")
            except Exception as e:
                logger.debug(f"[CoinAcceptor] Error parsing balance: {e}")
        
        # Parse coin detection
        elif "[COIN]" in line:
            try:
                # Extract value from format: [COIN] Output A1 - Value: ₱X.X | Total: ₱Y.YY
                if "Value:" in line:
                    value_part = line.split("Value:")[1].split("|")[0].strip()
                    value = float(value_part.replace("₱", ""))
                    with self._lock:
                        # Amount is already updated by ESP32, just log it
                        pass
                    logger.info(f"[CoinAcceptor] Coin detected: ₱{value}")
                    self.coin_queue.put(value)
            except Exception as e:
                logger.debug(f"[CoinAcceptor] Error parsing coin event: {e}")
        
        # Log other messages
        elif line and not line.startswith("OK"):
            logger.debug(f"[CoinAcceptor] {line}")
    
    def get_received_amount(self):
        """Get the total amount received (thread-safe)"""
        if self._shared_reader:
            try:
                return float(self._shared_reader.get_coin_total())
            except Exception:
                return 0.0
        with self._lock:
            return self.received_amount
    
    def reset_amount(self):
        """Reset the received amount to zero"""
        if self._shared_reader:
            with self._lock:
                self.received_amount = 0.0
            return
        if not self.serial_conn:
            logger.warning("[CoinAcceptor] Serial connection not available")
            return
        
        try:
            self.serial_conn.write(b"RESET_BALANCE\n")
            with self._lock:
                self.received_amount = 0.0
            logger.info("[CoinAcceptor] Balance reset")
        except Exception as e:
            logger.error(f"[CoinAcceptor] Error resetting balance: {e}")

    def _on_shared_coin(self, total):
        try:
            with self._lock:
                self.received_amount = float(total)
        except Exception:
            pass
    
    def set_coin_value(self, output: int, value: float):
        """
        Set the coin value for a specific output (A1-A6)
        
        Args:
            output (int): Output number 1-6
            value (float): Coin value in pesos
        """
        if not self.serial_conn:
            logger.warning("[CoinAcceptor] Serial connection not available")
            return
        
        if output < 1 or output > 6:
            logger.error(f"[CoinAcceptor] Invalid output: {output}. Must be 1-6")
            return
        
        if value <= 0:
            logger.error(f"[CoinAcceptor] Invalid value: {value}. Must be positive")
            return
        
        try:
            cmd = f"SET_COIN_VALUE {output} {value}\n"
            self.serial_conn.write(cmd.encode())
            logger.info(f"[CoinAcceptor] Set output A{output} value to ₱{value}")
        except Exception as e:
            logger.error(f"[CoinAcceptor] Error setting coin value: {e}")
    
    def set_output(self, output: int):
        """
        Set the active output (A1-A6) that will be counted
        
        Args:
            output (int): Output number 1-6
        """
        if not self.serial_conn:
            logger.warning("[CoinAcceptor] Serial connection not available")
            return
        
        if output < 1 or output > 6:
            logger.error(f"[CoinAcceptor] Invalid output: {output}. Must be 1-6")
            return
        
        try:
            cmd = f"SET_OUTPUT {output}\n"
            self.serial_conn.write(cmd.encode())
            logger.info(f"[CoinAcceptor] Set active output to A{output}")
        except Exception as e:
            logger.error(f"[CoinAcceptor] Error setting output: {e}")
    
    def cleanup(self):
        """Clean up and close the serial connection"""
        self.is_running = False
        
        if self.read_thread:
            self.read_thread.join(timeout=1.0)
        
        if self.serial_conn:
            try:
                self.serial_conn.close()
                logger.info("[CoinAcceptor] Serial connection closed")
            except Exception as e:
                logger.error(f"[CoinAcceptor] Error closing serial connection: {e}")
    
    def __del__(self):
        """Cleanup on object destruction"""
        self.cleanup()
