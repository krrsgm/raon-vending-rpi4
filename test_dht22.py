#!/usr/bin/env python3
"""
DHT22 Sensor Test Script
Displays real-time temperature and humidity readings
"""

import tkinter as tk
from tkinter import ttk
import time
import threading
import platform

# Conditional imports for Raspberry Pi
try:
    import board
    import adafruit_dht
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    print("Warning: Adafruit DHT library not available - will use simulated readings")


class DHT22Sensor:
    """DHT22 sensor handler"""
    
    def __init__(self, pin):
        """
        Initialize DHT22 sensor.
        
        Args:
            pin (int): GPIO pin number (BCM numbering)
        """
        self.pin = pin
        self.sensor = None
        self.last_read_time = 0
        self.min_read_interval = 2.0  # Minimum 2 second interval for DHT22
        
        if DHT_AVAILABLE and platform.system() == "Linux":
            try:
                # Map BCM pin numbers to board pins
                pin_map = {
                    27: board.D27,
                    22: board.D22,
                }
                board_pin = pin_map.get(pin, board.D27)
                self.sensor = adafruit_dht.DHT22(board_pin, use_pulseio=False)
                print(f"✓ DHT22 initialized on GPIO{pin}")
            except Exception as e:
                print(f"✗ Failed to initialize DHT22 on GPIO{pin}: {e}")
                self.sensor = None
        else:
            if not DHT_AVAILABLE:
                print(f"ℹ DHT22 library not available - using simulated readings for GPIO{pin}")
            else:
                print(f"ℹ Running on {platform.system()} - using simulated readings for GPIO{pin}")
    
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
            if self.sensor is not None and DHT_AVAILABLE and platform.system() == "Linux":
                # Real hardware reading
                temperature = self.sensor.temperature
                humidity = self.sensor.humidity
                self.last_read_time = current_time
                return (humidity, temperature)
            else:
                # Simulated reading for development/testing
                import random
                temperature = round(random.uniform(20, 30), 1)
                humidity = round(random.uniform(40, 60), 1)
                self.last_read_time = current_time
                return (humidity, temperature)
        except RuntimeError as e:
            # Common DHT11 error
            print(f"RuntimeError on GPIO{self.pin}: {e}")
            return (None, None)
        except Exception as e:
            print(f"Sensor read error on GPIO{self.pin}: {e}")
            return (None, None)


