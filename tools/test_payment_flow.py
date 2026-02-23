#!/usr/bin/env python3
"""
test_payment_flow.py
Test the complete payment flow: bill acceptor, coin acceptor, and UI updates
"""
import time
from bill_acceptor import BillAcceptor
from coin_handler import CoinAcceptor
from payment_handler import PaymentHandler

print("\n" + "="*60)
print("PAYMENT FLOW TEST")
print("="*60)

# Test 1: Bill Acceptor
print("\n[TEST 1] Bill Acceptor")
print("-" * 60)
try:
    bill = BillAcceptor(port='/dev/ttyACM0', baudrate=9600)
    if bill.connect():
        print("✓ Bill acceptor connected")
        bill.set_callback(lambda amt: print(f"  Bill update: ₱{amt}"))
        bill.start_reading()
        print("✓ Bill acceptor started")
        print("  Insert a bill for 5 seconds...")
        time.sleep(5)
        amt = bill.get_received_amount()
        print(f"  Received: ₱{amt}")
        bill.stop_reading()
    else:
        print("✗ Bill acceptor connection failed")
except Exception as e:
    print(f"✗ Bill acceptor error: {e}")

# Test 2: Coin Acceptor
print("\n[TEST 2] Coin Acceptor (GPIO)")
print("-" * 60)
try:
    coin = CoinAcceptor(coin_pin=17)
    print(f"✓ Coin acceptor initialized on GPIO 17")
    print("  Insert coins for 5 seconds...")
    time.sleep(5)
    amt = coin.get_received_amount()
    print(f"  Received: ₱{amt}")
except Exception as e:
    print(f"✗ Coin acceptor error: {e}")

# Test 3: Payment Handler
print("\n[TEST 3] Payment Handler (Combined)")
print("-" * 60)
try:
    config = {
        'hardware': {
            'bill_acceptor': {
                'serial_port': '/dev/ttyACM0',
                'baudrate': 9600
            }
        },
        'esp32_host': 'serial:/dev/ttyS0'
    }
    
    handler = PaymentHandler(config, coin_port=None)
    print(f"✓ Payment handler initialized")
    
    required_amount = 50.0
    handler.start_payment_session(required_amount, on_payment_update=lambda amt: print(f"  Payment update: ₱{amt}"))
    print(f"  Waiting for ₱{required_amount}...")
    
    for i in range(10):
        time.sleep(1)
        current = handler.get_current_amount()
        print(f"  [{i+1}s] Received: ₱{current}")
        if current >= required_amount:
            print("✓ Payment complete!")
            break
            
except Exception as e:
    print(f"✗ Payment handler error: {e}")

print("\n" + "="*60)
