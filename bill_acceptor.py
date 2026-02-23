"""Bill acceptor module - clean implementation

This file provides a simple text-line parser for the Arduino/ESP32 forwarder
protocol used in this project. It intentionally keeps behavior minimal: parse
human-friendly lines ("Bill inserted: ₱100"), canonical lines ("BILL:100"),
and pulses ("PULSES:10" -> amount = 10 * 10). It debounces duplicates and
invokes a registered callback with the running bill total.

ACCEPTED DENOMINATIONS: ₱20, ₱50, ₱100 only
All other bills are automatically rejected.
"""

import serial
try:
    from serial.tools import list_ports
except Exception:
    list_ports = None

import threading
import time
from queue import Queue
import re


class BillAcceptor:
    # Accepted bill denominations in Philippine pesos
    ACCEPTED_DENOMINATIONS = [20, 50, 100]
    
    def __init__(self, port='/dev/ttyUSB1', baudrate=9600, timeout=1.0,
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

        self._last_bill_time_ms = 0
        self._last_bill_amount = None
        # Increase debounce to reduce false positives from noisy serial lines
        self._bill_debounce_ms = 800

        # Dispatcher queue to invoke callbacks outside of the serial read thread.
        # We enqueue the running received total and a background thread will call
        # the registered callback (if any) so callback exceptions don't affect
        # the serial read thread execution.
        self._dispatch_queue = Queue()
        self._dispatch_running = True
        self._dispatcher_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._dispatcher_thread.start()


    def _choose_stopbits_for_port(self, port_name: str):
        if not port_name:
            return serial.STOPBITS_TWO
        if 'ttyACM' in port_name or 'ttyUSB' in port_name or 'COM' in port_name:
            return serial.STOPBITS_ONE
        return serial.STOPBITS_TWO

    def connect(self):
        target = self.esp32_serial_port if (self.esp32_mode and self.esp32_serial_port) else self.port
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
                            line = line.strip()
                            if not line:
                                continue
                            print(f"DEBUG: Received serial line: '{line}'")
                            self._process_esp32_line(line)
                    except Exception:
                        self._process_raw_bytes(data)
                else:
                    time.sleep(0.05)
            except Exception as e:
                print(f"Error in bill read loop: {e}")
                time.sleep(0.1)

    def _process_raw_bytes(self, data: bytes):
        return

    def _process_esp32_line(self, line: str):
        if not line:
            return
        s = line.strip()
        s_upper = s.upper()
        print(f"===== DEBUG BILL ACCEPTOR: Processing line for parsing: '{s}' =====")

        # human friendly - matches "Bill inserted: ₱20" or "BILL INSERTED 20"
        m = re.search(r'BILL\s+INSERTED[:\s]*[\u20B1₱]?\s*(\d+)', s_upper)
        if m:
            try:
                amount = int(m.group(1))
                print(f"DEBUG: Parsed human-friendly bill amount {amount}")
                self._debounced_register(amount)
                return
            except Exception:
                pass

        # canonical
        if s_upper.startswith('BILL:'):
            try:
                amount = int(s.split(':', 1)[1])
                print(f"DEBUG: Parsed BILL:<amount> = {amount}")
                self._debounced_register(amount)
                return
            except Exception:
                print(f"Unrecognized BILL line: {line}")
                return

        # pulses
        if s_upper.startswith('PULSES:'):
            try:
                cnt = int(s.split(':', 1)[1])
                amount = cnt * 10
                print(f"DEBUG: Parsed PULSES:{cnt} -> amount {amount}")
                # Only register if resulting amount matches an accepted denomination
                if amount in self.ACCEPTED_DENOMINATIONS:
                    self._debounced_register(amount)
                else:
                    print(f"DEBUG: Ignored PULSES amount {amount} (not an accepted denomination)")
                return
            except Exception:
                pass

        # tolerant fallback parsing: some forwarders send different human-friendly lines
        # e.g. "BILL 100", "INSERTED 100", "PAYMENT: 100", or just "₱100". Try to
        # extract an amount if the line contains bill-related keywords or currency symbols.
        try:
            # Only use fallback if the line includes explicit bill-related keywords
            if any(k in s_upper for k in ('INSERT', 'BILL')) or ('₱' in s or '\u20B1' in s):
                m2 = re.search(r'[:\s]*[\u20B1₱]?\s*(\d{2,4})', s)
                if m2:
                    amount = int(m2.group(1))
                    # Only accept known denominations to avoid noise (e.g., stray '20' parsed)
                    if amount in self.ACCEPTED_DENOMINATIONS:
                        print(f"DEBUG: Fallback parsed accepted amount {amount} from '{s}'")
                        self._debounced_register(amount)
                    else:
                        print(f"DEBUG: Fallback parsed amount {amount} ignored (not an accepted denomination)")
                    return
        except Exception:
            pass

        # hex
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
                print(f"DEBUG: Debounce ignored duplicate amount {amount}")
                return
            # Record last bill metadata under lock but call _register_bill outside the lock
            self._last_bill_amount = amount
            self._last_bill_time_ms = now_ms
        print(f"DEBUG: Registering bill amount {amount}")
        # Call registration without holding self._lock to avoid deadlocks
        self._register_bill(amount)

    def _is_valid_denomination(self, denomination: int) -> bool:
        """Check if the bill is one of the accepted denominations: 20, 50, 100 pesos."""
        return denomination in self.ACCEPTED_DENOMINATIONS

    def _register_bill(self, denomination: int):
        # Validate denomination - only accept 20, 50, 100 peso bills
        if not self._is_valid_denomination(denomination):
            print(f"⚠ Bill REJECTED: ₱{denomination} (only ₱20, ₱50, ₱100 are accepted)")
            # Send rejection signal to bill acceptor hardware if possible
            try:
                if self.serial_conn and getattr(self.serial_conn, 'is_open', False):
                    self.serial_conn.write(b'REJECT\n')
                    self.serial_conn.flush()
            except Exception:
                pass
            return
        
        with self._lock:
            self.received_amount += denomination
            self.bill_queue.put(denomination)
        print(f"✓ Bill accepted: ₱{denomination} (Total: ₱{self.received_amount:.2f})")
        # Enqueue dispatch request so a separate thread invokes the registered callback.
        try:
            print(f"DEBUG: Enqueueing bill callback for amount {self.received_amount}")
            self._dispatch_queue.put_nowait(self.received_amount)
        except Exception as e:
            print(f"DEBUG: Failed to enqueue callback: {e}")

    def _dispatch_loop(self):
        """Background loop to call the registered callback with the latest total.

        Running in a dedicated daemon thread so serial reading isn't blocked by
        slow callbacks or GUI interactions. If no callback is set the value is
        dropped with a debug message.
        """
        import time, traceback
        while True:
            try:
                amt = self._dispatch_queue.get(timeout=1.0)
            except Exception:
                # Timeout - check if we should keep running
                if not getattr(self, '_dispatch_running', True):
                    break
                continue
            # Recognize sentinel None to stop the dispatcher
            if amt is None:
                break
            try:
                if self._callback:
                    print(f"DEBUG: Dispatcher invoking callback on thread {threading.current_thread().name} with amount={amt}")
                    try:
                        self._callback(amt)
                    except Exception as e:
                        print(f"DEBUG: Dispatcher callback error: {e}")
                        traceback.print_exc()
                else:
                    print(f"DEBUG: Dispatcher dropped callback (no callback registered) for amount={amt}")
            except Exception as e:
                print(f"DEBUG: Dispatcher loop unexpected error: {e}")
                try:
                    traceback.print_exc()
                except Exception:
                    pass

    def set_callback(self, callback):
        try:
            print(f"DEBUG: BillAcceptor.set_callback: callback set = {bool(callback)}, callback={callback}")
        except Exception:
            pass
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
        # Stop dispatcher thread cleanly
        try:
            self._dispatch_running = False
            try:
                self._dispatch_queue.put_nowait(None)
            except Exception:
                pass
            try:
                if hasattr(self, '_dispatcher_thread') and self._dispatcher_thread.is_alive():
                    self._dispatcher_thread.join(timeout=1.0)
            except Exception:
                pass
        except Exception:
            pass
        self.disconnect()


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
