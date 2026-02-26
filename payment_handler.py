from threading import Lock
from coin_handler_esp32 import CoinAcceptorESP32
from coin_hopper import CoinHopper
import logging
import platform
import os
from arduino_serial_utils import detect_arduino_serial_port

try:
    from bill_acceptor import BillAcceptor
except ImportError:
    BillAcceptor = None

try:
    from dht22_handler import get_shared_serial_reader
except Exception:
    get_shared_serial_reader = None

try:
    from coin_handler import CoinAcceptor
except ImportError:
    CoinAcceptor = None

logger = logging.getLogger(__name__)

class PaymentHandler:
    """Payment handler that manages bill and coin acceptance, plus coin hopper dispensing."""
    def __init__(self, config, coin_port=None, coin_baud=115200, bill_port=None,
                 bill_baud=None, bill_esp32_mode=False, bill_esp32_serial_port=None, bill_esp32_host=None, bill_esp32_port=5000,
                 coin_hopper_port=None, coin_hopper_baud=115200, use_gpio_coin=True, coin_gpio_pin=17):
        """Initialize the payment handler with coin acceptor, bill acceptor, and hoppers.

        Args:
            config (dict): Configuration dictionary
            coin_port (str): Serial port for ESP32 coin acceptor (e.g., '/dev/ttyUSB0' or 'COM3'). If None, auto-detect.
            coin_baud (int): Baud rate for coin acceptor (default 115200)
            bill_port (str): Serial port for bill acceptor
                - '/dev/ttyUSB1' if using USB serial adapter
            bill_baud (int, optional): Baud rate for bill acceptor
            bill_esp32_mode (bool): If True, expect bill events forwarded by ESP32
            bill_esp32_serial_port (str): Serial port connected to ESP32
            bill_esp32_host (str): Host for ESP32 TCP proxy
            bill_esp32_port (int): Port for ESP32 TCP proxy
            coin_hopper_port (str): Serial port connected to arduino_bill_forward
            coin_hopper_baud (int): Baud rate for coin hopper (default 115200)
            use_gpio_coin (bool): If True, use GPIO-based coin acceptor (Raspberry Pi)
            coin_gpio_pin (int): GPIO pin for coin acceptor (default 17)
        """
        # Shared serial reader for Arduino Uno (DHT/IR/coin/bill) if enabled.
        # This avoids multiple consumers opening the same USB serial port.
        shared_reader = None
        auto_port = detect_arduino_serial_port(preferred_port=coin_port or bill_port or coin_hopper_port)
        if not coin_port:
            coin_port = auto_port
        if not bill_port:
            bill_port = auto_port
        if not coin_hopper_port:
            coin_hopper_port = auto_port
        try:
            hw_cfg = config.get('hardware', {}) if isinstance(config, dict) else {}
            dht_cfg = hw_cfg.get('dht22_sensors', {})
            ir_cfg = hw_cfg.get('ir_sensors', {})
            use_shared = bool(
                dht_cfg.get('use_esp32_serial', False)
                or ir_cfg.get('use_esp32_serial', False)
                or (not use_gpio_coin)
            )
            if use_shared and get_shared_serial_reader:
                shared_reader = get_shared_serial_reader(port=coin_port or bill_port, baudrate=coin_baud or 115200)
        except Exception:
            shared_reader = None
        self._shared_reader = shared_reader

        # Setup coin acceptor - prefer GPIO-based on Raspberry Pi, fallback to ESP32
        self.coin_acceptor = None
        self.use_gpio_coin = use_gpio_coin and (platform.system() == 'Linux' or CoinAcceptor is not None)
        
        if self.use_gpio_coin and CoinAcceptor:
            try:
                self.coin_acceptor = CoinAcceptor(coin_pin=coin_gpio_pin, counter_pin=None)
                print(f"DEBUG: GPIO coin acceptor initialized on GPIO {coin_gpio_pin}")
                logger.info(f"GPIO coin acceptor initialized on GPIO {coin_gpio_pin}")
                
                # Register callback for coin updates if available
                try:
                    if hasattr(self.coin_acceptor, 'set_callback'):
                        self.coin_acceptor.set_callback(self._on_coin_update)
                        print(f"DEBUG: Coin acceptor callback registered")
                except Exception as e:
                    print(f"DEBUG: Failed to register coin acceptor callback: {e}")
                    
            except Exception as e:
                print(f"DEBUG: Failed to initialize GPIO coin acceptor: {e}")
                logger.warning(f"Failed to initialize GPIO coin acceptor: {e}")
                self.coin_acceptor = None
        
        # Fallback to ESP32-based coin acceptor if GPIO failed
        if not self.coin_acceptor and not self.use_gpio_coin:
            try:
                self.coin_acceptor = CoinAcceptorESP32(port=coin_port, baudrate=coin_baud, shared_reader=shared_reader)
                print(f"DEBUG: ESP32 coin acceptor initialized")
                logger.info("ESP32 coin acceptor initialized")
            except Exception as e:
                print(f"DEBUG: Failed to initialize ESP32 coin acceptor: {e}")
                logger.warning(f"Failed to initialize ESP32 coin acceptor: {e}")
        
        # Ensure coin acceptor is initialized
        if not self.coin_acceptor:
            print("WARNING: No coin acceptor available (neither GPIO nor ESP32)")
            logger.warning("No coin acceptor available (neither GPIO nor ESP32)")
        else:
            # Ensure payment UI receives push updates from coin acceptor in all modes.
            try:
                if hasattr(self.coin_acceptor, 'set_callback'):
                    self.coin_acceptor.set_callback(self._on_coin_update)
            except Exception:
                pass
        
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
                    esp32_port=bill_esp32_port,
                    shared_reader=shared_reader
                )
                print(f"DEBUG: BillAcceptor created (before connect)")
                if self.bill_acceptor.connect():
                    print(f"DEBUG: BillAcceptor connected successfully")
                    # Register callback to notify UI of bill updates
                    try:
                        # Register bill acceptor callback directly to PaymentHandler._on_bill_update
                        self.bill_acceptor.set_callback(self._on_bill_update)
                        logger.info("Bill acceptor callback registered")
                        # Extra debug print to ensure callback registration is visible in logs
                        print("DEBUG: PaymentHandler set BillAcceptor callback (direct)")
                    except Exception as e:
                        logger.warning(f"Could not register bill acceptor callback: {e}")
                        print(f"DEBUG: Failed to set BillAcceptor callback: {e}")
                    
                    # Start reading bills
                    if self.bill_acceptor.start_reading():
                        print(f"DEBUG: BillAcceptor reading started successfully")
                        logger.info("Bill acceptor reading started")
                    else:
                        print(f"DEBUG: BillAcceptor failed to start reading")
                else:
                    logger.warning("Bill acceptor connection failed")
                    print(f"DEBUG: BillAcceptor connection failed")
                    self.bill_acceptor = None
            except Exception as e:
                logger.warning(f"Error initializing bill acceptor: {e}")
                print(f"DEBUG: Error initializing bill acceptor: {e}")
                self.bill_acceptor = None
        else:
            if skip_hardware:
                logger.info("Skipping bill acceptor initialization on non-Linux development host")
            else:
                print("DEBUG: BillAcceptor class not available")
        
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

    def start_payment_session(self, required_amount=None, on_payment_update=None, on_change_update=None):
        """Start a new payment session.
        
        Args:
            required_amount (float, optional): Target amount to collect
            on_payment_update (callable, optional): Callback(amount) when coins received
        """
        self._callback = on_payment_update
        # Optional callback for change-dispense status messages
        self._change_callback = on_change_update
        # Debug: show that start_payment_session set the callback
        try:
            print(f"DEBUG: PaymentHandler.start_payment_session: callback set = {bool(self._callback)}")
        except Exception:
            pass
        if self.coin_acceptor:
            self.coin_acceptor.reset_amount()
        if self.bill_acceptor:
            self.bill_acceptor.reset_amount()
        # Safety: hopper relays must be off unless actively dispensing change.
        if self.coin_hopper:
            try:
                self.coin_hopper.ensure_relays_off()
            except Exception:
                pass
        return True

    def _on_bill_update(self, bill_total_amount, prompt_msg=None):
        """Internal callback invoked when bill acceptor reports an update.

        We forward combined total (coins + bills) to the UI callback if set.
        """
        # Debug: incoming bill update
        try:
            print(f"DEBUG: PaymentHandler._on_bill_update received bill_total_amount={bill_total_amount}, current_total={self.get_current_amount()}, callback_present={bool(self._callback)}")
        except Exception:
            pass

        if self._callback:
            try:
                self._callback(self.get_current_amount())
            except Exception as e:
                print(f"DEBUG: PaymentHandler._on_bill_update callback error: {e}")
                pass

    def _on_coin_update(self, coin_total_amount):
        """Internal callback invoked when coin acceptor reports an update.

        We forward combined total (coins + bills) to the UI callback if set.
        """
        # Debug: incoming coin update
        try:
            print(f"DEBUG: PaymentHandler._on_coin_update received coin_total_amount={coin_total_amount}, current_total={self.get_current_amount()}, callback_present={bool(self._callback)}")
        except Exception:
            pass

        if self._callback:
            try:
                self._callback(self.get_current_amount())
            except Exception as e:
                print(f"DEBUG: PaymentHandler._on_coin_update callback error: {e}")
                pass

    def get_current_amount(self):
        """Get the total amount received in the current session."""
        with self._lock:
            coin_amount = 0.0
            if self.coin_acceptor:
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
        coin_received = 0.0
        if self.coin_acceptor:
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
            # Round to nearest whole peso and ensure non-negative integer
            try:
                change_int = int(round(change_needed))
            except Exception:
                change_int = int(change_needed)
            if change_int <= 0:
                change_int = 0
            if change_int > 0 and self.coin_hopper:
                success, dispensed, message = self.coin_hopper.dispense_change(
                    change_int,
                    callback=self._change_callback
                )
                if success:
                    change_amount = dispensed
                    change_status = f"Change dispensed: ₱{dispensed}"
                else:
                    # Preserve partial dispense amount so UI reflects actual output.
                    try:
                        change_amount = max(0, int(dispensed))
                    except Exception:
                        change_amount = 0
                    change_status = f"Error: {message}"
            else:
                change_status = "Change dispenser not available"
        if self.coin_acceptor:
            self.coin_acceptor.reset_amount()
        if self.bill_acceptor:
            self.bill_acceptor.reset_amount()
        # Always return hopper to safe OFF state after session end.
        if self.coin_hopper:
            try:
                self.coin_hopper.ensure_relays_off()
            except Exception:
                pass
        self._callback = None
        self._change_callback = None
        return total_received, change_amount, change_status

    def cleanup(self):
        """Clean up GPIO resources."""
        try:
            if self.coin_acceptor:
                self.coin_acceptor.cleanup()
        except Exception as e:
            logger.debug(f"Error cleaning up coin acceptor: {e}")
            pass
            
        if self.coin_hopper:
            try:
                self.coin_hopper.cleanup()
            except Exception:
                pass
        
        if self.bill_acceptor:
            try:
                self.bill_acceptor.disconnect()
            except Exception:
                pass
