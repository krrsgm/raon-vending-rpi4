import RPi.GPIO as GPIO
import time
from coin_handler import CoinAcceptor

def main():
    try:
        # Initialize coin acceptor
        coin_acceptor = CoinAcceptor(coin_pin=17)
        print("Coin acceptor initialized. Insert coins to test...")
        
        # Main loop
        while True:
            current_amount = coin_acceptor.get_received_amount()
            if current_amount > 0:
                print(f"Received amount: ₱{current_amount:.2f}")
                coin_acceptor.reset_amount()
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        coin_acceptor.cleanup()
        GPIO.cleanup()

if __name__ == "__main__":
    main()