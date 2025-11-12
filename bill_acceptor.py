import serial
import threading
import time
from queue import Queue


class BillAcceptor:
    """
    Handler for TB74 bill acceptor.

    Modes supported:
    - direct MAX232 -> Raspberry Pi UART (default)
    - esp32_proxy: ESP32 forwards bill events to the Pi (serial or TCP)

    When the TB74 is connected to the ESP32, the ESP32 can forward accepted-bill
    events to the Pi. This class supports reading those forwarded events either
    via a serial port (e.g. `/dev/ttyAMA0`) connected to ESP32 TX/RX or via a
    TCP socket if the ESP32 exposes a TCP endpoint.

    Message format expected from ESP32 (simple line-based):
      BILL:20\n
    The above will be parsed and added to the received amount.

    Default serial parameters (for direct TB74 or ESP32 serial):
      baudrate=9600, 8 data bits, 2 stop bits, no parity
    """

    # TB74 Protocol byte responses for different denominations
    # These are typical values; adjust based on your specific TB74 configuration
    BILL_DENOMINATIONS = {
        0x41: 20,      # ₱20 note
        0x42: 50,      # ₱50 note
        0x43: 100,     # ₱100 note
        0x44: 500,     # ₱500 note
        0x45: 1000,    # ₱1000 note
    }

    def __init__(self, port='/dev/ttyAMA0', baudrate=9600, timeout=1.0,
                 esp32_mode=False, esp32_serial_port=None, esp32_host=None, esp32_port=5000):
        """
        Initialize the bill acceptor handler.

        Args:
            port (str): Serial port 
                - '/dev/ttyAMA0' on Raspberry Pi (hardware UART with MAX232)
                - '/dev/ttyUSB0' if using USB serial adapter
            baudrate (int): Serial communication speed (default 9600 for TB74)
            timeout (float): Serial read timeout in seconds
            esp32_mode (bool): If True, expect events forwarded by ESP32
            esp32_serial_port (str): Serial port connected to ESP32 (preferred)
            esp32_host (str): ESP32 host for TCP proxy
            esp32_port (int): ESP32 TCP port for proxy
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.is_running = False
        self.read_thread = None
        self.received_amount = 0.0
        self.bill_queue = Queue()  # Queue for accepted bills
        self._lock = threading.Lock()
        self._callback = None  # Optional callback for UI updates

        # ESP32 proxy configuration
        self.esp32_mode = bool(esp32_mode)
        self.esp32_serial_port = esp32_serial_port
        self.esp32_host = esp32_host
        self.esp32_port = esp32_port
        self._esp32_socket = None

    def connect(self):
        """
        Connect to the bill acceptor or ESP32 proxy depending on configuration.

        Returns:
            bool: True on success, False on failure
        """
        if self.esp32_mode:
            # Prefer explicit serial port for ESP32 if provided
            if self.esp32_serial_port:
                try:
                    self.serial_conn = serial.Serial(
                        port=self.esp32_serial_port,
                        baudrate=self.baudrate,
                        bytesize=serial.EIGHTBITS,
                        stopbits=serial.STOPBITS_TWO,
                        parity=serial.PARITY_NONE,
                        timeout=self.timeout
                    )
                    print(f"Bill acceptor (ESP32 proxy) connected to {self.esp32_serial_port}")
                    return True
                except serial.SerialException as e:
                    print(f"Failed to connect to ESP32 serial port {self.esp32_serial_port}: {e}")
                    return False

            # Otherwise try TCP connection to ESP32 host:port
            if self.esp32_host:
                try:
                    import socket
                    sock = socket.create_connection((self.esp32_host, int(self.esp32_port)), timeout=self.timeout)
                    self._esp32_socket = sock
                    print(f"Bill acceptor (ESP32 proxy) connected to {self.esp32_host}:{self.esp32_port}")
                    return True
                except Exception as e:
                    print(f"Failed to connect to ESP32 at {self.esp32_host}:{self.esp32_port}: {e}")
                    return False

            print("ESP32 proxy mode enabled but no serial port or host configured")
            return False

        # Default: connect to local serial port (MAX232 -> TB74)
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_TWO,
                parity=serial.PARITY_NONE,
                timeout=self.timeout
            )
            print(f"Bill acceptor connected to {self.port} at {self.baudrate} baud")
            return True
        except serial.SerialException as e:
            print(f"Failed to connect to bill acceptor: {e}")
            return False

    def disconnect(self):
        """Disconnect from the bill acceptor."""
        # Stop TCP socket if used
        try:
            if self._esp32_socket:
                try:
                    self._esp32_socket.close()
                except Exception:
                    pass
                self._esp32_socket = None
        except Exception:
            pass

        if self.serial_conn and hasattr(self.serial_conn, 'is_open') and self.serial_conn.is_open:
            self.stop_reading()
            try:
                self.serial_conn.close()
            except Exception:
                pass
            print("Bill acceptor disconnected")

    def start_reading(self):
        """Start the background thread that reads bill acceptor data."""
        if self.esp32_mode and not (self._esp32_socket or self.serial_conn):
            print("Error: ESP32 proxy selected but no connection established. Call connect() first.")
            return False

        if not self.esp32_mode and (not self.serial_conn or not getattr(self.serial_conn, 'is_open', True)):
            print("Error: Serial connection not open. Call connect() first.")
            return False

        if self.is_running:
            return True

        self.is_running = True
        # Select appropriate read loop depending on mode
        if self.esp32_mode and self._esp32_socket:
            self.read_thread = threading.Thread(target=self._read_loop_tcp, daemon=True)
        else:
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        print("Bill acceptor reading started")
        return True

    def stop_reading(self):
        """Stop the background reading thread."""
        self.is_running = False
        if self.read_thread:
            self.read_thread.join(timeout=2.0)
        print("Bill acceptor reading stopped")

    def _read_loop(self):
        """Background thread loop that continuously reads from the bill acceptor."""
        while self.is_running:
            try:
                # Read available data from serial port
                if self.serial_conn and getattr(self.serial_conn, 'in_waiting', 0) > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    # If this is ESP32 serial proxy, data is expected to be line text
                    try:
                        text = data.decode('utf-8', errors='ignore')
                        for line in text.splitlines():
                            self._process_esp32_line(line.strip())
                    except Exception:
                        # Fallback to raw processing
                        self._process_bill_data(data)
                else:
                    time.sleep(0.05)  # Sleep briefly to avoid busy-waiting
            except Exception as e:
                print(f"Error reading from bill acceptor: {e}")
                time.sleep(0.1)

    def _read_loop_tcp(self):
        """Read-loop for TCP socket connection to ESP32 proxy."""
        sock = self._esp32_socket
        f = sock.makefile('r', encoding='utf-8', errors='ignore')
        while self.is_running:
            try:
                line = f.readline()
                if not line:
                    time.sleep(0.05)
                    continue
                self._process_esp32_line(line.strip())
            except Exception as e:
                print(f"Error reading from ESP32 TCP proxy: {e}")
                time.sleep(0.1)

    def _process_bill_data(self, data):
        """
        Process incoming bill acceptor data.

        Args:
            data (bytes): Raw data from serial port
        """
        # Default: TB74 raw bytes mapping
        for byte in data:
            if byte in self.BILL_DENOMINATIONS:
                denomination = self.BILL_DENOMINATIONS[byte]
                self._register_bill(denomination)

    def _process_esp32_line(self, line):
        """Process a single line of text forwarded by the ESP32.

        Expected formats:
          BILL:20
          BILL:100
        """
        if not line:
            return
        # Normalize
        s = line.strip()
        # Accept simple prefixed messages
        if s.upper().startswith('BILL:'):
            try:
                amount = int(s.split(':', 1)[1])
                self._register_bill(amount)
            except Exception:
                print(f"Unrecognized bill message: {line}")
        else:
            # Could be raw hex bytes sent as hex string
            # e.g. "41" or "0x41"
            try:
                hexval = s
                if hexval.startswith('0x'):
                    hexval = hexval[2:]
                b = bytes.fromhex(hexval)
                self._process_bill_data(b)
            except Exception:
                # Unknown line
                pass

    def _register_bill(self, denomination):
        """Register a bill denomination into the local state and notify callback."""
        with self._lock:
            self.received_amount += denomination
            self.bill_queue.put(denomination)

        print(f"Bill accepted: ₱{denomination} (Total: ₱{self.received_amount:.2f})")

        # Call user callback if provided
        if self._callback:
            try:
                self._callback(self.received_amount)
            except Exception as e:
                print(f"Callback error: {e}")

    def set_callback(self, callback):
        """
        Set a callback function to be called when a bill is accepted.

        Args:
            callback (callable): Function that takes total_amount as parameter
        """
        self._callback = callback

    def get_received_amount(self):
        """
        Get the total amount received so far in this session.

        Returns:
            float: Total bill amount in pesos
        """
        with self._lock:
            return self.received_amount

    def get_last_bills(self, count=None):
        """
        Get the last accepted bills.

        Args:
            count (int, optional): Number of recent bills to retrieve

        Returns:
            list: List of bill denominations
        """
        bills = []
        while not self.bill_queue.empty():
            try:
                bills.append(self.bill_queue.get_nowait())
            except Exception:
                break

        if count:
            bills = bills[-count:]

        return bills

    def reset_amount(self):
        """Reset the total received amount to 0."""
        with self._lock:
            self.received_amount = 0.0
            # Clear any remaining bills in queue
            while not self.bill_queue.empty():
                try:
                    self.bill_queue.get_nowait()
                except Exception:
                    break
        print("Bill acceptor amount reset")

    def send_command(self, command_bytes):
        """
        Send a raw command to the bill acceptor (for advanced control).

        Args:
            command_bytes (bytes): Command data to send

        Returns:
            bool: True if sent successfully
        """
        try:
            if self.serial_conn and getattr(self.serial_conn, 'is_open', True):
                self.serial_conn.write(command_bytes)
                return True
        except Exception as e:
            print(f"Failed to send command to bill acceptor: {e}")
        return False

    def cleanup(self):
        """Clean up resources."""
        self.disconnect()


# Mock implementation for testing without hardware
class MockBillAcceptor(BillAcceptor):
    """Mock bill acceptor for testing without physical hardware."""

    def __init__(self):
        super().__init__()
        self.is_mock = True
        print("MockBillAcceptor initialized (testing mode)")

    def connect(self):
        """Mock connect - always succeeds."""
        print("Mock: Bill acceptor connected")
        return True

    def disconnect(self):
        """Mock disconnect."""
        self.is_running = False
        print("Mock: Bill acceptor disconnected")

    def start_reading(self):
        """Mock start reading."""
        self.is_running = True
        print("Mock: Bill acceptor reading started")
        return True

    def send_command(self, command_bytes):
        """Mock send command."""
        return True

    def simulate_bill_accepted(self, denomination):
        """
        Simulate a bill being accepted (for testing).

        Args:
            denomination (int): Bill amount to simulate
        """
        with self._lock:
            self.received_amount += denomination
            self.bill_queue.put(denomination)

        print(f"Mock: Bill accepted: ₱{denomination} (Total: ₱{self.received_amount:.2f})")

        if self._callback:
            try:
                self._callback(self.received_amount)
            except Exception as e:
                print(f"Callback error: {e}")

    def set_callback(self, callback):
        """
        Set a callback function to be called when a bill is accepted.

        Args:
            callback (callable): Function that takes total_amount as parameter
        """
        self._callback = callback

    def get_received_amount(self):
        """
        Get the total amount received so far in this session.

        Returns:
            float: Total bill amount in pesos
        """
        with self._lock:
            return self.received_amount

    def get_last_bills(self, count=None):
        """
        Get the last accepted bills.

        Args:
            count (int, optional): Number of recent bills to retrieve

        Returns:
            list: List of bill denominations
        """
        bills = []
        while not self.bill_queue.empty():
            try:
                bills.append(self.bill_queue.get_nowait())
            except Exception:
                break

        if count:
            bills = bills[-count:]

        return bills

    def reset_amount(self):
        """Reset the total received amount to 0."""
        with self._lock:
            self.received_amount = 0.0
            # Clear any remaining bills in queue
            while not self.bill_queue.empty():
                try:
                    self.bill_queue.get_nowait()
                except Exception:
                    break
        print("Bill acceptor amount reset")

    def send_command(self, command_bytes):
        """
        Send a raw command to the bill acceptor (for advanced control).

        Args:
            command_bytes (bytes): Command data to send

        Returns:
            bool: True if sent successfully
        """
        try:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.write(command_bytes)
                return True
        except Exception as e:
            print(f"Failed to send command to bill acceptor: {e}")
        return False

    def cleanup(self):
        """Clean up resources."""
        self.disconnect()


# Mock implementation for testing without hardware
class MockBillAcceptor(BillAcceptor):
    """Mock bill acceptor for testing without physical hardware."""

    def __init__(self):
        super().__init__()
        self.is_mock = True
        print("MockBillAcceptor initialized (testing mode)")

    def connect(self):
        """Mock connect - always succeeds."""
        print("Mock: Bill acceptor connected")
        return True

    def disconnect(self):
        """Mock disconnect."""
        self.is_running = False
        print("Mock: Bill acceptor disconnected")

    def start_reading(self):
        """Mock start reading."""
        self.is_running = True
        print("Mock: Bill acceptor reading started")
        return True

    def send_command(self, command_bytes):
        """Mock send command."""
        return True

    def simulate_bill_accepted(self, denomination):
        """
        Simulate a bill being accepted (for testing).

        Args:
            denomination (int): Bill amount to simulate
        """
        with self._lock:
            self.received_amount += denomination
            self.bill_queue.put(denomination)

        print(f"Mock: Bill accepted: ₱{denomination} (Total: ₱{self.received_amount:.2f})")

        if self._callback:
            try:
                self._callback(self.received_amount)
            except Exception as e:
                print(f"Callback error: {e}")
