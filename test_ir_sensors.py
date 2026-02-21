#!/usr/bin/env python3
"""
Simple IR Sensor Test - Read HIGH/LOW signal states
Tests GPIO 24 (Sensor 1) and GPIO 25 (Sensor 2)
"""

import time
import sys

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    print("[WARNING] RPi.GPIO not available - using mock mode")
    # Import mock GPIO if available
    try:
        from rpi_gpio_mock import GPIO as GPIO
    except ImportError:
        print("[ERROR] Could not import mock GPIO either")
        sys.exit(1)

# IR Sensor pins
SENSOR_1_PIN = 24
SENSOR_2_PIN = 25

def setup_sensors():
    """Initialize GPIO pins for IR sensors."""
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(SENSOR_1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(SENSOR_2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        print(f"✓ GPIO initialized (GPIO_AVAILABLE={GPIO_AVAILABLE})")
        print(f"✓ Sensor 1 (GPIO {SENSOR_1_PIN}): INPUT with PULL_UP")
        print(f"✓ Sensor 2 (GPIO {SENSOR_2_PIN}): INPUT with PULL_UP")
    except Exception as e:
        print(f"[ERROR] Failed to initialize GPIO: {e}")
        sys.exit(1)

def read_sensors(duration=10, interval=0.5):
    """Read and display IR sensor states."""
    print(f"\nReading IR sensors for {duration} seconds...\n")
    print(f"{'Time (s)':>8} | {'Sensor 1 (GPIO24)':>18} | {'Sensor 2 (GPIO25)':>18}")
    print("-" * 50)
    
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            
            # Read sensor states
            sensor_1_state = GPIO.input(SENSOR_1_PIN)
            sensor_2_state = GPIO.input(SENSOR_2_PIN)
            
            # Convert to readable format
            state_1 = "HIGH (no object)" if sensor_1_state else "LOW (object detected)"
            state_2 = "HIGH (no object)" if sensor_2_state else "LOW (object detected)"
            
            print(f"{elapsed:>8.1f} | {state_1:>18} | {state_2:>18}")
            
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\n[INFO] Test interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Error reading sensors: {e}")
    finally:
        cleanup()

def cleanup():
    """Clean up GPIO."""
    try:
        GPIO.cleanup()
        print("\n✓ GPIO cleaned up")
    except Exception as e:
        print(f"\n[WARNING] Error during cleanup: {e}")

def main():
    print("=" * 50)
    print("IR Sensor Test - Signal State Monitor")
    print("=" * 50)
    
    setup_sensors()
    read_sensors(duration=30, interval=0.5)

if __name__ == "__main__":
    main()
