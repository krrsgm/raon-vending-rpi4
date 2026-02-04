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
    """Controls MUX4 selector pins (S0-S3) and SIG output on Raspberry Pi."""

    def __init__(self, s0_pin=17, s1_pin=5, s2_pin=18, s3_pin=19, sig_pin=23):
        """
        Initialize MUX4 controller.

        Args:
            s0_pin..s3_pin: BCM GPIO pins for multiplexer selectors (S0..S3)
            sig_pin: BCM GPIO pin for SIG output
        """
        self.s0_pin = s0_pin
        self.s1_pin = s1_pin
        self.s2_pin = s2_pin
        self.s3_pin = s3_pin
        self.sig_pin = sig_pin

        self.is_initialized = False
        self._lock = threading.Lock()
        self._pulse_thread = None
        self._stop_pulse = False

        # Determine platform (RPi vs mock)
        try:
            with open('/proc/device-tree/model', 'r') as f:
                self.is_raspberry_pi = 'Raspberry Pi' in f.read()
        except (FileNotFoundError, IOError):
            self.is_raspberry_pi = False

        if GPIO_AVAILABLE and self.is_raspberry_pi:
            self.gpio = GPIO
            self._init_hardware()
        else:
            self.gpio = MockGPIO
            print("[MUX4] Using mock GPIO (not on Raspberry Pi or GPIO not available)")

    def _init_hardware(self):
        try:
            # Use BCM numbering
            try:
                self.gpio.setmode(self.gpio.BCM)
            except RuntimeError:
                pass

            # Setup selector pins as outputs
            self.gpio.setup(self.s0_pin, self.gpio.OUT, initial=self.gpio.LOW)
            self.gpio.setup(self.s1_pin, self.gpio.OUT, initial=self.gpio.LOW)
            self.gpio.setup(self.s2_pin, self.gpio.OUT, initial=self.gpio.LOW)
            self.gpio.setup(self.s3_pin, self.gpio.OUT, initial=self.gpio.LOW)
            # Setup SIG pin as output
            self.gpio.setup(self.sig_pin, self.gpio.OUT, initial=self.gpio.LOW)

            self.is_initialized = True
            print(f"[MUX4] Initialized S0={self.s0_pin},S1={self.s1_pin},S2={self.s2_pin},S3={self.s3_pin},SIG={self.sig_pin}")
        except Exception as e:
            print(f"[MUX4] ERROR initializing hardware: {e}")
            self.gpio = MockGPIO

    def select_channel(self, channel):
        """Select multiplexer `channel` (0-15) by setting S0..S3."""
        if channel < 0 or channel > 15:
            raise ValueError("channel must be 0..15")
        with self._lock:
            # Set bits on S0..S3 (LSB = S0)
            bits = [(channel >> i) & 1 for i in range(4)]
            try:
                self.gpio.output(self.s0_pin, self.gpio.HIGH if bits[0] else self.gpio.LOW)
                self.gpio.output(self.s1_pin, self.gpio.HIGH if bits[1] else self.gpio.LOW)
                self.gpio.output(self.s2_pin, self.gpio.HIGH if bits[2] else self.gpio.LOW)
                self.gpio.output(self.s3_pin, self.gpio.HIGH if bits[3] else self.gpio.LOW)
            except Exception as e:
                print(f"[MUX4] ERROR selecting channel: {e}")

    def set_output(self, state):
        with self._lock:
            try:
                self.gpio.output(self.sig_pin, self.gpio.HIGH if state else self.gpio.LOW)
            except Exception as e:
                print(f"[MUX4] ERROR setting SIG: {e}")

    def pulse(self, duration_ms):
        """Pulse SIG only (assumes selector already set)."""
        with self._lock:
            try:
                self.gpio.output(self.sig_pin, self.gpio.HIGH)
                time.sleep(duration_ms / 1000.0)
                self.gpio.output(self.sig_pin, self.gpio.LOW)
            except Exception as e:
                print(f"[MUX4] ERROR during pulse: {e}")

    def pulse_async(self, duration_ms):
        """Non-blocking pulse of SIG (no channel)."""
        # Reuse the existing thread slot so async pulses don't pile up
        if self._pulse_thread and self._pulse_thread.is_alive():
            try:
                self._pulse_thread.join(timeout=0.1)
            except Exception:
                pass

        def _worker():
            try:
                self.pulse(duration_ms)
            except Exception as e:
                print(f"[MUX4] ERROR in async pulse: {e}")

        self._pulse_thread = threading.Thread(target=_worker, daemon=True)
        self._pulse_thread.start()

    def pulse_channel(self, slot_number, duration_ms):
        """Select channel based on `slot_number` (49-64) and pulse SIG."""
        if slot_number < 49 or slot_number > 64:
            raise ValueError("slot_number must be in 49..64")
        channel = (slot_number - 49) % 16
        with self._lock:
            try:
                self.select_channel(channel)
                # small settle time for selectors
                time.sleep(0.01)
                self.pulse(duration_ms)
            except Exception as e:
                print(f"[MUX4] ERROR pulsing channel for slot {slot_number}: {e}")

    def pulse_async_channel(self, slot_number, duration_ms):
        # Non-blocking pulse for a channel
        if self._pulse_thread and self._pulse_thread.is_alive():
            try:
                self._pulse_thread.join(timeout=0.1)
            except Exception:
                pass
        self._pulse_thread = threading.Thread(target=self.pulse_channel, args=(slot_number, duration_ms), daemon=True)
        self._pulse_thread.start()

    def read_input(self):
        # Temporarily make SIG an input and read state
        with self._lock:
            try:
                self.gpio.setup(self.sig_pin, self.gpio.IN)
                state = self.gpio.input(self.sig_pin)
                self.gpio.setup(self.sig_pin, self.gpio.OUT, initial=self.gpio.LOW)
                return bool(state)
            except Exception as e:
                print(f"[MUX4] ERROR reading SIG: {e}")
                return False

    def cleanup(self):
        try:
            if self._pulse_thread and self._pulse_thread.is_alive():
                self._pulse_thread.join(timeout=0.1)
            if self.gpio != MockGPIO and GPIO_AVAILABLE:
                # cleanup individual pins
                try:
                    self.gpio.cleanup(self.sig_pin)
                except Exception:
                    pass
                for p in (self.s0_pin, self.s1_pin, self.s2_pin, self.s3_pin):
                    try:
                        self.gpio.cleanup(p)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[MUX4] ERROR during cleanup: {e}")

    def __del__(self):
        self.cleanup()