class DHT22TestGUI:
    """GUI for testing DHT22 sensors"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("DHT22 Sensor Test")
        self.root.geometry("600x400")
        
        # Sensor configurations
        self.sensors = {
            "Sensor 1 (GPIO 27)": 27,
            "Sensor 2 (GPIO 22)": 22,
        }
        
        self.sensor_objects = {}
        self.running = True
        self.labels = {}
        
        # Create GUI
        self.create_widgets()
        
        # Start sensor readings in background thread
        self.reading_thread = threading.Thread(target=self.read_sensors_loop, daemon=True)
        self.reading_thread.start()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        """Create GUI elements"""
        # Title
        title_frame = ttk.Frame(self.root)
        title_frame.pack(fill=tk.X, padx=20, pady=10)
        
        title_label = ttk.Label(
            title_frame, 
            text="DHT22 Temperature & Humidity Monitor",
            font=("Helvetica", 14, "bold")
        )
        title_label.pack()
        
        # Sensors frame
        sensors_frame = ttk.LabelFrame(self.root, text="Sensor Readings", padding=15)
        sensors_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        for sensor_name, pin in self.sensors.items():
            # Create a frame for each sensor
            sensor_frame = ttk.Frame(sensors_frame)
            sensor_frame.pack(fill=tk.X, pady=10)
            
            # Sensor label
            label = ttk.Label(sensor_frame, text=sensor_name, font=("Helvetica", 11, "bold"))
            label.pack(anchor=tk.W)
            
            # Temperature
            temp_frame = ttk.Frame(sensor_frame)
            temp_frame.pack(fill=tk.X, padx=20)
            ttk.Label(temp_frame, text="Temperature:", width=15).pack(side=tk.LEFT)
            temp_value = ttk.Label(temp_frame, text="-- °C", font=("Helvetica", 10), foreground="blue")
            temp_value.pack(side=tk.LEFT, padx=5)
            
            # Humidity
            humidity_frame = ttk.Frame(sensor_frame)
            humidity_frame.pack(fill=tk.X, padx=20)
            ttk.Label(humidity_frame, text="Humidity:", width=15).pack(side=tk.LEFT)
            humidity_value = ttk.Label(humidity_frame, text="-- %", font=("Helvetica", 10), foreground="green")
            humidity_value.pack(side=tk.LEFT, padx=5)
            
            # Status
            status_frame = ttk.Frame(sensor_frame)
            status_frame.pack(fill=tk.X, padx=20)
            status_label = ttk.Label(status_frame, text="Status: Initializing...", font=("Helvetica", 9), foreground="gray")
            status_label.pack(anchor=tk.W)
            
            self.labels[pin] = {
                'temp': temp_value,
                'humidity': humidity_value,
                'status': status_label
            }
            
            # Initialize sensor
            self.sensor_objects[pin] = DHT22Sensor(pin)
        
        # Button frame
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=20, pady=10)
        
        refresh_button = ttk.Button(button_frame, text="Refresh Now", command=self.force_refresh)
        refresh_button.pack(side=tk.LEFT, padx=5)
        
        quit_button = ttk.Button(button_frame, text="Exit", command=self.on_closing)
        quit_button.pack(side=tk.LEFT, padx=5)
        
        # Info frame
        info_frame = ttk.Frame(self.root)
        info_frame.pack(fill=tk.X, padx=20, pady=10)
        
        info_label = ttk.Label(
            info_frame,
            text="Readings update every 2 seconds. Readings are simulated if sensors are not connected.",
            font=("Helvetica", 9),
            foreground="gray"
        )
        info_label.pack()
    
    def read_sensors_loop(self):
        """Background thread to read sensors continuously"""
        last_update = {}
        
        while self.running:
            try:
                for pin, sensor in self.sensor_objects.items():
                    humidity, temp = sensor.read()
                    
                    if temp is not None and humidity is not None:
                        # Update labels
                        self.labels[pin]['temp'].config(
                            text=f"{temp:.1f} °C",
                            foreground="blue"
                        )
                        self.labels[pin]['humidity'].config(
                            text=f"{humidity:.1f} %",
                            foreground="green"
                        )
                        self.labels[pin]['status'].config(
                            text="Status: ✓ OK",
                            foreground="darkgreen"
                        )
                        last_update[pin] = time.time()
                    else:
                        # No update available yet
                        time_since_update = time.time() - last_update.get(pin, time.time())
                        if time_since_update > 10:
                            self.labels[pin]['status'].config(
                                text="Status: ✗ No reading",
                                foreground="red"
                            )
                        else:
                            self.labels[pin]['status'].config(
                                text="Status: ⏳ Waiting...",
                                foreground="orange"
                            )
                
                time.sleep(0.5)
            except Exception as e:
                print(f"Error in sensor loop: {e}")
                time.sleep(1)
    
    def force_refresh(self):
        """Force immediate sensor read"""
        for pin, sensor in self.sensor_objects.items():
            sensor.last_read_time = 0  # Reset to allow immediate read
    
    def on_closing(self):
        """Handle window closing"""
        self.running = False
        self.root.destroy()


def main():
    """Main function"""
    print("=" * 60)
    print("DHT22 Sensor Test")
    print("=" * 60)
    print()
    print("Sensors configured:")
    print("  - Sensor 1: GPIO 27")
    print("  - Sensor 2: GPIO 22")
    print()
    print("Starting GUI...")
    print()
    
    root = tk.Tk()
    gui = DHT22TestGUI(root)
    root.mainloop()
    
    print("Test completed.")


if __name__ == "__main__":
    main()
