#!/usr/bin/env python3
"""Test script for Item Dispense Monitor.

Tests IR sensor-based item dispensing detection.
"""

import time
from item_dispense_monitor import ItemDispenseMonitor


def test_dispense_monitor():
    """Test item dispense monitor functionality."""
    print("=" * 60)
    print("Item Dispense Monitor Test")
    print("=" * 60)
    
    # Create monitor with 2 IR sensors in bin area
    # detection_mode='any' means either sensor can detect the falling item
    monitor = ItemDispenseMonitor(
        ir_sensor_pins=[6, 5], 
        default_timeout=5.0,
        detection_mode='any'  # Either sensor detecting absence = success
    )
    
    # Track events
    events = []
    
    # Register callbacks
    def on_dispensed(slot_id, success):
        status = "SUCCESS ✓" if success else "FAILED ✗"
        msg = f"DISPENSE {status}: Slot {slot_id}"
        events.append(('dispensed', slot_id, success))
        print(f"\n>>> {msg}")
    
    def on_timeout(slot_id, elapsed):
        msg = f"TIMEOUT ALERT: Slot {slot_id} - Item not dispensed after {elapsed:.1f}s!"
        events.append(('timeout', slot_id, elapsed))
        print(f"\n>>> {msg}")
    
    def on_status(slot_id, msg):
        events.append(('status', slot_id, msg))
        print(f"[Slot {slot_id}] {msg}")
    
    monitor.set_on_item_dispensed(on_dispensed)
    monitor.set_on_dispense_timeout(on_timeout)
    monitor.set_on_dispense_status(on_status)
    
    try:
        print("\n[TEST] Starting monitoring...")
        monitor.start_monitoring()
        print("[TEST] ✓ Monitoring started\n")
        
        # Test 1: Start dispense operations
        print("[TEST] Test 1: Starting dispense operations...")
        monitor.start_dispense(1, timeout=5.0, item_name="Soda Bottle")
        monitor.start_dispense(2, timeout=5.0, item_name="Snack Bag")
        
        # Check active dispenses
        active = monitor.get_active_dispenses()
        print(f"[TEST] Active dispenses: {len(active)}")
        for slot_id in active:
            print(f"      - Slot {slot_id}: {active[slot_id]['item_name']}")
        
        print("\n[TEST] Test 1: Waiting for dispenses (20 seconds)...")
        time.sleep(20)
        
        # Check if any still active
        active = monitor.get_active_dispenses()
        if active:
            print(f"\n[TEST] Still active after timeout: {active}")
        
        # Test 2: Cancel dispense
        print("\n[TEST] Test 2: Cancel dispense test...")
        monitor.start_dispense(1, timeout=10.0, item_name="Candy Bar")
        time.sleep(1)
        
        if monitor.is_dispensing(1):
            print("[TEST] ✓ Slot 1 is being monitored")
            monitor.cancel_dispense(1)
            print("[TEST] ✓ Cancelled dispense for slot 1")
        
        time.sleep(1)
        
        if not monitor.is_dispensing(1):
            print("[TEST] ✓ Slot 1 is no longer monitored")
        
        # Test 3: Multiple simultaneous dispenses
        print("\n[TEST] Test 3: Multiple simultaneous dispenses...")
        for i in range(2, 4):
            monitor.start_dispense(i, timeout=3.0, item_name=f"Item {i}")
        
        print("[TEST] Waiting 10 seconds...")
        time.sleep(10)
        
        # Summary
        print("\n[TEST] Event Summary:")
        print(f"  Total events: {len(events)}")
        dispensed = sum(1 for e in events if e[0] == 'dispensed')
        timeouts = sum(1 for e in events if e[0] == 'timeout')
        status_msgs = sum(1 for e in events if e[0] == 'status')
        print(f"  Dispense events: {dispensed}")
        print(f"  Timeout events: {timeouts}")
        print(f"  Status messages: {status_msgs}")
        
        print("\n[TEST] Detection Mode Information:")
        print("  Configured mode: 'any'")
        print("  - Item detected if EITHER sensor shows absence")
        print("  - Recommended for bin area with multiple sensors")
        print("  - Maximizes coverage of fall bin area")
        
        print("\n[TEST] ✓ All tests completed successfully")
        
    except KeyboardInterrupt:
        print("\n[TEST] Test interrupted by user")
    except Exception as e:
        print(f"\n[TEST] ✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n[TEST] Cleaning up...")
        monitor.cleanup()
        print("[TEST] Done")


if __name__ == "__main__":
    test_dispense_monitor()
