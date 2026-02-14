"""
mux4_controller.py
Controls MUX4 selector pins (S0-S3) and SIG pin on Raspberry Pi for slots 49-64.

The ESP32 in this design controls the first three multiplexers (slots 1-48).
MUX4 (slots 49-64) is handled entirely by the Raspberry Pi: the RPi drives
the selector pins S0..S3 and the SIG (output) pin to pulse/discharge the
selected channel. This module provides a small, well-tested controller with
clear fallbacks for non-RPi environments.
"""
import time
import platform
import threading

# Try to import RPi.GPIO; fall back to a tiny mock for development/testing
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False


class _MockGPIO:
    """Minimal mock of the RPi.GPIO interface used by this module."""
    BCM = 'BCM'
    OUT = 'OUT'
    IN = 'IN'
    HIGH = 1
    LOW = 0

    @staticmethod
    def setmode(mode):
        print(f"[MockGPIO] setmode({mode})")

    @staticmethod
    def setup(pin, mode, pull_up_down=None, initial=None):
        print(f"[MockGPIO] setup(pin={pin}, mode={mode}, initial={initial})")

    @staticmethod
    def output(pin, state):
        s = 'HIGH' if state else 'LOW'
        print(f"[MockGPIO] output(pin={pin}, state={s})")

    @staticmethod
    def input(pin):
        print(f"[MockGPIO] input(pin={pin}) -> LOW")
        return _MockGPIO.LOW

    @staticmethod
    def cleanup(pin=None):
        print(f"[MockGPIO] cleanup(pin={pin})")


GPIO_IMPL = GPIO if GPIO_AVAILABLE else _MockGPIO


