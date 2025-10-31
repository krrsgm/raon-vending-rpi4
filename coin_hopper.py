import time
try:
    import RPi.GPIO as GPIO
except ImportError:
    from rpi_gpio_mock import GPIO

class CoinHopper:
    """Controls coin hoppers for dispensing change.
    
    Supports two hoppers:
    - 1 peso coin hopper
    - 5 peso coin hopper
    
    Uses GPIO pins to control motor activation for each hopper.
    Includes coin counting via feedback sensor.
    """
    
    def __init__(self, one_peso_pin, five_peso_pin, one_peso_sensor, five_peso_sensor):
        """Initialize coin hoppers.
        
        Args:
            one_peso_pin: GPIO pin number for 1 peso hopper motor
            five_peso_pin: GPIO pin number for 5 peso hopper motor
            one_peso_sensor: GPIO pin number for 1 peso coin counter feedback
            five_peso_sensor: GPIO pin number for 5 peso coin counter feedback
        """
        # Setup GPIO
        self.one_peso_pin = one_peso_pin
        self.five_peso_pin = five_peso_pin
        self.one_peso_sensor = one_peso_sensor
        self.five_peso_sensor = five_peso_sensor
        
        # Configure GPIO pins
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(one_peso_pin, GPIO.OUT)
        GPIO.setup(five_peso_pin, GPIO.OUT)
        GPIO.setup(one_peso_sensor, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(five_peso_sensor, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Initialize motors to stopped state
        GPIO.output(one_peso_pin, GPIO.LOW)
        GPIO.output(five_peso_pin, GPIO.LOW)
        
        # Setup coin counting
        self.one_peso_count = 0
        self.five_peso_count = 0
        self.last_one_peso_state = GPIO.input(one_peso_sensor)
        self.last_five_peso_state = GPIO.input(five_peso_sensor)
        
        # Add sensor event detection
        GPIO.add_event_detect(one_peso_sensor, GPIO.BOTH, callback=self._one_peso_callback)
        GPIO.add_event_detect(five_peso_sensor, GPIO.BOTH, callback=self._five_peso_callback)

    def _one_peso_callback(self, channel):
        """Count 1 peso coins via sensor feedback."""
        current_state = GPIO.input(channel)
        if current_state != self.last_one_peso_state:
            if current_state == GPIO.HIGH:  # Coin detected
                self.one_peso_count += 1
            self.last_one_peso_state = current_state

    def _five_peso_callback(self, channel):
        """Count 5 peso coins via sensor feedback."""
        current_state = GPIO.input(channel)
        if current_state != self.last_five_peso_state:
            if current_state == GPIO.HIGH:  # Coin detected
                self.five_peso_count += 1
            self.last_five_peso_state = current_state

    def calculate_change(self, amount):
        """Calculate optimal coin combination for change.
        
        Args:
            amount: Amount of change needed in pesos
            
        Returns:
            Tuple of (num_five_peso, num_one_peso) coins needed
        """
        # Use as many 5 peso coins as possible, then ones for remainder
        num_five = amount // 5
        remainder = amount % 5
        num_one = remainder
        
        return (num_five, num_one)

    def dispense_change(self, amount, callback=None):
        """Dispense specified amount of change using minimum coins.
        
        Args:
            amount: Amount to dispense in pesos
            callback: Optional function to call with status updates
            
        Returns:
            Tuple of (success, dispensed_amount, error_message)
        """
        if amount <= 0:
            return (True, 0, "No change needed")
            
        # Calculate coins needed
        five_needed, one_needed = self.calculate_change(amount)
        
        try:
            # Reset counters
            self.five_peso_count = 0
            self.one_peso_count = 0
            
            # Dispense 5 peso coins
            if five_needed > 0:
                if callback:
                    callback(f"Dispensing {five_needed} five peso coins...")
                GPIO.output(self.five_peso_pin, GPIO.HIGH)
                
                # Wait for correct number of coins
                timeout = time.time() + 30  # 30 second timeout
                while self.five_peso_count < five_needed:
                    if time.time() > timeout:
                        GPIO.output(self.five_peso_pin, GPIO.LOW)
                        return (False, 
                               (self.five_peso_count * 5) + self.one_peso_count,
                               "Timeout dispensing 5 peso coins")
                    time.sleep(0.1)
                    
                GPIO.output(self.five_peso_pin, GPIO.LOW)

            # Dispense 1 peso coins
            if one_needed > 0:
                if callback:
                    callback(f"Dispensing {one_needed} one peso coins...")
                GPIO.output(self.one_peso_pin, GPIO.HIGH)
                
                # Wait for correct number of coins
                timeout = time.time() + 30  # 30 second timeout
                while self.one_peso_count < one_needed:
                    if time.time() > timeout:
                        GPIO.output(self.one_peso_pin, GPIO.LOW)
                        return (False,
                               (self.five_peso_count * 5) + self.one_peso_count,
                               "Timeout dispensing 1 peso coins")
                    time.sleep(0.1)
                    
                GPIO.output(self.one_peso_pin, GPIO.LOW)
            
            total_dispensed = (self.five_peso_count * 5) + self.one_peso_count
            return (True, total_dispensed, "Change dispensed successfully")
            
        except Exception as e:
            # Ensure motors are stopped
            GPIO.output(self.five_peso_pin, GPIO.LOW)
            GPIO.output(self.one_peso_pin, GPIO.LOW)
            return (False,
                   (self.five_peso_count * 5) + self.one_peso_count,
                   f"Error dispensing change: {str(e)}")

    def cleanup(self):
        """Clean up GPIO resources."""
        try:
            GPIO.output(self.one_peso_pin, GPIO.LOW)
            GPIO.output(self.five_peso_pin, GPIO.LOW)
            GPIO.remove_event_detect(self.one_peso_sensor)
            GPIO.remove_event_detect(self.five_peso_sensor)
        except:
            pass  # Ignore cleanup errors