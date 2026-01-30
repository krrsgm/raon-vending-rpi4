#!/usr/bin/env python3
"""
Test script to verify Arduino Uno communication with Raspberry Pi
Tests both bill acceptor and coin hopper functionality
"""

import serial
import time
import sys
from threading import Thread, Event

class ArduinoCommunicationTest:
    def __init__(self, port='/dev/ttyACM0', baudrate=115200, timeout=1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.is_running = False
        self.stop_event = Event()
        
    def connect(self):
        """Connect to Arduino"""
        try:
            print(f"🔌 Attempting to connect to {self.port} at {self.baudrate} baud...")
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE,
                timeout=self.timeout
            )
            time.sleep(2)  # Wait for Arduino to reset
            print(f"✓ Connected to {self.port}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Arduino"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            print("Disconnected from Arduino")
    
    def read_arduino_startup(self):
        """Read initial Arduino startup messages"""
        print("\n📋 Reading Arduino startup messages...")
        startup_timeout = time.time() + 3
        while time.time() < startup_timeout:
            try:
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    text = data.decode('utf-8', errors='ignore')
                    print(f"  📨 {text.strip()}")
            except Exception as e:
                print(f"  Error: {e}")
            time.sleep(0.1)
    
    def test_bill_acceptor(self):
        """Wait for bill insertion and display amount"""
        print("\n💵 BILL ACCEPTOR TEST")
        print("=" * 50)
        print("Insert a bill into the TB74 bill acceptor...")
        print("(This test will run for 30 seconds)")
        print("=" * 50)
        
        timeout = time.time() + 30
        bills_received = []
        
        while time.time() < timeout:
            try:
                if self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    text = data.decode('utf-8', errors='ignore')
                    for line in text.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        print(f"  📨 {line}")
                        
                        if 'Bill inserted' in line or 'BILL' in line.upper():
                            bills_received.append(line)
                            print(f"  ✓ Bill detected!")
                            
            except Exception as e:
                print(f"  Error: {e}")
            
            time.sleep(0.05)
        
        if bills_received:
            print(f"\n✓ Bill Acceptor: PASS ({len(bills_received)} bill(s) received)")
            return True
        else:
            print(f"\n✗ Bill Acceptor: FAIL (no bills detected)")
            return False
    
    def test_coin_hopper_status(self):
        """Test coin hopper status query"""
        print("\n🪙 COIN HOPPER TEST")
        print("=" * 50)
        print("Sending STATUS command to Arduino...")
        print("=" * 50)
        
        try:
            # Send STATUS command
            self.serial_conn.write(b'STATUS\n')
            self.serial_conn.flush()
            print("  📤 Sent: STATUS")
            
            # Read response
            time.sleep(0.5)
            response = ""
            timeout = time.time() + 2
            while time.time() < timeout and self.serial_conn.in_waiting > 0:
                data = self.serial_conn.read(self.serial_conn.in_waiting)
                response += data.decode('utf-8', errors='ignore')
                time.sleep(0.05)
            
            if response:
                print(f"  📨 Response: {response.strip()}")
                if 'STATUS' in response.upper():
                    print(f"✓ Coin Hopper: PASS (Arduino responded)")
                    return True
                else:
                    print(f"⚠ Coin Hopper: Partial response received")
                    return False
            else:
                print(f"✗ Coin Hopper: FAIL (no response from Arduino)")
                return False
                
        except Exception as e:
            print(f"✗ Coin Hopper: ERROR - {e}")
            return False
    
    def test_coin_hopper_dispense_dry_run(self):
        """Test coin hopper dispense command (motors OFF for safety - dry run)"""
        print("\n🧪 COIN HOPPER DISPENSE DRY RUN")
        print("=" * 50)
        print("Sending DISPENSE_DENOM 1 1 (dispense 1x 1-peso coin)...")
        print("⚠️  Motors should NOT run (just testing communication)")
        print("=" * 50)
        
        try:
            # Send dispense command with 2 second timeout
            self.serial_conn.write(b'DISPENSE_DENOM 1 1 2000\n')
            self.serial_conn.flush()
            print("  📤 Sent: DISPENSE_DENOM 1 1 2000")
            
            # Read response
            time.sleep(0.5)
            response = ""
            timeout = time.time() + 3
            while time.time() < timeout and self.serial_conn.in_waiting > 0:
                data = self.serial_conn.read(self.serial_conn.in_waiting)
                response += data.decode('utf-8', errors='ignore')
                time.sleep(0.05)
            
            if response:
                print(f"  📨 Response: {response.strip()}")
                if 'OK' in response.upper() or 'DONE' in response.upper():
                    print(f"✓ Coin Hopper Dispense: PASS (Arduino responded correctly)")
                    return True
                else:
                    print(f"⚠ Coin Hopper Dispense: Partial response")
                    return False
            else:
                print(f"✗ Coin Hopper Dispense: FAIL (no response)")
                return False
                
        except Exception as e:
            print(f"✗ Coin Hopper Dispense: ERROR - {e}")
            return False
    
    def run_all_tests(self):
        """Run all communication tests"""
        print("\n" + "=" * 60)
        print("🤖 ARDUINO UNO ↔ RASPBERRY PI COMMUNICATION TEST")
        print("=" * 60)
        
        # Connection test
        if not self.connect():
            print("\n❌ Cannot proceed - Arduino not found")
            return False
        
        # Read startup messages
        self.read_arduino_startup()
        
        # Test bill acceptor
        bill_result = self.test_bill_acceptor()
        
        # Test coin hopper status
        status_result = self.test_coin_hopper_status()
        
        # Test coin hopper dispense
        dispense_result = self.test_coin_hopper_dispense_dry_run()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Bill Acceptor:       {'✓ PASS' if bill_result else '✗ FAIL'}")
        print(f"Coin Hopper Status:  {'✓ PASS' if status_result else '✗ FAIL'}")
        print(f"Coin Hopper Dispense:{'✓ PASS' if dispense_result else '✗ FAIL'}")
        
        all_pass = bill_result and status_result and dispense_result
        print("=" * 60)
        
        if all_pass:
            print("✓ All tests PASSED - Arduino communication working!")
        else:
            print("✗ Some tests failed - Check connections")
        
        self.disconnect()
        return all_pass

def find_arduino_port():
    """Find Arduino port on Linux (Raspberry Pi)"""
    import glob
    
    # Try common Arduino USB ports
    possible_ports = [
        '/dev/ttyACM0',
        '/dev/ttyACM1',
        '/dev/ttyUSB0',
        '/dev/ttyUSB1',
    ]
    
    print("🔍 Searching for Arduino port...")
    for port in possible_ports:
        try:
            s = serial.Serial(port, 115200, timeout=0.1)
            s.close()
            print(f"✓ Found Arduino at {port}")
            return port
        except:
            pass
    
    # Try glob pattern as fallback
    ports = glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyUSB*')
    if ports:
        print(f"✓ Found Arduino at {ports[0]}")
        return ports[0]
    
    print("✗ No Arduino found")
    return None

if __name__ == '__main__':
    # Auto-detect port or use argument
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        port = find_arduino_port()
    
    if not port:
        print("❌ Arduino not detected")
        print("Usage: python3 test_arduino_communication.py [/dev/ttyACM0]")
        sys.exit(1)
    
    # Run tests
    tester = ArduinoCommunicationTest(port=port)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)
