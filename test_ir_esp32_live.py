#!/usr/bin/env python3
"""
Live IR Sensor Test - Read from ESP32 serial and log to sensor_data_logger

This script reads IR sensor states from the ESP32's serial output,
parses them in real-time, and logs them via sensor_data_logger for
graphing and historical trending.
"""

import time
import sys
import re
import threading

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("[ERROR] pyserial not installed. Install with: pip install pyserial")
    sys.exit(1)

from sensor_data_logger import get_sensor_logger


def autodetect_esp32_port():
    """Auto-detect ESP32 serial port from available COM ports."""
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = (p.description or "").lower()
        mfg = (p.manufacturer or "").lower()
        keywords = ["esp32", "arduino", "cp210", "silicon labs", "ch340"]
        if any(kw in desc or kw in mfg for kw in keywords):
            return p.device
    return ports[0].device if ports else None


class ESP32IRMonitor(threading.Thread):
    """Background thread to read and log IR sensor data from ESP32."""
    
    def __init__(self, port, baudrate=115200):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.running = True
        self.logger = get_sensor_logger()
        self.connected = False
        # Regex to parse IR sensor lines
        self.ir1_pattern = re.compile(r"IR1.*?:\s*(BLOCKED|CLEAR)", re.IGNORECASE)
        self.ir2_pattern = re.compile(r"IR2.*?:\s*(BLOCKED|CLEAR)", re.IGNORECASE)
    
    def run(self):
        """Main thread loop - read and log IR data."""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.connected = True
            print(f"✓ Connected to ESP32 on {self.port}")
        except Exception as e:
            print(f"✗ Failed to open serial port {self.port}: {e}")
            self.connected = False
            return
        
        # Tracking for deduplication (avoid logging duplicate states)
        last_ir1 = None
        last_ir2 = None
        read_count = 0
        
        while self.running:
            try:
                if self.ser and self.ser.is_open:
                    line = self.ser.readline().decode(errors="ignore").strip()
                    if not line:
                        continue
                    
                    read_count += 1
                    
                    # Parse IR1
                    m1 = self.ir1_pattern.search(line)
                    if m1:
                        ir1_state = m1.group(1).upper()
                        # Convert to boolean (BLOCKED = True obstacle, CLEAR = False no obstacle)
                        ir1_bool = (ir1_state == "BLOCKED")
                        if ir1_bool != last_ir1:
                            last_ir1 = ir1_bool
                            print(f"[IR1] {ir1_state}")
                    
                    # Parse IR2
                    m2 = self.ir2_pattern.search(line)
                    if m2:
                        ir2_state = m2.group(1).upper()
                        ir2_bool = (ir2_state == "BLOCKED")
                        if ir2_bool != last_ir2:
                            last_ir2 = ir2_bool
                            print(f"[IR2] {ir2_state}")
                    
                    # Log to sensor logger when we have both IR readings
                    if (m1 or m2) and last_ir1 is not None and last_ir2 is not None:
                        self.logger.log_ir_sensor_reading(
                            ir_sensor1_detection=last_ir1,
                            ir_sensor2_detection=last_ir2
                        )
            
            except Exception as e:
                print(f"Serial read error: {e}")
                continue
    
    def stop(self):
        """Stop the monitor thread."""
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()


def main():
    print("=" * 60)
    print("ESP32 IR Sensor Live Monitor and Logger")
    print("=" * 60)
    print()
    
    # Auto-detect ESP32
    port = autodetect_esp32_port()
    if not port:
        print("[ERROR] Could not find ESP32 serial port")
        print("Please check:")
        print("  - ESP32 is connected via USB")
        print("  - USB driver is installed")
        sys.exit(1)
    
    print(f"Detected ESP32 on port: {port}")
    print("Starting live IR sensor monitoring and logging...")
    print()
    
    # Start monitor thread
    monitor = ESP32IRMonitor(port)
    monitor.start()
    
    if not monitor.connected:
        sys.exit(1)
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping monitor...")
        monitor.stop()
        monitor.join(timeout=2)
        print("✓ Monitor stopped")


if __name__ == "__main__":
    main()
