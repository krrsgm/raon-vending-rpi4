"""
mux4_controller.py
Controls MUX4 SIG pin on Raspberry Pi for slots 49-64.

The ESP32 controls the multiplexer selector pins (S0-S3) for MUX4,
but the SIG (signal/output) pin is controlled directly by the Raspberry Pi.

This allows the RPi to read/write the output state for MUX4 slots independently.
"""

import time
import platform
import threading

# Try to import GPIO library
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    print("[MUX4] WARNING: RPi.GPIO not available - using mock mode")

# Mock GPIO for testing on non-Pi systems
class MockGPIO:
    BCM = 'BCM'
    OUT = 'OUT'
    IN = 'IN'
    HIGH = 1
    LOW = 0
    
    @staticmethod
    def setmode(mode):
        pass
    
    @staticmethod
    def setup(pin, mode, initial=None):
        print(f"[MockGPIO] setup(pin={pin}, mode={mode})")
    
    @staticmethod
    def output(pin, state):
        print(f"[MockGPIO] output(pin={pin}, state={'HIGH' if state else 'LOW'})")
    
    @staticmethod
    def input(pin):
        print(f"[MockGPIO] input(pin={pin}) -> returning LOW")
        return MockGPIO.LOW
    
    @staticmethod
    def cleanup(pin=None):
        pass


class MUX4Controller:
    """Controls MUX4 SIG output pin on Raspberry Pi."""
    
    def __init__(self, sig_pin=23):
        """
        Initialize MUX4 SIG controller.
        
        Args:
            sig_pin: GPIO pin number (BCM) for MUX4 SIG signal
                    Default: GPIO23 (available on Raspberry Pi 4)
        """
        self.sig_pin = sig_pin
        self.is_initialized = False
        self._lock = threading.Lock()
        self._pulse_thread = None
        self._stop_pulse = False
        
        # Determine if we're on Raspberry Pi
        try:
            with open('/proc/device-tree/model', 'r') as f:
                self.is_raspberry_pi = 'Raspberry Pi' in f.read()
        except (FileNotFoundError, IOError):
            self.is_raspberry_pi = False
        
        # Select GPIO library
        if GPIO_AVAILABLE and self.is_raspberry_pi:
            self.gpio = GPIO
            self._init_hardware()
        else:
            self.gpio = MockGPIO
            print("[MUX4] Using mock GPIO (not on Raspberry Pi or GPIO not available)")
        
    def _init_hardware(self):
        """Initialize GPIO hardware."""
        try:
            if self.is_raspberry_pi and GPIO_AVAILABLE:
                # Check if GPIO is already initialized
                try:
                    self.gpio.setmode(self.gpio.BCM)
                except RuntimeError as e:
                    if "already been set" in str(e):
                        print(f"[MUX4] GPIO mode already set, continuing...")
                    else:
                        raise
                
                self.gpio.setup(self.sig_pin, self.gpio.OUT, initial=self.gpio.LOW)
                self.is_initialized = True
                print(f"[MUX4] SIG pin initialized on GPIO{self.sig_pin}")
        except Exception as e:
            print(f"[MUX4] ERROR initializing hardware: {e}")
            print(f"[MUX4] Falling back to mock mode")
            self.gpio = MockGPIO
    
    def set_output(self, state):
        """
        Set MUX4 SIG output HIGH or LOW.
        
        Args:
            state: True for HIGH, False for LOW
        """
        with self._lock:
            try:
                self.gpio.output(self.sig_pin, self.gpio.HIGH if state else self.gpio.LOW)
                status = "HIGH" if state else "LOW"
                print(f"[MUX4] SIG set to {status}")
            except Exception as e:
                print(f"[MUX4] ERROR setting output: {e}")
    
    def pulse(self, duration_ms):
        """
        Pulse the MUX4 SIG output for a specified duration.
        
        Args:
            duration_ms: Pulse duration in milliseconds
        """
        with self._lock:
            try:
                self.gpio.output(self.sig_pin, self.gpio.HIGH)
                print(f"[MUX4] Pulse START ({duration_ms}ms)")
                time.sleep(duration_ms / 1000.0)
                self.gpio.output(self.sig_pin, self.gpio.LOW)
                print(f"[MUX4] Pulse END")
            except Exception as e:
                print(f"[MUX4] ERROR during pulse: {e}")
    
    def pulse_async(self, duration_ms):
        """
        Pulse the MUX4 SIG output asynchronously (non-blocking).
        
        Args:
            duration_ms: Pulse duration in milliseconds
        """
        # Cancel any existing pulse
        if self._pulse_thread and self._pulse_thread.is_alive():
            self._stop_pulse = True
            self._pulse_thread.join(timeout=2.0)
        
        # Start new pulse thread
        self._stop_pulse = False
        self._pulse_thread = threading.Thread(
            target=self.pulse,
            args=(duration_ms,),
            daemon=True
        )
        self._pulse_thread.start()
    
    def read_input(self):
        """
        Read the MUX4 SIG pin as an input (for feedback verification).
        Note: This temporarily switches pin mode to INPUT.
        
        Returns:
            True if pin is HIGH, False if LOW
        """
        with self._lock:
            try:
                # Temporarily switch to input mode
                self.gpio.setup(self.sig_pin, self.gpio.IN)
                state = self.gpio.input(self.sig_pin)
                # Switch back to output mode
                self.gpio.setup(self.sig_pin, self.gpio.OUT, initial=self.gpio.LOW)
                return bool(state)
            except Exception as e:
                print(f"[MUX4] ERROR reading input: {e}")
                return False
    
    def cleanup(self):
        """Clean up GPIO resources."""
        try:
            if self._pulse_thread and self._pulse_thread.is_alive():
                self._stop_pulse = True
                self._pulse_thread.join(timeout=1.0)
            
            if self.gpio != MockGPIO and GPIO_AVAILABLE:
                self.gpio.cleanup(self.sig_pin)
                print(f"[MUX4] Cleaned up GPIO{self.sig_pin}")
        except Exception as e:
            print(f"[MUX4] ERROR during cleanup: {e}")
    
    def __del__(self):
        """Cleanup on object destruction."""
        self.cleanup()
