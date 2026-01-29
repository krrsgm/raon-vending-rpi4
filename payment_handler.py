from threading import Lock
from coin_handler import CoinAcceptor
from coin_hopper import CoinHopper
import logging
import platform
import os

try:
    from bill_acceptor import BillAcceptor
except ImportError:
    BillAcceptor = None

logger = logging.getLogger(__name__)

class PaymentHandler:
    """Payment handler that manages bill and coin acceptance, plus coin hopper dispensing."""
    def __init__(self, config, coin_pin=17, counter_pin=None, bill_port='/dev/ttyUSB1',
                 bill_baud=None, bill_esp32_mode=False, bill_esp32_serial_port=None, bill_esp32_host=None, bill_esp32_port=5000,
                 coin_hopper_port='/dev/ttyUSB1', coin_hopper_baud=115200):
        """Initialize the payment handler with coin acceptor, bill acceptor, and hoppers.

        Args:
            config (dict): Configuration dictionary
            coin_pin (int): GPIO pin number (BCM) for the coin signal (for coin acceptor)
            counter_pin (int, optional): GPIO pin for the counter signal if used
            bill_port (str): Serial port for bill acceptor
                - '/dev/ttyUSB1' if using USB serial adapter
            bill_baud (int, optional): Baud rate for bill acceptor
            bill_esp32_mode (bool): If True, expect bill events forwarded by ESP32
            bill_esp32_serial_port (str): Serial port connected to ESP32
            bill_esp32_host (str): Host for ESP32 TCP proxy
            bill_esp32_port (int): Port for ESP32 TCP proxy
            coin_hopper_port (str): Serial port connected to arduino_bill_forward
            coin_hopper_baud (int): Baud rate for coin hopper (default 115200)
        """
        # Setup coin acceptor (hardware coin sensor on Raspberry Pi)
        self.coin_acceptor = CoinAcceptor(coin_pin=coin_pin, counter_pin=counter_pin)
        
        # Setup bill acceptor if available. On non-Linux hosts (e.g., Windows) we
        # prefer to avoid attempting serial/TCP hardware connections unless the
        # configured port/host explicitly looks like a real device. This keeps
        # the UI usable during development without noisy error messages.
        self.bill_acceptor = None
        run_platform = platform.system()
        skip_hardware = False
        # If running on non-Linux and the bill port doesn't look like COM or serial path, skip
        if run_platform != 'Linux':
            bp = str(bill_port or '')
            looks_like_serial = bp.lower().startswith('com') or bp.startswith('serial:') or ('tty' in bp) or os.path.exists(bp)
            if not looks_like_serial and not bill_esp32_mode and not (bill_esp32_host):
                skip_hardware = True

        if BillAcceptor and not skip_hardware:
            try:
                # Initialize bill acceptor with ESP32 proxy options when requested
                # Choose sensible default baud: proxy/USB devices typically use 115200
                if bill_baud is None:
                    chosen_baud = 115200 if bill_esp32_mode or ('ttyACM' in str(bill_port) or 'ttyUSB' in str(bill_port)) else 9600
                else:
                    chosen_baud = int(bill_baud)

                self.bill_acceptor = BillAcceptor(
                    port=bill_port,
                    baudrate=chosen_baud,
                    esp32_mode=bill_esp32_mode,
                    esp32_serial_port=bill_esp32_serial_port,
                    esp32_host=bill_esp32_host,
                    esp32_port=bill_esp32_port
                )
                if self.bill_acceptor.connect():
                    # Register callback to notify UI of bill updates
                    def on_bill_received(amt):
                        logger.info(f"Bill acceptor callback: received {amt}")
                        self._on_bill_update(amt)
                    
                    try:
                        self.bill_acceptor.set_callback(on_bill_received)
                        logger.info("Bill acceptor callback registered")
                    except Exception as e:
                        logger.warning(f"Could not register bill acceptor callback: {e}")
                    
                    self.bill_acceptor.start_reading()
                    logger.info("Bill acceptor reading started")
                else:
                    logger.warning("Bill acceptor connection failed")
                    self.bill_acceptor = None
            except Exception as e:
                logger.warning(f"Error initializing bill acceptor: {e}")
                self.bill_acceptor = None
        else:
            if skip_hardware:
                logger.info("Skipping bill acceptor initialization on non-Linux development host")
        
        # Setup coin hoppers via serial to arduino_bill_forward
        self.coin_hopper = None
        # On non-Linux hosts, skip coin hopper unless the configured port looks like a real serial device
        coin_skip = False
        if run_platform != 'Linux':
            cp = str(coin_hopper_port or '')
            looks_like_serial = cp.lower().startswith('com') or cp.startswith('serial:') or ('tty' in cp) or os.path.exists(cp)
            if not looks_like_serial:
                coin_skip = True

        if not coin_skip:
            try:
                self.coin_hopper = CoinHopper(
                    serial_port=coin_hopper_port,
                    baudrate=coin_hopper_baud
                )
                if self.coin_hopper.connect():
                    logger.info(f"Coin hopper connected to {coin_hopper_port} @ {coin_hopper_baud} baud")
                else:
                    logger.warning(f"Coin hopper connection failed on {coin_hopper_port}")
                    self.coin_hopper = None
            except Exception as e:
                logger.warning(f"Error initializing coin hoppers: {e}")
                self.coin_hopper = None
        else:
            logger.info("Skipping coin hopper initialization on non-Linux development host")
            
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

    def _on_bill_update(self, bill_total_amount):
        """Internal callback invoked when bill acceptor reports an update.

        We forward combined total (coins + bills) to the UI callback if set.
        """
        if self._callback:
            try:
                self._callback(self.get_current_amount())
            except Exception:
                pass

    def get_current_amount(self):
        """Get the total amount received in the current session."""
        with self._lock:
            coin_amount = self.coin_acceptor.get_received_amount()
            bill_amount = 0.0
            if self.bill_acceptor:
                bill_amount = self.bill_acceptor.get_received_amount()
            return coin_amount + bill_amount

    def stop_payment_session(self, required_amount=None):
        """Stop the current payment session and handle change if needed.
        
        Args:
            required_amount (float, optional): If provided, calculate and dispense change
            
        Returns:
            Tuple of (total_received, change_amount, change_status)
        """
        coin_received = self.coin_acceptor.get_received_amount()
        bill_received = 0.0
        if self.bill_acceptor:
            bill_received = self.bill_acceptor.get_received_amount()
        
        total_received = coin_received + bill_received
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
        if self.bill_acceptor:
            self.bill_acceptor.reset_amount()
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
        
        if self.bill_acceptor:
            try:
                self.bill_acceptor.cleanup()
            except Exception:
                pass
