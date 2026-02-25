import tkinter as tk
from tkinter import ttk
import time
import platform
import threading
import re

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except Exception:
    SERIAL_AVAILABLE = False

# Conditional imports for Raspberry Pi
try:
    import board
    import adafruit_dht
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    # Use mock for development on non-RPi systems
    from rpi_gpio_mock import GPIO


class SharedSerialReader(threading.Thread):
    """Background reader for DHT22/IR/coin/bill values printed over Arduino serial."""
    def __init__(self, port, baudrate=115200):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.running = True
        self._lock = threading.Lock()
        # Store latest readings per label
        self.readings = {
            'DHT1': {'temp': None, 'humidity': None},
            'DHT2': {'temp': None, 'humidity': None},
        }
        self.ir_states = {'IR1': None, 'IR2': None}
        self.coin_total = 0.0
        self.bill_total = 0.0
        self._coin_callbacks = []
        self._bill_callbacks = []
        self.connected = False
        # Match lines like: "DHT1: 25.0C 60%"
        self.pattern = re.compile(r"(DHT1|DHT2).*?:\s*([\-0-9.]+)\s*C\s*([\-0-9.]+)\s*%?", re.IGNORECASE)
        self.ir1_pattern = re.compile(r"IR1.*?:\s*(BLOCKED|CLEAR)", re.IGNORECASE)
        self.ir2_pattern = re.compile(r"IR2.*?:\s*(BLOCKED|CLEAR)", re.IGNORECASE)
        self.coin_pattern = re.compile(r"\[COIN\].*?Value:\s*[^\d-]*([-\d.]+).*?Total:\s*[^\d-]*([-\d.]+)", re.IGNORECASE)
        self.balance_pattern = re.compile(r"BALANCE:\s*[^\d-]*([-\d.]+)", re.IGNORECASE)
        self.bill_pattern = re.compile(r"(?:BILL\s+INSERTED|BILL)[:\s]*[\u20B1â‚±]?\s*(\d+)", re.IGNORECASE)

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connected = True
            print(f"[ESP32DHTReader] Connected to ESP32 on {self.port}")
        except Exception as e:
            print(f"[ESP32DHTReader] Failed to open {self.port}: {e}")
            self.connected = False
            return

        while self.running:
            try:
                if self.ser and self.ser.is_open:
                    line = self.ser.readline().decode(errors="ignore").strip()
                    if not line:
                        continue
                    m = self.pattern.search(line)
                    if m:
                        label = m.group(1).upper()
                        try:
                            temp = float(m.group(2))
                            humid = float(m.group(3))
                        except Exception:
                            continue
                        with self._lock:
                            if label in self.readings:
                                self.readings[label]['temp'] = temp
                                self.readings[label]['humidity'] = humid
                        continue
                    m1 = self.ir1_pattern.search(line)
                    if m1:
                        state = m1.group(1).upper() == "BLOCKED"
                        with self._lock:
                            self.ir_states['IR1'] = state
                        continue
                    m2 = self.ir2_pattern.search(line)
                    if m2:
                        state = m2.group(1).upper() == "BLOCKED"
                        with self._lock:
                            self.ir_states['IR2'] = state
                        continue
                    m3 = self.coin_pattern.search(line)
                    if m3:
                        try:
                            total = float(m3.group(2))
                        except Exception:
                            total = None
                        if total is not None:
                            with self._lock:
                                self.coin_total = total
                            callbacks = list(self._coin_callbacks)
                            for cb in callbacks:
                                try:
                                    cb(total)
                                except Exception:
                                    pass
                        continue
                    m4 = self.balance_pattern.search(line)
                    if m4:
                        try:
                            total = float(m4.group(1))
                        except Exception:
                            total = None
                        if total is not None:
                            with self._lock:
                                self.coin_total = total
                        continue
                    m5 = self.bill_pattern.search(line)
                    if m5:
                        try:
                            amount = float(m5.group(1))
                        except Exception:
                            amount = None
                        if amount is not None:
                            with self._lock:
                                self.bill_total += amount
                            callbacks = list(self._bill_callbacks)
                            for cb in callbacks:
                                try:
                                    cb(self.bill_total)
                                except Exception:
                                    pass
                        continue
            except Exception as e:
                print(f"[ESP32DHTReader] Read error: {e}")
                continue

    def get_reading(self, label):
        with self._lock:
            data = self.readings.get(label.upper(), {})
            return data.get('humidity'), data.get('temp')

    def get_ir_state(self, label):
        with self._lock:
            return self.ir_states.get(label.upper(), None)

    def add_coin_callback(self, callback):
        if callback and callback not in self._coin_callbacks:
            self._coin_callbacks.append(callback)

    def add_bill_callback(self, callback):
        if callback and callback not in self._bill_callbacks:
            self._bill_callbacks.append(callback)

    def get_coin_total(self):
        with self._lock:
            return self.coin_total

    def get_bill_total(self):
        with self._lock:
            return self.bill_total

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()


