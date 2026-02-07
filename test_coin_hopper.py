"""
Test script for coin hopper with relay control via Arduino.

This test monitors coin detection through Arduino serial connection and controls relays:
- Relay stays ON while detecting coins
- When 5 coins pass through, turn OFF the relay
- Reset after successful detection

Arduino pin assignments:
- Pin 11: 1₱ coin hopper sensor
- Pin 12: 5₱ coin hopper sensor  
- Pin 9: Relay control for 1₱ hopper
- Pin 10: Relay control for 5₱ hopper

Communication: USB serial to Arduino (coin hopper controller)
"""

import serial
import time
import threading
from collections import deque
from coin_hopper import CoinHopper


class CoinHopperRelayTest:
    """Test coin hopper relay control via Arduino serial connection."""
    
    def __init__(self, serial_port='/dev/ttyUSB1', baudrate=115200):
        """Initialize coin hopper relay test.
        
        Args:
            serial_port: Serial port connected to Arduino
            baudrate: Serial communication speed
        """
        self.hopper = CoinHopper(
            serial_port=serial_port,
            baudrate=baudrate,
            timeout=2.0
        )
        
        # State tracking
        self.coin_count = 0
        self.relay_active = False
        self.coin_history = deque(maxlen=10)  # Last 10 coin detections
        self._lock = threading.Lock()
        self.monitoring = False
        
        print("[CoinHopperTest] Initialized")
        print(f"  Serial port: {serial_port}")
        print(f"  Baudrate: {baudrate}")
    
    def connect(self):
        """Connect to Arduino via coin hopper serial.
        
        Returns:
            True if successful, False otherwise
        """
        if self.hopper.connect():
            print("[CoinHopperTest] Connected to Arduino")
            return True
        else:
            print("[CoinHopperTest] Failed to connect to Arduino")
            return False
    
    def relay_on(self):
        """Turn on both relays via Arduino command.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.hopper.send_command("RELAY_ON")
            if response and ("OK" in response or "ON" in response):
                self.relay_active = True
                print("[CoinHopperTest] Relay turned ON")
                return True
            else:
                print(f"[CoinHopperTest] Relay ON failed: {response}")
                return False
        except Exception as e:
            print(f"[CoinHopperTest] Error turning ON relay: {e}")
            return False
    
    def relay_off(self):
        """Turn off both relays via Arduino command.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.hopper.send_command("RELAY_OFF")
            if response and ("OK" in response or "OFF" in response):
                self.relay_active = False
                print("[CoinHopperTest] Relay turned OFF - 5 coins detected!")
                return True
            else:
                print(f"[CoinHopperTest] Relay OFF failed: {response}")
                return False
        except Exception as e:
            print(f"[CoinHopperTest] Error turning OFF relay: {e}")
            return False
    
    def get_sensor_status(self):
        """Get sensor status from Arduino.
        
        Returns:
            Status string or None on error
        """
        try:
            response = self.hopper.send_command("SENSOR_STATUS")
            return response
        except Exception as e:
            print(f"[CoinHopperTest] Error getting sensor status: {e}")
            return None
    
    def get_coin_count(self):
        """Get current coin count from Arduino.
        
        Returns:
            Coin count or None on error
        """
        try:
            response = self.hopper.send_command("COIN_COUNT")
            if response:
                # Try to extract count from response (format: "COUNT: 5")
                import re
                match = re.search(r'(\d+)', response)
                if match:
                    return int(match.group(1))
            return None
        except Exception as e:
            print(f"[CoinHopperTest] Error getting coin count: {e}")
            return None
    
    def reset_count(self):
        """Reset coin counter on Arduino.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.hopper.send_command("RESET_COUNT")
            if response and "OK" in response:
                with self._lock:
                    self.coin_count = 0
                    self.coin_history.clear()
                print("[CoinHopperTest] Counter reset")
                return True
            return False
        except Exception as e:
            print(f"[CoinHopperTest] Error resetting count: {e}")
            return False
    
    def monitor_coins(self, duration=60, target_coins=5):
        """Monitor coin detection for specified duration.
        
        Args:
            duration: Monitoring duration in seconds
            target_coins: Number of coins to detect before turning off relay
        """
        print(f"\n[CoinHopperTest] Starting {duration}s monitoring (target: {target_coins} coins)...")
        print("Coins detected; relay will turn off when target is reached\n")
        
        # Clear and initialize
        self.reset_count()
        self.relay_on()
        
        start_time = time.time()
        self.monitoring = True
        
        try:
            while self.monitoring and (time.time() - start_time) < duration:
                # Check coin count from Arduino
                count = self.get_coin_count()
                
                if count is not None:
                    with self._lock:
                        if count != self.coin_count:
                            # New coin detected
                            self.coin_count = count
                            self.coin_history.append((count, time.time()))
                            print(f"Coin detected! Total: {count}/{target_coins}")
                            
                            # Check if we reached target
                            if count >= target_coins:
                                print(f"\n*** TARGET REACHED: {count} coins detected ***")
                                self.relay_off()
                                break
                
                # Get and display sensor status periodically
                if int(time.time() - start_time) % 5 == 0:
                    status = self.get_sensor_status()
                    if status:
                        print(f"[Status] {status}")
                
                time.sleep(0.5)
        
        except KeyboardInterrupt:
            print("\nMonitoring interrupted by user")
        finally:
            self.monitoring = False
    
    def test_relay_control(self):
        """Test relay on/off control.
        
        Returns:
            True if both relay states work, False otherwise
        """
        print("\n[CoinHopperTest] Testing relay control...")
        
        # Test relay ON
        print("  Testing relay ON...")
        if not self.relay_on():
            print("  Failed to turn relay ON")
            return False
        time.sleep(1)
        
        # Test relay OFF
        print("  Testing relay OFF...")
        if not self.relay_off():
            print("  Failed to turn relay OFF")
            return False
        time.sleep(1)
        
        # Restore to ON state
        print("  Restoring relay to ON state...")
        if not self.relay_on():
            print("  Failed to restore relay ON")
            return False
        
        print("  Relay control test complete!")
        return True
    
    def test_sensor_reading(self):
        """Test sensor status reading.
        
        Returns:
            True if sensor can be read, False otherwise
        """
        print("\n[CoinHopperTest] Testing sensor reading...")
        
        status = self.get_sensor_status()
        if status:
            print(f"  Sensor status: {status}")
            return True
        else:
            print("  Failed to read sensor status")
            return False
    
    def get_status(self):
        """Get current test status.
        
        Returns:
            Dict with status information
        """
        with self._lock:
            status = {
                'coins_detected': self.coin_count,
                'relay_active': self.relay_active,
                'relay_state': 'ON' if self.relay_active else 'OFF',
                'recent_coins': list(self.coin_history)
            }
            return status
    
    def cleanup(self):
        """Clean up and disconnect."""
        try:
            print("\n[CoinHopperTest] Cleaning up...")
            
            self.monitoring = False
            
            # Turn off relay
            try:
                self.relay_off()
            except:
                pass
            
            # Disconnect from Arduino
            if self.hopper:
                self.hopper.disconnect()
            
            print("[CoinHopperTest] Cleanup complete")
        except Exception as e:
            print(f"[CoinHopperTest] Error during cleanup: {e}")


def main():
    """Main test function."""
    tester = None
    
    try:
        # Initialize tester with Arduino serial connection
        tester = CoinHopperRelayTest(
            serial_port='/dev/ttyUSB1',
            baudrate=115200
        )
        
        print("\n" + "="*60)
        print("COIN HOPPER RELAY TEST (Arduino Control)")
        print("="*60)
        print("Options:")
        print("  1 - Test relay control (ON/OFF)")
        print("  2 - Test sensor reading")
        print("  3 - Monitor coins for 60s (target 5 coins)")
        print("  4 - Custom monitoring duration")
        print("  5 - Get current status")
        print("  6 - Reset coin count")
        print("  7 - Relay OFF only")
        print("  8 - Relay ON only")
        print("  Q - Quit")
        print("="*60)
        
        # Connect to Arduino
        if not tester.connect():
            print("\nCannot proceed without Arduino connection.")
            return
        
        print("\nArduino connected successfully!\n")
        
        while True:
            try:
                choice = input("Select option (1-8, Q): ").strip().upper()
                
                if choice == '1':
                    tester.test_relay_control()
                    
                elif choice == '2':
                    tester.test_sensor_reading()
                    
                elif choice == '3':
                    tester.monitor_coins(duration=60, target_coins=5)
                    
                elif choice == '4':
                    try:
                        duration = int(input("Enter duration in seconds: "))
                        target = int(input("Enter target coin count: "))
                        tester.monitor_coins(duration=duration, target_coins=target)
                    except ValueError:
                        print("Invalid input")
                    
                elif choice == '5':
                    status = tester.get_status()
                    print(f"\nCurrent Status:")
                    print(f"  Coins detected: {status['coins_detected']}")
                    print(f"  Relay state: {status['relay_state']}")
                    print(f"  Recent coins: {status['recent_coins']}")
                    
                elif choice == '6':
                    tester.reset_count()
                    
                elif choice == '7':
                    tester.relay_off()
                    
                elif choice == '8':
                    tester.relay_on()
                    
                elif choice == 'Q':
                    break
                    
                else:
                    print("Invalid option")
                    
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nInterrupted")
                break
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if tester:
            tester.cleanup()


if __name__ == "__main__":
    main()
