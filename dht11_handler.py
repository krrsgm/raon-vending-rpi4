import tkinter as tk
from tkinter import ttk
import time
import random  # For simulation
from rpi_gpio_mock import GPIO  # Using our mock for development

# TODO: Replace this with actual DHT11 reading code on the Raspberry Pi
class DHT11Sensor:
    def __init__(self, pin=4):
        self.pin = pin  # Allow different GPIO pins for different sensors
        
    def read(self):
        # Simulate sensor readings for development
        # Replace this with actual DHT11 reading code on the Raspberry Pi
        temperature = random.uniform(20, 30)
        humidity = random.uniform(40, 60)
        return humidity, temperature

class DHT11Display(tk.Frame):
    def __init__(self, master=None, sensor_number=1):
        super().__init__(master)
        self.master = master
        self.sensor_number = sensor_number
        # Create sensor with specified GPIO pin
        pin = 4 if sensor_number == 1 else 17  # GPIO4 for Components, GPIO17 for Payment
        self.sensor = DHT11Sensor(pin=pin)
        self.create_widgets()
        self.update_readings()

    def create_widgets(self):
        # Main container with padding
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
        """Update temperature and humidity readings every 2 seconds"""
        try:
            # Read from sensor
            humidity, temperature = self.sensor.read()
            if humidity is not None and temperature is not None:
                self.temp_reading.config(text=f"{temperature:.1f}")
                self.humid_reading.config(text=f"{humidity:.1f}")
            else:
                self.temp_reading.config(text="Error")
                self.humid_reading.config(text="Error")

            # Update last updated time
            current_time = time.strftime("%H:%M:%S")
            self.last_updated.config(text=f"Last updated: {current_time}")
        except Exception as e:
            print(f"Error reading sensor: {e}")
            self.temp_reading.config(text="Error")
            self.humid_reading.config(text="Error")
        
        # Schedule next update
        self.after(2000, self.update_readings)

def main():
    root = tk.Tk()
    root.title("DHT11 Monitor")
    
    # Create frame to hold both sensors side by side
    sensors_frame = ttk.Frame(root)
    sensors_frame.pack(padx=10, pady=10, fill='both', expand=True)
    
    # Add both sensors
    components_sensor = DHT11Display(sensors_frame, sensor_number=1)
    components_sensor.grid(row=0, column=0, padx=10, pady=5, sticky='nsew')
    
    payment_sensor = DHT11Display(sensors_frame, sensor_number=2)
    payment_sensor.grid(row=0, column=1, padx=10, pady=5, sticky='nsew')
    
    # Configure grid weights
    sensors_frame.columnconfigure(0, weight=1)
    sensors_frame.columnconfigure(1, weight=1)
    
    # Set window size and position
    window_width = 800  # Increased for two sensors
    window_height = 300
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    root.mainloop()

if __name__ == "__main__":
    main()