def _autodetect_serial_port():
    if not SERIAL_AVAILABLE:
        return None
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        mfg = (p.manufacturer or "").lower()
        keywords = ["esp32", "arduino", "cp210", "ch340", "silicon labs"]
        if any(kw in desc or kw in mfg for kw in keywords):
            return p.device
    return ports[0].device if ports else None


# Backwards-compatible alias (legacy naming)
_autodetect_esp32_port = _autodetect_serial_port


def get_shared_serial_reader(port=None, baudrate=115200):
    """Return a shared serial reader instance for DHT/IR."""
    if not hasattr(get_shared_serial_reader, "_readers"):
        get_shared_serial_reader._readers = {}
        get_shared_serial_reader._lock = threading.Lock()
    if not port:
        port = _autodetect_serial_port()
    if not port:
        return None
    key = f"{port}:{int(baudrate)}"
    with get_shared_serial_reader._lock:
        reader = get_shared_serial_reader._readers.get(key)
        if not reader:
            reader = SharedSerialReader(port, baudrate)
            reader.start()
            get_shared_serial_reader._readers[key] = reader
        return reader


class DHT22Sensor:
    """
    DHT22 sensor handler compatible with Raspberry Pi 4.
    Uses Adafruit's circuit python library for reliable readings.
    """
    
    def __init__(self, pin=27, use_esp32_serial=False, esp32_port=None, esp32_baud=115200, esp32_label=None):
        """
        Initialize DHT22 sensor.
        
        Args:
            pin (int): GPIO pin number (BCM numbering)
                      Default pin 27 for Sensor 1
                      Pin 22 for Sensor 2
        """
        self.pin = pin
        self.sensor = None
        self.last_read_time = 0
        self.min_read_interval = 2.0  # DHT22 minimum 2 second interval
        self.use_esp32_serial = use_esp32_serial
        self.esp32_label = esp32_label

        # Use a class-level cache so multiple DHT22Sensor instances
        # (e.g. one in `TECController` and one in UI) don't hammer
        # the same GPIO pin independently. Cache stores tuple
        # (humidity, temperature, last_time).
        if not hasattr(DHT22Sensor, '_cache'):
            DHT22Sensor._cache = {}
            DHT22Sensor._cache_lock = threading.Lock()
        
        if self.use_esp32_serial:
            reader = get_shared_serial_reader(esp32_port, esp32_baud)
            if reader:
                self.sensor = reader
                if not self.esp32_label:
                    # Default mapping: pin order -> DHT1/DHT2
                    self.esp32_label = "DHT1" if pin == 27 else "DHT2"
            else:
                print("[DHT22Sensor] WARNING: Arduino serial requested but port not found")
        elif DHT_AVAILABLE and platform.system() == "Linux":
            try:
                # Map BCM pin numbers to board pins for RPi4
                pin_map = {
                    27: board.D27,  # GPIO27 - DHT22 Sensor 1
                    22: board.D22,  # GPIO22 - DHT22 Sensor 2
                }
                board_pin = pin_map.get(pin, board.D4)
                self.sensor = adafruit_dht.DHT22(board_pin, use_pulseio=False)
                print(f"DHT22 initialized on GPIO{pin}")
            except Exception as e:
                print(f"Failed to initialize DHT22: {e}")
                self.sensor = None
        else:
            if not DHT_AVAILABLE:
                print("DHT22 library not available - using simulated readings")
            if platform.system() != "Linux":
                print(f"Running on {platform.system()} - using simulated sensor readings")
    
    def read(self):
        """
        Read temperature and humidity from sensor.
        Returns (humidity, temperature) or (None, None) on error.
        """
        current_time = time.time()
        # Check class-level cache first to ensure reads for the same
        # pin are rate-limited across all instances.
        try:
            with DHT22Sensor._cache_lock:
                cached = DHT22Sensor._cache.get(self.pin)
                if cached:
                    h, t, last_time = cached
                    if (current_time - last_time) < self.min_read_interval:
                        # Return cached value (rate-limited)
                        return (h, t)
        except Exception:
            # If cache isn't available for any reason, fall back to instance timing
            if (current_time - self.last_read_time) < self.min_read_interval:
                return (None, None)
        
        try:
            if self.use_esp32_serial and self.sensor is not None:
                humidity, temperature = self.sensor.get_reading(self.esp32_label or "DHT1")
                if humidity is not None and temperature is not None:
                    self.last_read_time = current_time
                    try:
                        with DHT22Sensor._cache_lock:
                            DHT22Sensor._cache[self.pin] = (humidity, temperature, current_time)
                    except Exception:
                        pass
                return (humidity, temperature)
            if self.sensor is not None and DHT_AVAILABLE:
                # Real hardware reading
                temperature = self.sensor.temperature
                humidity = self.sensor.humidity
                self.last_read_time = current_time
                # Update class cache
                try:
                    with DHT22Sensor._cache_lock:
                        DHT22Sensor._cache[self.pin] = (humidity, temperature, current_time)
                except Exception:
                    pass
                return (humidity, temperature)
            else:
                # Simulated reading for development
                import random
                temperature = round(random.uniform(20, 30), 1)
                humidity = round(random.uniform(40, 60), 1)
                self.last_read_time = current_time
                try:
                    with DHT22Sensor._cache_lock:
                        DHT22Sensor._cache[self.pin] = (humidity, temperature, current_time)
                except Exception:
                    pass
                return (humidity, temperature)
        except RuntimeError as e:
            # Common DHT22 error, return None to retry
            return (None, None)
        except Exception as e:
            print(f"[DHT22Sensor] GPIO{self.pin} read error: {e}")
            return (None, None)


