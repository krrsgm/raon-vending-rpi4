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
    
    def __init__(self, serial_port='/dev/ttyUSB1', baudrate=115200, auto_detect=True):
        """Initialize coin hopper relay test.
        
        Args:
            serial_port: Serial port connected to Arduino (default ttyUSB1)
            baudrate: Serial communication speed
            auto_detect: Automatically detect USB serial port if provided port fails
        """
        self.hopper = CoinHopper(
            serial_port=serial_port,
            baudrate=baudrate,
            timeout=2.0,
            auto_detect=auto_detect
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
        print(f"  Auto-detect: {auto_detect}")
    
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
        """Turn on both motors via OPEN commands (1-peso and 5-peso hoppers).
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Open both hoppers (turn on motors)
            response1 = self.hopper.send_command("OPEN 1")
            response2 = self.hopper.send_command("OPEN 5")
            
            if (response1 and "OK" in response1) and (response2 and "OK" in response2):
                self.relay_active = True
                print("[CoinHopperTest] Relays turned ON (OPEN 1 and 5)")
                return True
            else:
                print(f"[CoinHopperTest] Relay ON failed - Response 1: {response1}, Response 2: {response2}")
                return False
        except Exception as e:
            print(f"[CoinHopperTest] Error turning ON relays: {e}")
            return False
    
    def relay_off(self):
        """Turn off both motors via CLOSE commands (1-peso and 5-peso hoppers).
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Close both hoppers (turn off motors)
            response1 = self.hopper.send_command("CLOSE 1")
            response2 = self.hopper.send_command("CLOSE 5")
            
            if (response1 and "OK" in response1) and (response2 and "OK" in response2):
                self.relay_active = False
                print("[CoinHopperTest] Relays turned OFF (CLOSE 1 and 5) - 5 coins detected!")
                return True
            else:
                print(f"[CoinHopperTest] Relay OFF failed - Response 1: {response1}, Response 2: {response2}")
                return False
        except Exception as e:
            print(f"[CoinHopperTest] Error turning OFF relays: {e}")
            return False
    
    def get_sensor_status(self):
        """Get sensor status from Arduino via STATUS command.
        
        Returns:
            Status string or None on error
        """
        try:
            response = self.hopper.send_command("STATUS")
            return response
        except Exception as e:
            print(f"[CoinHopperTest] Error getting sensor status: {e}")
            return None
    
    def get_coin_count(self):
        """Get current coin count from Arduino via STATUS command.
        
        Returns:
            Coin count or None on error
        """
        try:
            response = self.hopper.send_command("STATUS")
            if response:
                # Try to extract counts from status response
                # Arduino returns something like: "one_count: 2 five_count: 1"
                import re
                one_match = re.search(r'one_count[:\s]+([0-9]+)', response, re.IGNORECASE)
                five_match = re.search(r'five_count[:\s]+([0-9]+)', response, re.IGNORECASE)
                
                one_count = int(one_match.group(1)) if one_match else 0
                five_count = int(five_match.group(1)) if five_match else 0
                total = one_count + five_count
                
                return total
            return None
        except Exception as e:
            print(f"[CoinHopperTest] Error getting coin count: {e}")
            return None
    
    def reset_count(self):
        """Reset coin counters by sending RESET command to Arduino.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.hopper.send_command("RESET")
            with self._lock:
                self.coin_count = 0
                self.coin_history.clear()
            print("[CoinHopperTest] Counter reset (RESET command)")
            return True
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

    def relay1_on(self):
        """Turn on 1-peso motor only."""
        try:
            response = self.hopper.send_command("OPEN 1")
            if response and "OK" in response:
                self.relay_active = True
                print("[CoinHopperTest] Relay1 turned ON (OPEN 1)")
                return True
        except Exception as e:
            print(f"[CoinHopperTest] Error turning ON relay1: {e}")
        return False

    def relay1_off(self):
        """Turn off 1-peso motor only."""
        try:
            response = self.hopper.send_command("CLOSE 1")
            if response and "OK" in response:
                self.relay_active = False
                print("[CoinHopperTest] Relay1 turned OFF (CLOSE 1)")
                return True
        except Exception as e:
            print(f"[CoinHopperTest] Error turning OFF relay1: {e}")
        return False

    def relay5_on(self):
        """Turn on 5-peso motor only."""
        try:
            response = self.hopper.send_command("OPEN 5")
            if response and "OK" in response:
                self.relay_active = True
                print("[CoinHopperTest] Relay5 turned ON (OPEN 5)")
                return True
        except Exception as e:
            print(f"[CoinHopperTest] Error turning ON relay5: {e}")
        return False

    def relay5_off(self):
        """Turn off 5-peso motor only."""
        try:
            response = self.hopper.send_command("CLOSE 5")
            if response and "OK" in response:
                self.relay_active = False
                print("[CoinHopperTest] Relay5 turned OFF (CLOSE 5)")
                return True
        except Exception as e:
            print(f"[CoinHopperTest] Error turning OFF relay5: {e}")
        return False

    def test_relay1_control(self):
        """Test relay control for 1-peso hopper only."""
        print("\n[CoinHopperTest] Testing 1-PESO relay control...")
        if not self.relay1_on():
            print("  Failed to turn relay1 ON")
            return False
        time.sleep(1)
        if not self.relay1_off():
            print("  Failed to turn relay1 OFF")
            return False
        time.sleep(1)
        print("  1-PESO relay control test complete!")
        return True

    def test_relay5_control(self):
        """Test relay control for 5-peso hopper only."""
        print("\n[CoinHopperTest] Testing 5-PESO relay control...")
        if not self.relay5_on():
            print("  Failed to turn relay5 ON")
            return False
        time.sleep(1)
        if not self.relay5_off():
            print("  Failed to turn relay5 OFF")
            return False
        time.sleep(1)
        print("  5-PESO relay control test complete!")
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
        # Initialize tester with Arduino serial connection (auto-detect enabled)
        tester = CoinHopperRelayTest(
            serial_port='/dev/ttyUSB1',
            baudrate=115200,
            auto_detect=True  # Automatically detect USB/ACM ports
        )
        
        print("\n" + "="*60)
        print("COIN HOPPER RELAY TEST (Compatible with Real Dispensing)")
        print("="*60)
        print("This test uses same Arduino commands as actual coin dispensing.")
        print("Commands used: OPEN <denom>, CLOSE <denom>, STATUS, STOP")
        print("\nOptions:")
        print("  1 - Test 1-PESO relay control (ON/OFF)")
        print("  2 - Test 5-PESO relay control (ON/OFF)")
        print("  3 - Test sensor reading")
        print("  4 - Monitor coins for 60s (target 5 coins)")
        print("  5 - Custom monitoring duration")
        print("  6 - Get current status")
        print("  7 - Reset coin count/stop job")
        print("  8 - Relay OFF only (CLOSE 1 and 5)")
        print("  9 - Relay ON only (OPEN 1 and 5)")
        print("  Q - Quit")
        print("="*60)
        
        # Connect to Arduino
        if not tester.connect():
            print("\nCannot proceed without Arduino connection.")
            return
        
        print("\nArduino connected successfully!\n")
        
        while True:
            try:
                choice = input("Select option (1-9, Q): ").strip().upper()

                if choice == '1':
                    tester.test_relay1_control()

                elif choice == '2':
                    tester.test_relay5_control()

                elif choice == '3':
                    tester.test_sensor_reading()

                elif choice == '4':
                    try:
                        duration = int(input("Enter duration in seconds: "))
                        target = int(input("Enter target coin count: "))
                        tester.monitor_coins(duration=duration, target_coins=target)
                    except ValueError:
                        print("Invalid input")
                    
                elif choice == '5':
                    tester.monitor_coins(duration=60, target_coins=5)

                elif choice == '6':
                    status = tester.get_status()
                    print(f"\nCurrent Status:")
                    print(f"  Coins detected: {status['coins_detected']}")
                    print(f"  Relay state: {status['relay_state']}")
                    print(f"  Recent coins: {status['recent_coins']}")
                    
                elif choice == '7':
                    tester.reset_count()
                    
                elif choice == '8':
                    tester.relay_off()
                    
                elif choice == '9':
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
