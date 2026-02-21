#!/usr/bin/env python3
"""
Test script for ESP32 Coin Acceptor
Tests coin detection and balance tracking
"""

import time
import sys
from coin_handler_esp32 import CoinAcceptorESP32

def print_header(text):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def test_coin_acceptor():
    """Test the ESP32 coin acceptor"""
    
    print_header("ESP32 Coin Acceptor Test")
    
    # Initialize coin acceptor
    print("[1] Initializing ESP32 coin acceptor...")
    try:
        coin = CoinAcceptorESP32(port=None, baudrate=115200)  # Auto-detect port
        print("✓ Connected to ESP32 coin acceptor")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return False
    
    # Wait for initial connection
    time.sleep(1)
    
    # Configure coin values
    print("\n[2] Configuring coin outputs (A1-A6)...")
    try:
        coin.set_coin_value(1, 1.0)   # A1: 1 peso
        coin.set_coin_value(2, 1.0)   # A2: 1 peso
        coin.set_coin_value(3, 5.0)   # A3: 5 pesos
        coin.set_coin_value(4, 5.0)   # A4: 5 pesos
        coin.set_coin_value(5, 10.0)  # A5: 10 pesos
        coin.set_coin_value(6, 10.0)  # A6: 10 pesos
        print("✓ Coin values configured")
        time.sleep(0.5)
    except Exception as e:
        print(f"✗ Failed to configure: {e}")
        coin.cleanup()
        return False
    
    # Display initial status
    print("\n[3] Getting initial status...")
    try:
        # Get balance before starting test
        initial_balance = coin.get_received_amount()
        print(f"✓ Initial Balance: ₱{initial_balance:.2f}")
    except Exception as e:
        print(f"✗ Error getting balance: {e}")
        coin.cleanup()
        return False
    
    # Test instructions
    print_header("Ready for Coin Insertion Test")
    print("Follow these instructions:")
    print("  1. Choose which coin output to test (A1-A6)")
    print("  2. Insert coins into the chosen output")
    print("  3. Watch the balance increase in real-time")
    print("\nCoin outputs:")
    print("  A1/A2: ₱1 (1 peso coins)")
    print("  A3/A4: ₱5 (5 peso coins)")
    print("  A5/A6: ₱10 (10 peso coins)")
    print("\nExample: To test A3, type: 3")
    print("\n")
    
    # Test loop
    try:
        while True:
            try:
                output = input("Enter output number (1-6) or 'q' to quit: ").strip().upper()
                
                if output == 'Q':
                    print("\nTest completed.")
                    break
                
                try:
                    output_num = int(output)
                except ValueError:
                    print("✗ Invalid input. Please enter 1-6 or 'q'")
                    continue
                
                if output_num < 1 or output_num > 6:
                    print("✗ Output must be between 1 and 6")
                    continue
                
                # Set active output
                print(f"\n[SET OUTPUT] Switching to output A{output_num}...")
                coin.set_output(output_num)
                time.sleep(0.5)
                
                # Start monitoring balance
                last_balance = coin.get_received_amount()
                print(f"\nMonitoring output A{output_num}...")
                print(f"Current balance: ₱{last_balance:.2f}")
                print("Insert coins now (press Ctrl+C when done)...\n")
                
                # Poll for coin insertions
                start_time = time.time()
                no_change_count = 0
                
                while True:
                    current_balance = coin.get_received_amount()
                    
                    # Check if balance changed
                    if current_balance > last_balance:
                        coin_value = current_balance - last_balance
                        print(f"✓ Coin detected! +₱{coin_value:.2f} | Total: ₱{current_balance:.2f}")
                        last_balance = current_balance
                        no_change_count = 0
                    else:
                        no_change_count += 1
                    
                    time.sleep(0.1)
                    
                    # If no coins detected for 5 seconds, prompt for next action
                    if no_change_count > 50:  # 5 seconds
                        elapsed = time.time() - start_time
                        print(f"\n[INFO] No coins inserted for 5 seconds (elapsed: {elapsed:.1f}s)")
                        print(f"Final balance for A{output_num}: ₱{current_balance:.2f}")
                        break
                        
            except KeyboardInterrupt:
                current_balance = coin.get_received_amount()
                elapsed = time.time() - start_time
                print(f"\n\n[STOPPED] Monitoring stopped")
                print(f"Final balance: ₱{current_balance:.2f}")
                print(f"Time elapsed: {elapsed:.1f}s")
                continue
                
    except KeyboardInterrupt:
        print("\n\nTest terminated by user")
    except Exception as e:
        print(f"\n✗ Error during test: {e}")
    finally:
        # Cleanup
        print("\n[CLEANUP] Closing ESP32 connection...")
        coin.cleanup()
        print("✓ Connection closed")
    
    return True

def quick_balance_check():
    """Quick test to just check current balance"""
    print_header("Quick Balance Check")
    
    print("[1] Connecting to ESP32...")
    try:
        coin = CoinAcceptorESP32(port=None, baudrate=115200)
        time.sleep(0.5)
        
        balance = coin.get_received_amount()
        print(f"✓ Current balance: ₱{balance:.2f}")
        
        print(f"\nResetting balance...")
        coin.reset_amount()
        time.sleep(0.5)
        
        new_balance = coin.get_received_amount()
        print(f"✓ New balance: ₱{new_balance:.2f}")
        
        coin.cleanup()
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Main entry point"""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║         ESP32 Coin Acceptor Test Suite                    ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    print("\nSelect test mode:")
    print("  1. Full coin insertion test (interactive)")
    print("  2. Quick balance check")
    print("  3. Exit")
    
    mode = input("\nEnter choice (1-3): ").strip()
    
    if mode == "1":
        success = test_coin_acceptor()
        sys.exit(0 if success else 1)
    elif mode == "2":
        success = quick_balance_check()
        sys.exit(0 if success else 1)
    elif mode == "3":
        print("Exiting...")
        sys.exit(0)
    else:
        print("Invalid choice")
        sys.exit(1)

if __name__ == "__main__":
    main()
