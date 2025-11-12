import serial
try:
    # pyserial >=3.0 provides tools.list_ports
    from serial.tools import list_ports
except Exception:
    list_ports = None
import threading
import time
from queue import Queue
import re


class BillAcceptor:
    """Simple BillAcceptor that reads line-based events from a serial proxy

    It accepts the following text formats from the Arduino/ESP32 forwarder:
      BILL:<amount>
      Bill inserted: ₱<amount>
      PULSES:<n>    (mapped to amount = n * 10 by default)

    This class debounces duplicate reports and calls an optional callback
    when a bill is registered.
    """

    def __init__(self, port='/dev/ttyAMA0', baudrate=9600, timeout=1.0,
                 esp32_mode=False, esp32_serial_port=None, esp32_host=None, esp32_port=5000):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.is_running = False
        self.read_thread = None
        self.received_amount = 0.0
        self.bill_queue = Queue()
        self._lock = threading.Lock()
        self._callback = None

        self.esp32_mode = bool(esp32_mode)
        self.esp32_serial_port = esp32_serial_port
        self.esp32_host = esp32_host
        self.esp32_port = esp32_port

        # Debounce repeated identical bill reports (milliseconds)
        self._last_bill_time_ms = 0
        self._last_bill_amount = None
        self._bill_debounce_ms = 300

    def _choose_stopbits_for_port(self, port_name: str):
        if not port_name:
            return serial.STOPBITS_TWO
        if 'ttyACM' in port_name or 'ttyUSB' in port_name or 'COM' in port_name:
            return serial.STOPBITS_ONE
        return serial.STOPBITS_TWO

    def connect(self):
        """Open the configured serial port (or autodetect a USB-serial device)."""
        target = None
        if self.esp32_mode and self.esp32_serial_port:
            target = self.esp32_serial_port
        else:
            target = self.port

        try:
            stopbits = self._choose_stopbits_for_port(target)
            self.serial_conn = serial.Serial(
                port=target,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                stopbits=stopbits,
                parity=serial.PARITY_NONE,
                timeout=self.timeout,
            )
            print(f"Bill acceptor connected to {target} at {self.serial_conn.baudrate} baud")
            return True
        except Exception as e:
            # fallback: try to autodetect a USB serial device
            print(f"Failed to open {target}: {e}. Trying to autodetect USB serial...")
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
                        timeout=self.timeout,
                    )
                    print(f"Bill acceptor autodetected and connected to {autodetected}")
                    return True
                except Exception as e2:
                    print(f"Autodetect open failed: {e2}")
            return False

    def _auto_find_usb_serial(self):
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

        for dev, desc in ports:
            d = (desc or '').lower()
            if 'arduino' in d or 'cp210' in d or 'ftdi' in d or 'ch340' in d or 'usb serial' in d:
                return dev
        if ports:
            return ports[0][0]
        return None

    def disconnect(self):
        self.stop_reading()
        try:
            if self.serial_conn and getattr(self.serial_conn, 'is_open', False):
                self.serial_conn.close()
        except Exception:
            pass

    def start_reading(self):
        if not self.serial_conn:
            print("Serial connection not open; call connect() first")
            return False
        if self.is_running:
            return True
        self.is_running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        print("Bill acceptor reading started")
        return True

    def stop_reading(self):
        self.is_running = False
        if self.read_thread:
            self.read_thread.join(timeout=1.0)

    def _read_loop(self):
        while self.is_running:
            try:
                if not self.serial_conn:
                    time.sleep(0.05)
                    continue
                in_wait = getattr(self.serial_conn, 'in_waiting', 0)
                if in_wait > 0:
                    data = self.serial_conn.read(in_wait)
                    try:
                        text = data.decode('utf-8', errors='ignore')
                        for line in text.splitlines():
                            self._process_esp32_line(line.strip())
                    except Exception:
                        self._process_raw_bytes(data)
                else:
                    time.sleep(0.05)
            except Exception as e:
                print(f"Error in bill read loop: {e}")
                time.sleep(0.1)

    def _process_raw_bytes(self, data: bytes):
        # If a project wants to support raw TB74 bytes, they can extend this.
        # For now we ignore raw binary for the USB-forwarder workflow.
        return

    def _process_esp32_line(self, line: str):
        if not line:
            return
        s = line.strip()
        s_upper = s.upper()

        # 1) human friendly: "Bill inserted: ₱50" or "Bill inserted: 50"
        m = re.search(r'BILL\s*INSERTED[:\s]*\u20B1?\s*(\d+)', s_upper)
        if m:
            try:
                amount = int(m.group(1))
                self._debounced_register(amount)
                return
            except Exception:
                pass

        # 2) canonical: BILL:<amount>
        if s_upper.startswith('BILL:'):
            try:
                amount = int(s.split(':', 1)[1])
                self._debounced_register(amount)
                return
            except Exception:
                print(f"Unrecognized BILL line: {line}")
                return

        # 3) pulses: PULSES:<n> -> default mapping each pulse = 10 pesos
        if s_upper.startswith('PULSES:'):
            try:
                cnt = int(s.split(':', 1)[1])
                amount = cnt * 10
                self._debounced_register(amount)
                return
            except Exception:
                pass

        # 4) hex byte like "41" or "0x41" -> optional mapping (not used in USB-forwarder)
        try:
            hexval = s
            if hexval.startswith('0X'):
                hexval = hexval[2:]
            if all(c in '0123456789ABCDEF' for c in hexval.upper()) and len(hexval) % 2 == 0:
                b = bytes.fromhex(hexval)
                self._process_raw_bytes(b)
        except Exception:
            pass

    def _debounced_register(self, amount: int):
        now_ms = int(time.time() * 1000)
        with self._lock:
            if self._last_bill_amount == amount and (now_ms - self._last_bill_time_ms) < self._bill_debounce_ms:
                return
            self._last_bill_amount = amount
            self._last_bill_time_ms = now_ms
        self._register_bill(amount)

    def _register_bill(self, denomination: int):
        with self._lock:
            self.received_amount += denomination
            self.bill_queue.put(denomination)
        print(f"Bill accepted: ₱{denomination} (Total: ₱{self.received_amount:.2f})")
        if self._callback:
            try:
                self._callback(self.received_amount)
            except Exception as e:
                print(f"Callback error: {e}")

    def set_callback(self, callback):
        self._callback = callback

    def get_received_amount(self):
        with self._lock:
            return self.received_amount

    def get_last_bills(self, count=None):
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
        with self._lock:
            self.received_amount = 0.0
            while not self.bill_queue.empty():
                try:
                    self.bill_queue.get_nowait()
                except Exception:
                    break
        print("Bill acceptor amount reset")

    def send_command(self, command_bytes: bytes):
        try:
            if self.serial_conn and getattr(self.serial_conn, 'is_open', False):
                self.serial_conn.write(command_bytes)
                return True
        except Exception as e:
            print(f"Failed to send command to bill acceptor: {e}")
        return False

    def cleanup(self):
        self.disconnect()


# Mock implementation for testing without hardware
class MockBillAcceptor(BillAcceptor):
    def __init__(self):
        super().__init__()
        self.is_mock = True
        print("MockBillAcceptor initialized (testing mode)")

    def connect(self):
        print("Mock: Bill acceptor connected")
        return True

    def disconnect(self):
        self.is_running = False
        print("Mock: Bill acceptor disconnected")

    def start_reading(self):
        self.is_running = True
        print("Mock: Bill acceptor reading started")
        return True

    def send_command(self, command_bytes: bytes):
        return True

    def simulate_bill_accepted(self, denomination: int):
        with self._lock:
            self.received_amount += denomination
            self.bill_queue.put(denomination)
        print(f"Mock: Bill accepted: ₱{denomination} (Total: ₱{self.received_amount:.2f})")
        if self._callback:
            try:
                self._callback(self.received_amount)
            except Exception as e:
                print(f"Callback error: {e}")
