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
        self.sensor = DHT11Sensor(pin=4 if sensor_number == 1 else 17)  # GPIO4 or GPIO17
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
        self.title_label = ttk.Label(
            self.container,
            text=f"Sensor {self.sensor_number}",
            style='Title.TLabel'
        )
        self.title_label.pack(pady=(0, 2))
        
        location_text = "Components" if self.sensor_number == 1 else "Payment"
        self.location_label = ttk.Label(
            self.container,
            text=location_text,
            style='Location.TLabel'
        )
        self.location_label.pack(pady=(0, 4))

        # Temperature frame for Sensor 1
        self.temp_frame1 = ttk.Frame(self.container)
        self.temp_frame1.pack(fill='x', pady=2)
        
        # Sensor 1 Temperature
        self.temp_icon1 = ttk.Label(self.temp_frame1, text="🌡️", font=('Helvetica', 16))
        self.temp_icon1.pack(side='left', padx=5)
        
        self.temp_reading1 = ttk.Label(
            self.temp_frame1,
            text="--",
            style='Reading.TLabel'
        )
        self.temp_reading1.pack(side='left')
        
        self.temp_unit1 = ttk.Label(
            self.temp_frame1,
            text="°C",
            style='Unit.TLabel'
        )
        self.temp_unit1.pack(side='left')

        # Humidity frame for Sensor 1
        self.humid_frame1 = ttk.Frame(self.container)
        self.humid_frame1.pack(fill='x', pady=2)
        
        self.humid_icon1 = ttk.Label(self.humid_frame1, text="💧", font=('Helvetica', 16))
        self.humid_icon1.pack(side='left', padx=5)
        
        self.humid_reading1 = ttk.Label(
            self.humid_frame1,
            text="--",
            style='Reading.TLabel'
        )
        self.humid_reading1.pack(side='left')
        
        self.humid_unit1 = ttk.Label(
            self.humid_frame1,
            text="%",
            style='Unit.TLabel'
        )
        self.humid_unit1.pack(side='left')

        # Separator
        ttk.Separator(self.container, orient='horizontal').pack(fill='x', pady=4)

        # Sensor 2 Label
        self.sensor2_label = ttk.Label(
            self.container,
            text="Sensor 2",
            style='Title.TLabel'
        )
        self.sensor2_label.pack(pady=(2, 1))

        # Temperature frame for Sensor 2
        self.temp_frame2 = ttk.Frame(self.container)
        self.temp_frame2.pack(fill='x', pady=2)
        
        self.temp_icon2 = ttk.Label(self.temp_frame2, text="🌡️", font=('Helvetica', 16))
        self.temp_icon2.pack(side='left', padx=5)
        
        self.temp_reading2 = ttk.Label(
            self.temp_frame2,
            text="--",
            style='Reading.TLabel'
        )
        self.temp_reading2.pack(side='left')
        
        self.temp_unit2 = ttk.Label(
            self.temp_frame2,
            text="°C",
            style='Unit.TLabel'
        )
        self.temp_unit2.pack(side='left')

        # Humidity frame for Sensor 2
        self.humid_frame2 = ttk.Frame(self.container)
        self.humid_frame2.pack(fill='x', pady=2)
        
        self.humid_icon2 = ttk.Label(self.humid_frame2, text="💧", font=('Helvetica', 16))
        self.humid_icon2.pack(side='left', padx=5)
        
        self.humid_reading2 = ttk.Label(
            self.humid_frame2,
            text="--",
            style='Reading.TLabel'
        )
        self.humid_reading2.pack(side='left')
        
        self.humid_unit2 = ttk.Label(
            self.humid_frame2,
            text="%",
            style='Unit.TLabel'
        )
        self.humid_unit2.pack(side='left')

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
            humidity, temperature = self.sensor.read()
            if humidity is not None and temperature is not None:
                self.temp_reading1.config(text=f"{temperature:.1f}")
                self.humid_reading1.config(text=f"{humidity:.1f}")
                
                # Update last updated time
                current_time = time.strftime("%H:%M:%S")
                self.last_updated.config(text=f"Last updated: {current_time}")
            else:
                self.temp_reading1.config(text="Error")
                self.humid_reading1.config(text="Error")
        except Exception as e:
            print(f"Error reading sensor: {e}")
            self.temp_reading.config(text="Error")
            self.humid_reading.config(text="Error")
        
        # Schedule next update
        self.after(2000, self.update_readings)

def main():
    root = tk.Tk()
    root.title("DHT11 Monitor")
    
    # Set window size and position
    window_width = 400
    window_height = 300
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    app = DHT11Display(root)
    app.pack(fill='both', expand=True)
    root.mainloop()

if __name__ == "__main__":
    main()