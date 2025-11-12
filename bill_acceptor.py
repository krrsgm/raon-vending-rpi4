import serial
import threading
import time
from queue import Queue


class BillAcceptor:
    """
    Handler for TB74 bill acceptor connected via MAX232 level converter to Raspberry Pi.
    
    Hardware Connection:
    - TB74 TX/RX → MAX232 → Raspberry Pi UART (GPIO 14/15 or /dev/ttyAMA0)
    
    The TB74 communicates using a serial protocol where:
    - Baud rate: 9600
    - Data bits: 8
    - Stop bits: 2
    - Parity: None
    - Flow control: None
    
    Bill denominations supported (configurable):
    - ₱20, ₱50, ₱100, ₱500, ₱1000
    
    Protocol:
    - Accepted bills send a status byte indicating denomination
    - Device requires polling or continuous monitoring
    
    MAX232 Pinout:
    - Pin 1: GND
    - Pin 2: TX to RPi (GPIO 15 / RXD)
    - Pin 3: RX from RPi (GPIO 14 / TXD)
    - Pin 4: +5V
    - TB74 TX → MAX232 RX
    - TB74 RX → MAX232 TX
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

    def __init__(self, port='/dev/ttyAMA0', baudrate=9600, timeout=1.0):
        """
        Initialize the bill acceptor handler.

        Args:
            port (str): Serial port 
                - '/dev/ttyAMA0' on Raspberry Pi (hardware UART with MAX232)
                - '/dev/ttyUSB0' if using USB serial adapter
            baudrate (int): Serial communication speed (default 9600 for TB74)
            timeout (float): Serial read timeout in seconds
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

    def connect(self):
        """
        Connect to the bill acceptor via MAX232 serial adapter.

        Connection Flow:
        TB74 (RS-232) ↔ MAX232 Level Converter ↔ Raspberry Pi UART (/dev/ttyAMA0)

        Returns:
            bool: True if connection successful, False otherwise
        """
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
        if self.serial_conn and self.serial_conn.is_open:
            self.stop_reading()
            self.serial_conn.close()
            print("Bill acceptor disconnected")

    def start_reading(self):
        """Start the background thread that reads bill acceptor data."""
        if not self.serial_conn or not self.serial_conn.is_open:
            print("Error: Serial connection not open. Call connect() first.")
            return False

        if self.is_running:
            return True

        self.is_running = True
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
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    self._process_bill_data(data)
                else:
                    time.sleep(0.05)  # Sleep briefly to avoid busy-waiting
            except Exception as e:
                print(f"Error reading from bill acceptor: {e}")
                time.sleep(0.1)

    def _process_bill_data(self, data):
        """
        Process incoming bill acceptor data.

        Args:
            data (bytes): Raw data from serial port
        """
        for byte in data:
            # Check if this byte represents an accepted bill denomination
            if byte in self.BILL_DENOMINATIONS:
                denomination = self.BILL_DENOMINATIONS[byte]
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
