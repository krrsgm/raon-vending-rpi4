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
        self.running = False
        self.payment_lock = Lock()
        self.received_amount = 0.0
        self.current_coin_value = 1.0  # Default coin value, adjust after programming
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.coin_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        if self.counter_pin:
            GPIO.setup(self.counter_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Add event detection for the coin signal
        GPIO.add_event_detect(self.coin_pin, GPIO.FALLING, 
                            callback=self._coin_detected, 
                            bouncetime=50)

    def _coin_detected(self, channel):
        """Called when a coin is detected by the Allan 123A-Pro"""
        current_time = time.time()
        
        # Debounce check
        if (current_time - self.last_trigger_time) < self.debounce_time:
            return
            
        self.last_trigger_time = current_time
        
        with self.payment_lock:
            # Add the current coin value when a coin is detected
            self.received_amount += self.current_coin_value

    def get_received_amount(self):
        """Get the total amount received"""
        with self.payment_lock:
            return self.received_amount

    def reset_amount(self):
        """Reset the received amount to zero"""
        with self.payment_lock:
            self.received_amount = 0.0

    def cleanup(self):
        """Clean up GPIO settings"""
        GPIO.remove_event_detect(self.coin_pin)