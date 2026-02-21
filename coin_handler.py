try:
    import RPi.GPIO as GPIO
except Exception:
    # Not running on Raspberry Pi / RPi.GPIO unavailable — use a local mock so the UI can run
    import rpi_gpio_mock as GPIO
import time
from threading import Thread, Lock
from queue import Queue

class CoinAcceptor:
    # Allan 123A-Pro coin values matching your calibration
    COIN_VALUES = {
        1: {'value': 1.0, 'description': 'Old 1 Peso Coin'},  # A1
        2: {'value': 1.0, 'description': 'New 1 Peso Coin'},  # A2
        3: {'value': 5.0, 'description': 'Old 5 Peso Coin'},  # A3
        4: {'value': 5.0, 'description': 'New 5 Peso Coin'},  # A4
        5: {'value': 10.0, 'description': 'Old 10 Peso Coin'}, # A5
        6: {'value': 10.0, 'description': 'New 10 Peso Coin'}  # A6
    }

    def __init__(self, coin_pin=17, counter_pin=None):  # GPIO17 for coin input
        self.coin_pin = coin_pin
        self.counter_pin = counter_pin
        self.last_trigger_time = 0
        self.debounce_time = 0.05  # 50ms debounce for Allan 123A-Pro
        # Pulse validation: ignore very short noise pulses and overly long signals
        self.min_pulse_width = 0.005   # 5 ms
        self.max_pulse_width = 0.5     # 500 ms
        self.validation_timeout_ms = int(self.max_pulse_width * 1000)
        self.running = False
        self.payment_lock = Lock()
        self.received_amount = 0.0
        self.current_coin_value = 1.0  # Default coin value, adjust after programming
        self._callback = None  # Callback for coin updates
        
        print(f"DEBUG: CoinAcceptor initializing on GPIO {coin_pin}")
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.coin_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        if self.counter_pin:
            GPIO.setup(self.counter_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Add event detection for the coin signal (we'll validate pulse width)
        GPIO.add_event_detect(self.coin_pin, GPIO.FALLING, callback=self._coin_detected)
        print(f"DEBUG: CoinAcceptor event detection added for GPIO {coin_pin}")

    def set_callback(self, callback):
        """Register a callback to be invoked when coins are received.
        
        Args:
            callback: Function that takes the total received amount as parameter
        """
        with self.payment_lock:
            self._callback = callback
        print(f"DEBUG: CoinAcceptor callback set")

    def _coin_detected(self, channel):
        """Initial FALLING interrupt handler: spawn a validator thread to measure pulse width
        and reject short noise pulses. The actual registration of the coin happens in
        `_validate_and_register` so this callback remains fast and non-blocking."""
        current_time = time.time()
        if (current_time - self.last_trigger_time) < self.debounce_time:
            return

        t = Thread(target=self._validate_and_register, args=(channel,))
        t.daemon = True
        t.start()

    def _validate_and_register(self, channel):
        """Validate the pulse width for the coin signal. Waits for the RISING edge (end
        of pulse) up to `validation_timeout_ms`. If pulse width is within expected
        bounds, register the coin; otherwise ignore as noise."""
        start = time.time()

        # Prefer hardware wait_for_edge when available (blocks briefly in this thread)
        try:
            edge = GPIO.wait_for_edge(self.coin_pin, GPIO.RISING, timeout=self.validation_timeout_ms)
            if edge is None:
                # timed out waiting for rising edge -> ignore
                return
        except Exception:
            # fallback: poll the pin until it goes HIGH or timeout
            timeout = start + self.max_pulse_width
            while time.time() < timeout:
                try:
                    if GPIO.input(self.coin_pin) == GPIO.HIGH:
                        break
                except Exception:
                    break
                time.sleep(0.002)
            else:
                return

        width = time.time() - start
        if width < self.min_pulse_width or width > self.max_pulse_width:
            # pulse too short (likely noise) or too long (stuck/invalid)
            return

        # Determine coin value based on pulse width (Allan 123A-Pro calibration)
        # INVERTED: 1peso=60ms, 5peso=40ms, 10peso=20ms (reversed from typical)
        coin_value = 1.0  # default
        if width >= 0.045:  # 45ms+ = 1 peso (longest pulse)
            coin_value = 1.0   # 1 peso coin
        elif width >= 0.030:  # 30-45ms = 5 peso (medium pulse)
            coin_value = 5.0   # 5 peso coin
        else:  # < 30ms = 10 peso (shortest pulse)
            coin_value = 10.0  # 10 peso coin

        # Final debounce and registration under lock
        with self.payment_lock:
            now = time.time()
            if (now - self.last_trigger_time) < self.debounce_time:
                return
            self.last_trigger_time = now
            self.received_amount += coin_value
            amount = self.received_amount
            callback = self._callback

        print(f"DEBUG: Coin validated on GPIO {channel}, width={width:.3f}s, value={coin_value}, total={amount}")
        if callback:
            try:
                callback(amount)
            except Exception as e:
                print(f"DEBUG: Coin callback error: {e}")

    def get_received_amount(self):
        """Get the total amount received"""
        with self.payment_lock:
            return self.received_amount

    def reset_amount(self):
        """Reset the received amount to zero"""
        with self.payment_lock:
            self.received_amount = 0.0
        print(f"DEBUG: CoinAcceptor amount reset to 0.0")

    def cleanup(self):
        """Clean up GPIO settings"""
        try:
            GPIO.remove_event_detect(self.coin_pin)
            print(f"DEBUG: CoinAcceptor GPIO {self.coin_pin} event detection removed")
        except Exception as e:
            print(f"DEBUG: Error cleaning up CoinAcceptor: {e}")