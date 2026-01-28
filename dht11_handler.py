import tkinter as tk
from tkinter import ttk
import time
import platform

# Conditional imports for Raspberry Pi
try:
    import board
    import adafruit_dht
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    # Use mock for development on non-RPi systems
    from rpi_gpio_mock import GPIO


class DHT22Sensor:
    """
    DHT22 sensor handler compatible with Raspberry Pi 4.
    Uses Adafruit's circuit python library for reliable readings.
    """
    
    def __init__(self, pin=27):
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
        
        if DHT_AVAILABLE and platform.system() == "Linux":
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
        
        # Enforce minimum read interval
        if (current_time - self.last_read_time) < self.min_read_interval:
            return (None, None)
        
        try:
            if self.sensor is not None and DHT_AVAILABLE:
                # Real hardware reading
                temperature = self.sensor.temperature
                humidity = self.sensor.humidity
                self.last_read_time = current_time
                return (humidity, temperature)
            else:
                # Simulated reading for development
                import random
                temperature = round(random.uniform(20, 30), 1)
                humidity = round(random.uniform(40, 60), 1)
                self.last_read_time = current_time
                return (humidity, temperature)
        except RuntimeError:
            # Common DHT22 error, return None to retry
            return (None, None)
        except Exception as e:
            print(f"Sensor read error: {e}")
            return (None, None)


class DHT22Display(tk.Frame):
    """Display widget for DHT22 sensor readings."""
    
    def __init__(self, master=None, sensor_number=1):
        super().__init__(master)
        self.master = master
        self.sensor_number = sensor_number
        
        # Create sensor with specified GPIO pin
        pin = 4 if sensor_number == 1 else 17
        # Create sensor with specified GPIO pin
        pin = 27 if sensor_number == 1 else 22
        self.sensor = DHT22Sensor(pin=pin)
        
        self.create_widgets()
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