class DHT22Display(tk.Frame):
    """Display widget for DHT22 sensor readings."""
    
    def __init__(self, master=None, sensor_number=1):
        super().__init__(master)
        self.master = master
        self.sensor_number = sensor_number
        
        # Create sensor with specified GPIO pin
        pin = 27 if sensor_number == 1 else 22
        self.sensor = DHT22Sensor(pin=pin)
        
        self.create_widgets()
        # Track last known readings to avoid None comparison errors
        self.last_humidity = None
        self.last_temperature = None
        self.update_readings()

    def create_widgets(self):
        """Create UI widgets."""
        self.container = ttk.Frame(self)
        self.container.pack(padx=5, pady=2, fill='both', expand=True)

        # Style configuration
        style = ttk.Style()
        style.configure('Reading.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('Unit.TLabel', font=('Helvetica', 12))
        style.configure('Title.TLabel', font=('Helvetica', 14, 'bold'))
        style.configure('Location.TLabel', font=('Helvetica', 12))

        # Title with location
        location_text = "Components" if self.sensor_number == 1 else "Payment"
        self.title_label = ttk.Label(
            self.container,
            text=location_text,
            style='Title.TLabel'
        )
        self.title_label.pack(pady=(0, 4))

        # Temperature frame
        self.temp_frame = ttk.Frame(self.container)
        self.temp_frame.pack(fill='x', pady=2)
        
        self.temp_icon = ttk.Label(self.temp_frame, text="🌡️", font=('Helvetica', 16))
        self.temp_icon.pack(side='left', padx=5)
        
        self.temp_reading = ttk.Label(
            self.temp_frame,
            text="--",
            style='Reading.TLabel'
        )
        self.temp_reading.pack(side='left')
        
        self.temp_unit = ttk.Label(
            self.temp_frame,
            text="°C",
            style='Unit.TLabel'
        )
        self.temp_unit.pack(side='left')

        # Humidity frame
        self.humid_frame = ttk.Frame(self.container)
        self.humid_frame.pack(fill='x', pady=2)
        
        self.humid_icon = ttk.Label(self.humid_frame, text="💧", font=('Helvetica', 16))
        self.humid_icon.pack(side='left', padx=5)
        
        self.humid_reading = ttk.Label(
            self.humid_frame,
            text="--",
            style='Reading.TLabel'
        )
        self.humid_reading.pack(side='left')
        
        self.humid_unit = ttk.Label(
            self.humid_frame,
            text="%",
            style='Unit.TLabel'
        )
        self.humid_unit.pack(side='left')

        # Last updated
        self.last_updated = ttk.Label(
            self.container,
            text="Last updated: Never",
            font=('Helvetica', 10)
        )
        self.last_updated.pack(pady=(20, 0))

    def update_readings(self):
        """Update temperature and humidity readings every 2 seconds."""
        try:
            humidity, temperature = self.sensor.read()
            
            # Only update if we have new valid data
            if humidity is not None and temperature is not None:
                if (humidity != self.last_humidity or 
                    temperature != self.last_temperature):
                    self.temp_reading.config(text=f"{temperature:.1f}")
                    self.humid_reading.config(text=f"{humidity:.1f}")
                    self.last_humidity = humidity
                    self.last_temperature = temperature
            else:
                # Show last known values or error
                if self.last_temperature is None:
                    self.temp_reading.config(text="Waiting...")
                    self.humid_reading.config(text="Waiting...")

            # Update last updated time
            current_time = time.strftime("%H:%M:%S")
            self.last_updated.config(text=f"Last updated: {current_time}")
        except Exception as e:
            print(f"Error updating readings: {e}")
        
        # Schedule next update (2 second minimum for DHT22)
        self.after(2000, self.update_readings)


def main():
    """Run DHT22 sensor display."""
    root = tk.Tk()
    root.title("DHT22 Monitor - Raspberry Pi 4")
    
    # Create frame to hold both sensors side by side
    sensors_frame = ttk.Frame(root)
    sensors_frame.pack(padx=10, pady=10, fill='both', expand=True)
    
    # Add both sensors
    components_sensor = DHT22Display(sensors_frame, sensor_number=1)
    components_sensor.grid(row=0, column=0, padx=10, pady=5, sticky='nsew')
    
    payment_sensor = DHT22Display(sensors_frame, sensor_number=2)
    payment_sensor.grid(row=0, column=1, padx=10, pady=5, sticky='nsew')
    
    # Configure grid weights
    sensors_frame.columnconfigure(0, weight=1)
    sensors_frame.columnconfigure(1, weight=1)
    
    # Set window size and position
    window_width = 800
    window_height = 300
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    root.mainloop()


if __name__ == "__main__":
    main()