class MUX4Controller:
    """Small, thread-safe controller for CD74HC4067-based MUX4.

    Defaults match existing wiring: S0=16, S1=5, S2=18, S3=19, SIG=23 (BCM).
    """

    def __init__(self, s0_pin=16, s1_pin=5, s2_pin=18, s3_pin=19, sig_pin=23):
        self.s0_pin = int(s0_pin)
        self.s1_pin = int(s1_pin)
        self.s2_pin = int(s2_pin)
        self.s3_pin = int(s3_pin)
        self.sig_pin = int(sig_pin)

        self._lock = threading.RLock()
        self._pulse_thread = None
        self._initialized = False

        # detect platform
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                self._is_rpi = 'Raspberry Pi' in model
        except Exception:
            self._is_rpi = False

        self.gpio = GPIO_IMPL
        self._init_hardware()

    def _init_hardware(self):
        """Configure GPIO pins (safe for mock and real RPi)."""
        try:
            # Use BCM mode where available
            try:
                self.gpio.setmode(self.gpio.BCM)
            except Exception:
                # some mocks may not support setmode
                pass

            # Setup selector pins and SIG as outputs, default LOW
            for p in (self.s0_pin, self.s1_pin, self.s2_pin, self.s3_pin, self.sig_pin):
                try:
                    # RPi.GPIO supports initial= param; ignore if not supported
                    self.gpio.setup(p, self.gpio.OUT, initial=self.gpio.LOW)
                except TypeError:
                    # older mock/setup signature
                    self.gpio.setup(p, self.gpio.OUT)
                    self.gpio.output(p, self.gpio.LOW)

            self._initialized = True
            print(f"[MUX4] Initialized S0={self.s0_pin},S1={self.s1_pin},S2={self.s2_pin},S3={self.s3_pin},SIG={self.sig_pin}")
        except Exception as e:
            print(f"[MUX4] ERROR initializing hardware: {e}")
            self._initialized = False

    def select_channel(self, channel):
        """Select a MUX channel 0..15 (LSB -> S0)."""
        if channel < 0 or channel > 15:
            raise ValueError('channel must be 0..15')
        bits = [(channel >> i) & 1 for i in range(4)]
        with self._lock:
            try:
                self.gpio.output(self.s0_pin, self.gpio.HIGH if bits[0] else self.gpio.LOW)
                self.gpio.output(self.s1_pin, self.gpio.HIGH if bits[1] else self.gpio.LOW)
                self.gpio.output(self.s2_pin, self.gpio.HIGH if bits[2] else self.gpio.LOW)
                self.gpio.output(self.s3_pin, self.gpio.HIGH if bits[3] else self.gpio.LOW)
            except Exception as e:
                print(f"[MUX4] ERROR selecting channel {channel}: {e}")

    def set_sig(self, on: bool):
        """Set SIG pin HIGH/LOW."""
        with self._lock:
            try:
                self.gpio.output(self.sig_pin, self.gpio.HIGH if on else self.gpio.LOW)
            except Exception as e:
                print(f"[MUX4] ERROR setting SIG={on}: {e}")

    def pulse(self, duration_ms: int):
        """Blocking pulse of SIG (milliseconds)."""
        if not self._initialized:
            print("[MUX4] WARNING: Not initialized; pulse ignored")
            return
        with self._lock:
            try:
                self.gpio.output(self.sig_pin, self.gpio.HIGH)
                time.sleep(duration_ms / 1000.0)
                self.gpio.output(self.sig_pin, self.gpio.LOW)
            except Exception as e:
                print(f"[MUX4] ERROR during pulse: {e}")

    def pulse_async(self, duration_ms: int):
        """Non-blocking pulse of SIG."""
        def worker():
            try:
                self.pulse(duration_ms)
            except Exception as e:
                print(f"[MUX4] async pulse error: {e}")

        # reuse single thread slot to avoid flooding
        if self._pulse_thread and self._pulse_thread.is_alive():
            try:
                self._pulse_thread.join(timeout=0.05)
            except Exception:
                pass
        self._pulse_thread = threading.Thread(target=worker, daemon=True)
        self._pulse_thread.start()

    def pulse_channel(self, slot_number: int, duration_ms: int):
        """Select channel based on slot_number (49-64) and pulse SIG."""
        if slot_number < 49 or slot_number > 64:
            raise ValueError('slot_number must be in 49..64')
        channel = (slot_number - 49) % 16
        with self._lock:
            try:
                self.select_channel(channel)
                # small settling time for selector pins
                time.sleep(0.01)
                self.pulse(duration_ms)
            except Exception as e:
                print(f"[MUX4] ERROR pulsing slot {slot_number}: {e}")

    def pulse_async_channel(self, slot_number: int, duration_ms: int):
        def worker():
            try:
                self.pulse_channel(slot_number, duration_ms)
            except Exception as e:
                print(f"[MUX4] async channel error: {e}")

        if self._pulse_thread and self._pulse_thread.is_alive():
            try:
                self._pulse_thread.join(timeout=0.05)
            except Exception:
                pass
        self._pulse_thread = threading.Thread(target=worker, daemon=True)
        self._pulse_thread.start()

    def read_sig(self) -> bool:
        """Temporarily configure SIG as input and read its state, then restore as output."""
        with self._lock:
            try:
                # Some GPIO libs accept (pin, IN) else ignore
                try:
                    self.gpio.setup(self.sig_pin, self.gpio.IN)
                    state = self.gpio.input(self.sig_pin)
                finally:
                    # restore output
                    try:
                        self.gpio.setup(self.sig_pin, self.gpio.OUT, initial=self.gpio.LOW)
                    except Exception:
                        try:
                            self.gpio.setup(self.sig_pin, self.gpio.OUT)
                            self.gpio.output(self.sig_pin, self.gpio.LOW)
                        except Exception:
                            pass
                return bool(state)
            except Exception as e:
                print(f"[MUX4] ERROR reading SIG: {e}")
                return False

    def cleanup(self):
        """Cleanup GPIO resources for MUX4 (non-destructive to others)."""
        try:
            if self._pulse_thread and self._pulse_thread.is_alive():
                try:
                    self._pulse_thread.join(timeout=0.1)
                except Exception:
                    pass
            # best-effort cleanup per-pin
            for p in (self.sig_pin, self.s0_pin, self.s1_pin, self.s2_pin, self.s3_pin):
                try:
                    self.gpio.cleanup(p)
                except Exception:
                    # some environments don't support per-pin cleanup
                    pass
        except Exception as e:
            print(f"[MUX4] ERROR during cleanup: {e}")

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass
