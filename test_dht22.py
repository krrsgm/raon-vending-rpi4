#!/usr/bin/env python3
"""
ESP32 DHT22 Sensor Test Script
Reads temperature and humidity from DHT22 sensors connected to ESP32
via serial communication. Displays readings in real-time GUI.
"""

import tkinter as tk
from tkinter import ttk
import time
import threading
import re
import sys

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("Warning: pyserial not installed. Install with: pip install pyserial")


def autodetect_esp32_port():
    """Auto-detect ESP32 serial port from available COM ports."""
    if not SERIAL_AVAILABLE:
        return None
    
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description or ""
        mfg = p.manufacturer or ""
        # Look for common ESP32/Arduino identifiers
        keywords = ["USB", "UART", "CP210", "Silicon Labs", "CH340", "ESP32", "Arduino"]
        if any(kw in desc or kw in mfg for kw in keywords):
            return p.device
    
    # Fallback: first available port
    if ports:
        return ports[0].device
    return None


class ESP32DHT22Reader(threading.Thread):
    """Background thread to read DHT22 values from ESP32 serial port."""
    
    def __init__(self, port, baudrate=115200):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.running = True
        self.lock = threading.Lock()
        self.latest = {1: (None, None), 2: (None, None)}  # {sensor: (temp, humidity)}
        self.connected = False
    
    def run(self):
        """Main thread loop."""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"✓ Connected to ESP32 on {self.port}")
            self.connected = True
        except Exception as e:
            print(f"✗ Failed to open serial port {self.port}: {e}")
            self.connected = False
            return
        
        # Regex patterns to parse ESP32 output
        dht1_pattern = re.compile(r"DHT1.*?:\s*([\d.\-]+)C\s+([\d.\-]+)%")
        dht2_pattern = re.compile(r"DHT2.*?:\s*([\d.\-]+)C\s+([\d.\-]+)%")
        
        while self.running:
            try:
                if self.ser and self.ser.is_open:
                    line = self.ser.readline().decode(errors="ignore").strip()
                    if not line:
                        continue
                    
                    # Parse DHT1 (GPIO35)
                    m1 = dht1_pattern.search(line)
                    if m1:
                        try:
                            temp = float(m1.group(1))
                            humidity = float(m1.group(2))
                            with self.lock:
                                self.latest[1] = (temp, humidity)
                        except (ValueError, IndexError):
                            pass
                    
                    # Parse DHT2 (GPIO36)
                    m2 = dht2_pattern.search(line)
                    if m2:
                        try:
                            temp = float(m2.group(1))
                            humidity = float(m2.group(2))
                            with self.lock:
                                self.latest[2] = (temp, humidity)
                        except (ValueError, IndexError):
                            pass
            except Exception as e:
                print(f"Serial read error: {e}")
                continue
    
    def get_latest(self, sensor):
        """Get latest reading for a sensor (1 or 2)."""
        with self.lock:
            return self.latest.get(sensor, (None, None))
    
    def stop(self):
        """Stop the reader thread."""
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()


class DHT22App(tk.Tk):
    """GUI application to display DHT22 sensor readings from ESP32."""
    
    def __init__(self, port):
        super().__init__()
        self.title("ESP32 DHT22 Sensor Test")
        self.geometry("500x250")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Title
        title_label = ttk.Label(self, text="ESP32 DHT22 Sensor Monitor", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=15)
        
        # Sensor 1 Frame
        sensor1_frame = ttk.LabelFrame(self, text="DHT1 (GPIO35)", padding=10)
        sensor1_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.dht1_temp_label = ttk.Label(sensor1_frame, text="Temperature: -- °C", font=("Helvetica", 12))
        self.dht1_temp_label.pack(anchor=tk.W)
        self.dht1_hum_label = ttk.Label(sensor1_frame, text="Humidity: -- %", font=("Helvetica", 12))
        self.dht1_hum_label.pack(anchor=tk.W)
        
        # Sensor 2 Frame
        sensor2_frame = ttk.LabelFrame(self, text="DHT2 (GPIO36)", padding=10)
        sensor2_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.dht2_temp_label = ttk.Label(sensor2_frame, text="Temperature: -- °C", font=("Helvetica", 12))
        self.dht2_temp_label.pack(anchor=tk.W)
        self.dht2_hum_label = ttk.Label(sensor2_frame, text="Humidity: -- %", font=("Helvetica", 12))
        self.dht2_hum_label.pack(anchor=tk.W)
        
        # Status frame
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=20, pady=10)
        
        status_text = f"Connected to: {port}"
        self.status_label = ttk.Label(status_frame, text=status_text, font=("Helvetica", 10), foreground="green")
        self.status_label.pack(anchor=tk.W)
        
        # Start reader thread
        self.reader = ESP32DHT22Reader(port)
        self.reader.start()
        
        if not self.reader.connected:
            self.status_label.config(text="Failed to connect to ESP32", foreground="red")
        
        # Update readings periodically
        self.update_readings()
    
    def update_readings(self):
        """Update sensor readings from ESP32."""
        # DHT1
        t1, h1 = self.reader.get_latest(1)
        if t1 is not None and h1 is not None:
            self.dht1_temp_label.config(text=f"Temperature: {t1:.1f} °C", foreground="black")
            self.dht1_hum_label.config(text=f"Humidity: {h1:.1f} %", foreground="black")
        else:
            self.dht1_temp_label.config(text="Temperature: -- °C", foreground="gray")
            self.dht1_hum_label.config(text="Humidity: -- %", foreground="gray")
        
        # DHT2
        t2, h2 = self.reader.get_latest(2)
        if t2 is not None and h2 is not None:
            self.dht2_temp_label.config(text=f"Temperature: {t2:.1f} °C", foreground="black")
            self.dht2_hum_label.config(text=f"Humidity: {h2:.1f} %", foreground="black")
        else:
            self.dht2_temp_label.config(text="Temperature: -- °C", foreground="gray")
            self.dht2_hum_label.config(text="Humidity: -- %", foreground="gray")
        
        self.after(1000, self.update_readings)
    
    def on_close(self):
        """Clean up and close."""
        self.reader.stop()
        self.destroy()


def main():
    """Main function."""
    print("=" * 60)
    print("ESP32 DHT22 Sensor Test")
    print("=" * 60)
    print()
    
    if not SERIAL_AVAILABLE:
        print("Error: pyserial is not installed.")
        print("Install with: pip install pyserial")
        sys.exit(1)
    
    port = autodetect_esp32_port()
    if not port:
        print("Error: Could not find ESP32 serial port.")
        print("Please check:")
        print("  - ESP32 is connected via USB")
        print("  - USB driver is installed")
        print("  - Port is not in use by another application")
        sys.exit(1)
    
    print(f"Detected ESP32 on port: {port}")
    print("Starting GUI...")
    print()
    
    app = DHT22App(port)
    app.mainloop()
    
    print("Test completed.")


if __name__ == "__main__":
    main()
