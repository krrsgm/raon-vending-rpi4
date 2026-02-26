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
    bill = BillAcceptor(port='/dev/ttyUSB0', baudrate=9600)
    if bill.connect():
        print("âœ“ Bill acceptor connected")
        bill.set_callback(lambda amt: print(f"  Bill update: â‚±{amt}"))
        bill.start_reading()
        print("âœ“ Bill acceptor started")
        print("  Insert a bill for 5 seconds...")
        time.sleep(5)
        amt = bill.get_received_amount()
        print(f"  Received: â‚±{amt}")
        bill.stop_reading()
    else:
        print("âœ— Bill acceptor connection failed")
except Exception as e:
    print(f"âœ— Bill acceptor error: {e}")

# Test 2: Coin Acceptor
print("\n[TEST 2] Coin Acceptor (GPIO)")
print("-" * 60)
try:
    coin = CoinAcceptor(coin_pin=17)
    print(f"âœ“ Coin acceptor initialized on GPIO 17")
    print("  Insert coins for 5 seconds...")
    time.sleep(5)
    amt = coin.get_received_amount()
    print(f"  Received: â‚±{amt}")
except Exception as e:
    print(f"âœ— Coin acceptor error: {e}")

# Test 3: Payment Handler
print("\n[TEST 3] Payment Handler (Combined)")
print("-" * 60)
try:
    config = {
        'hardware': {
            'bill_acceptor': {
                'serial_port': '/dev/ttyUSB0',
                'baudrate': 9600
            }
        },
        'esp32_host': 'serial:/dev/ttyS0'
    }
    
    handler = PaymentHandler(config, coin_port=None)
    print(f"âœ“ Payment handler initialized")
    
    required_amount = 50.0
    handler.start_payment_session(required_amount, on_payment_update=lambda amt: print(f"  Payment update: â‚±{amt}"))
    print(f"  Waiting for â‚±{required_amount}...")
    
    for i in range(10):
        time.sleep(1)
        current = handler.get_current_amount()
        print(f"  [{i+1}s] Received: â‚±{current}")
        if current >= required_amount:
            print("âœ“ Payment complete!")
            break
            
except Exception as e:
    print(f"âœ— Payment handler error: {e}")

print("\n" + "="*60)

