"""
Test script for coin hopper with relay control.

This test monitors coin detection and controls a relay:
- Relay stays ON while detecting coins
- When 5 coins pass through, turn OFF the relay
- Reset after successful detection

Pin assignments:
- Pin 11: 1₱ coin hopper sensor
- Pin 12: 5₱ coin hopper sensor
- Pin 9: Relay control for 1₱ hopper
- Pin 10: Relay control for 5₱ hopper
"""

import RPi.GPIO as GPIO
import time
import threading
from collections import deque
from coin_hopper import CoinHopper

class CoinHopperRelay:
    """Controls relay based on coin hopper detection."""
    
    def __init__(self, coin_sensor_1p=11, coin_sensor_5p=12, relay_pin_1p=9, relay_pin_5p=10,
                 serial_port='/dev/ttyUSB1', baudrate=115200):
        """Initialize coin hopper relay controller.
        
        Args:
            coin_sensor_1p: Pin for 1₱ coin sensor (default 11)
            coin_sensor_5p: Pin for 5₱ coin sensor (default 12)
            relay_pin_1p: Pin for 1₱ relay control (default 9)
            relay_pin_5p: Pin for 5₱ relay control (default 10)
            serial_port: Serial port for coin hopper Arduino
            baudrate: Serial baudrate
        """
        self.coin_sensor_1p = coin_sensor_1p
        self.coin_sensor_5p = coin_sensor_5p
        self.relay_pin_1p = relay_pin_1p
        self.relay_pin_5p = relay_pin_5p
        self.serial_port = serial_port
        self.baudrate = baudrate
        
        # State tracking
        self.coin_count = 0
        self.relay_active = True
        self.is_running = False
        self.monitoring_thread = None
        self.coin_history = deque(maxlen=10)  # Last 10 coin detections
        self._lock = threading.Lock()
        
        # Coin hopper instance
        self.hopper = None
        
        # Configure GPIO
        GPIO.setmode(GPIO.BOARD)  # Use BOARD numbering (physical pin numbers)
        
        # Setup relay pins (OUTPUT)
        GPIO.setup(self.relay_pin_1p, GPIO.OUT, initial=GPIO.HIGH)  # Relay ON (HIGH)
        GPIO.setup(self.relay_pin_5p, GPIO.OUT, initial=GPIO.HIGH)  # Relay ON (HIGH)
        
        # Setup sensor pins (INPUT)
        GPIO.setup(self.coin_sensor_1p, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.coin_sensor_5p, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Setup coin detection callbacks
        GPIO.add_event_detect(self.coin_sensor_1p, GPIO.FALLING, 
                            callback=self._on_1p_coin, bouncetime=100)
        GPIO.add_event_detect(self.coin_sensor_5p, GPIO.FALLING, 
                            callback=self._on_5p_coin, bouncetime=100)
        
        print("[CoinHopperRelay] Initialized")
        print(f"  1₱ relay pin: {self.relay_pin_1p}")
        print(f"  5₱ relay pin: {self.relay_pin_5p}")
        print(f"  1₱ sensor pin: {self.coin_sensor_1p}")
        print(f"  5₱ sensor pin: {self.coin_sensor_5p}")
    
    def _on_1p_coin(self, channel):
        """Callback when 1₱ coin detected."""
        self._handle_coin_detection('1P')
    
    def _on_5p_coin(self, channel):
        """Callback when 5₱ coin detected."""
        self._handle_coin_detection('5P')
    
    def _handle_coin_detection(self, denomination):
        """Handle coin detection and update relay state.
        
        Args:
            denomination: '1P' or '5P'
        """
        with self._lock:
            self.coin_count += 1
            self.coin_history.append((denomination, time.time()))
            
            print(f"[CoinHopper] Coin detected: {denomination} (Total: {self.coin_count})")
            
            # Check if we've reached 5 coins
            if self.coin_count >= 5:
                self._turn_off_relay()
                return
            
            # Keep relay ON while detecting coins
            if not self.relay_active:
                self._turn_on_relay()
    
    def _turn_on_relay(self):
        """Turn on both relays."""
        if self.relay_active:
            return
        
        try:
            GPIO.output(self.relay_pin_1p, GPIO.HIGH)
            GPIO.output(self.relay_pin_5p, GPIO.HIGH)
            self.relay_active = True
            print("[CoinHopperRelay] Relays turned ON")
        except Exception as e:
            print(f"[CoinHopperRelay] Error turning ON relays: {e}")
    
    def _turn_off_relay(self):
        """Turn off both relays."""
        if not self.relay_active:
            return
        
        try:
            GPIO.output(self.relay_pin_1p, GPIO.LOW)
            GPIO.output(self.relay_pin_5p, GPIO.LOW)
            self.relay_active = False
            print("[CoinHopperRelay] Relays turned OFF - 5 coins detected!")
        except Exception as e:
            print(f"[CoinHopperRelay] Error turning OFF relays: {e}")
    
    def connect_hopper(self):
        """Connect to coin hopper via serial.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.hopper = CoinHopper(
                serial_port=self.serial_port,
                baudrate=self.baudrate
            )
            if self.hopper.connect():
                print("[CoinHopperRelay] Connected to coin hopper")
                return True
            else:
                print("[CoinHopperRelay] Failed to connect to coin hopper")
                return False
        except Exception as e:
            print(f"[CoinHopperRelay] Error connecting to hopper: {e}")
            return False
    
    def get_status(self):
        """Get current status.
        
        Returns:
            Dict with status information
        """
        with self._lock:
            status = {
                'coins_detected': self.coin_count,
                'relay_active': self.relay_active,
                'relay_state': 'ON' if self.relay_active else 'OFF',
                'coin_history': list(self.coin_history)
            }
            return status
    
    def reset_counter(self):
        """Reset coin counter after dispensing."""
        with self._lock:
            print(f"[CoinHopperRelay] Resetting counter (was: {self.coin_count})")
            self.coin_count = 0
            self.coin_history.clear()
            # Turn relay back ON for next cycle
            if not self.relay_active:
                self._turn_on_relay()
    
    def run_test_series(self, duration=60):
        """Run continuous monitoring test.
        
        Args:
            duration: Test duration in seconds
        """
        print(f"\n[CoinHopperRelay] Starting {duration}s test...")
        print("Insert coins one at a time (5 target)...")
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration:
                status = self.get_status()
                
                # Print status every 2 seconds
                if int(time.time() - start_time) % 2 == 0:
                    print(f"Status: {status['coins_detected']} coins, "
                          f"Relay: {status['relay_state']}")
                
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\nTest interrupted by user")
    
    def manual_dispense_test(self, denomination=1, count=5):
        """Test dispensing coins through hopper.
        
        Args:
            denomination: 1 or 5
            count: Number of coins
        """
        if not self.hopper:
            print("[CoinHopperRelay] Hopper not connected")
            return
        
        print(f"\n[CoinHopperRelay] Dispensing {count} {denomination}₱ coins...")
        success, dispensed, msg = self.hopper.dispense_coins(denomination, count)
        print(f"Result: {msg}")
        
        if success and dispensed >= count:
            print("[CoinHopperRelay] Coins dispensed successfully")
        else:
            print(f"[CoinHopperRelay] Dispensing error: {msg}")
    
    def cleanup(self):
        """Clean up GPIO and connections."""
        try:
            print("\n[CoinHopperRelay] Cleaning up...")
            
            # Turn off relays
            try:
                GPIO.output(self.relay_pin_1p, GPIO.LOW)
                GPIO.output(self.relay_pin_5p, GPIO.LOW)
            except:
                pass
            time.sleep(0.1)
            
            # Disconnect hopper
            if self.hopper:
                self.hopper.disconnect()
            
            # Cleanup GPIO
            GPIO.cleanup()
            print("[CoinHopperRelay] Cleanup complete")
        except Exception as e:
            print(f"[CoinHopperRelay] Error during cleanup: {e}")


def main():
    """Main test function."""
    relay_controller = None
    
    try:
        # Initialize relay controller
        relay_controller = CoinHopperRelay(
            coin_sensor_1p=11,
            coin_sensor_5p=12,
            relay_pin_1p=9,
            relay_pin_5p=10,
            serial_port='/dev/ttyUSB1',
            baudrate=115200
        )
        
        print("\n" + "="*60)
        print("COIN HOPPER RELAY TEST")
        print("="*60)
        print("Options:")
        print("  1 - Monitor coin detection (60s)")
        print("  2 - Manual dispense test (5 coins of 1₱)")
        print("  3 - Manual dispense test (1 coin of 5₱)")
        print("  4 - Get current status")
        print("  5 - Reset counter")
        print("  Q - Quit")
        print("="*60)
        
        while True:
            try:
                choice = input("\nSelect option (1-5, Q): ").strip().upper()
                
                if choice == '1':
                    relay_controller.run_test_series(duration=60)
                    
                elif choice == '2':
                    # Try to connect and dispense
                    if relay_controller.connect_hopper():
                        relay_controller.manual_dispense_test(denomination=1, count=5)
                    else:
                        print("Could not connect to hopper (may not be connected)")
                    
                elif choice == '3':
                    if relay_controller.connect_hopper():
                        relay_controller.manual_dispense_test(denomination=5, count=1)
                    else:
                        print("Could not connect to hopper (may not be connected)")
                    
                elif choice == '4':
                    status = relay_controller.get_status()
                    print(f"\nCurrent Status:")
                    print(f"  Coins detected: {status['coins_detected']}")
                    print(f"  Relay state: {status['relay_state']}")
                    print(f"  Recent coins: {status['coin_history']}")
                    
                elif choice == '5':
                    relay_controller.reset_counter()
                    
                elif choice == 'Q':
                    break
                    
                else:
                    print("Invalid option")
                    
            except EOFError:
                # Handle EOF for non-interactive mode
                break
            except KeyboardInterrupt:
                print("\nInterrupted")
                break
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if relay_controller:
            relay_controller.cleanup()


if __name__ == "__main__":
    main()
