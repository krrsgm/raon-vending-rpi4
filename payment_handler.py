from threading import Lock
from coin_handler import CoinAcceptor
from coin_hopper import CoinHopper

class PaymentHandler:
    """Payment handler that manages the Allan 123A-Pro coin acceptor and coin hoppers."""
    def __init__(self, config, coin_pin=17, counter_pin=None):
        """Initialize the payment handler with coin acceptor and hoppers.
        
        Args:
            config (dict): Configuration containing coin hopper pin settings
            coin_pin (int): GPIO pin number (BCM) for the coin signal
            counter_pin (int, optional): GPIO pin for the counter signal if used
        """
        # Setup coin acceptor
        self.coin_acceptor = CoinAcceptor(coin_pin=coin_pin, counter_pin=counter_pin)
        
        # Setup coin hoppers if configured
        self.coin_hopper = None
        try:
            hopper_config = config.get('coin_hoppers', {})
            if hopper_config:
                one_peso = hopper_config.get('one_peso', {})
                five_peso = hopper_config.get('five_peso', {})
                
                self.coin_hopper = CoinHopper(
                    one_peso_pin=one_peso.get('motor_pin'),
                    five_peso_pin=five_peso.get('motor_pin'),
                    one_peso_sensor=one_peso.get('sensor_pin'),
                    five_peso_sensor=five_peso.get('sensor_pin')
                )
        except Exception as e:
            print(f"Error initializing coin hoppers: {e}")
            self.coin_hopper = None
            
        self._lock = Lock()
        self._callback = None  # Optional callback for UI updates
        self._change_callback = None  # Optional callback for change status

    def start_payment_session(self, required_amount=None, on_payment_update=None):
        """Start a new payment session.
        
        Args:
            required_amount (float, optional): Target amount to collect
            on_payment_update (callable, optional): Callback(amount) when coins received
        """
        self._callback = on_payment_update
        self.coin_acceptor.reset_amount()
        return True

    def get_current_amount(self):
        """Get the total amount received in the current session."""
        with self._lock:
            return self.coin_acceptor.get_received_amount()

    def stop_payment_session(self, required_amount=None):
        """Stop the current payment session and handle change if needed.
        
        Args:
            required_amount (float, optional): If provided, calculate and dispense change
            
        Returns:
            Tuple of (total_received, change_amount, change_status)
        """
        total_received = self.coin_acceptor.get_received_amount()
        change_amount = 0
        change_status = ""
        
        # Calculate change if needed
        if required_amount is not None and total_received > required_amount:
            change_needed = total_received - required_amount
            if self.coin_hopper:
                success, dispensed, message = self.coin_hopper.dispense_change(
                    change_needed,
                    callback=self._change_callback
                )
                if success:
                    change_amount = dispensed
                    change_status = f"Change dispensed: ₱{dispensed}"
                else:
                    change_status = f"Error: {message}"
            else:
                change_status = "Change dispenser not available"
        
        self.coin_acceptor.reset_amount()
        self._callback = None
        self._change_callback = None
        return total_received, change_amount, change_status

    def cleanup(self):
        """Clean up GPIO resources."""
        try:
            self.coin_acceptor.cleanup()
        except Exception:
            pass
            
        if self.coin_hopper:
            try:
                self.coin_hopper.cleanup()
            except Exception:
                pass
