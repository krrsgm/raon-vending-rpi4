"""IR Sensor Item Detection System

Monitors IR sensors to detect if items are successfully dispensed.
Provides callbacks and timeout alerts when items are not dispensed within expected time.
"""

try:
    import RPi.GPIO as GPIO
except Exception:
    # Not running on Raspberry Pi / RPi.GPIO unavailable — use a local mock
    import rpi_gpio_mock as GPIO

import time
import threading
from threading import Thread, Lock
from queue import Queue


class IRSensor:
    """
    Single IR sensor for item detection.
    
    Detects when an item is present or absent using IR reflection.
    Configured for sensing items in vending slots.
    """
    
    def __init__(self, pin, sensor_name="IR_Sensor"):
        """
        Initialize IR sensor.
        
        Args:
            pin (int): GPIO pin for IR sensor (BCM numbering)
            sensor_name (str): Name/label for this sensor
        """
        self.pin = pin
        self.sensor_name = sensor_name
        self.item_present = False
        self.last_state_change = 0
        self.debounce_time = 0.2  # 200ms debounce
        self._lock = Lock()
        
        # GPIO setup with pull-up resistor (IR sensors default HIGH when no obstruction)
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            print(f"[IRSensor] {sensor_name} initialized on GPIO{pin} with pull-up")
        except Exception as e:
            print(f"[IRSensor] Failed to initialize {sensor_name}: {e}")
    
    def read(self):
        """
        Read current item presence state with debouncing.
        
        Returns:
            bool: True if item detected, False otherwise
        """
        try:
            # Take multiple readings for stability
            readings = []
            for _ in range(3):
                state = GPIO.input(self.pin)
                readings.append(state == GPIO.HIGH)
                time.sleep(0.05)  # Small delay between reads
            
            # Use majority vote for debouncing
            item_present = sum(readings) >= 2
            
            with self._lock:
                self.item_present = item_present
            return self.item_present
        except Exception as e:
            print(f"[IRSensor] Error reading {self.sensor_name}: {e}")
            return None
    
    def is_item_present(self):
        """Check if item is currently present (thread-safe)."""
        with self._lock:
            return self.item_present

class ItemDispenseMonitor:
    """
    Monitors item dispensing using IR sensors positioned at bin catch area.
    
    Detects when items fall into the catch area by monitoring for IR beam obstruction.
    Provides timeout alerts if items are not dispensed within expected time.
    
    IR Sensors with pull-up resistors (typical configuration):
    - HIGH (True) = clear/unobstructed beam (no item present)
    - LOW (False) = blocked/obstructed beam (item blocking sensor)
    
    When an item falls through the catch area, it blocks the IR beam momentarily.
    Success is marked when ANY sensor detects beam obstruction (item falling through).
    """
    
    def __init__(self, ir_sensor_pins=[6, 5], default_timeout=15.0, detection_mode='any', simulate_detection=False):
        """
        Initialize item dispense monitor.
        
        Args:
            ir_sensor_pins (list): GPIO pins for IR sensors (default [GPIO6, GPIO5])
            default_timeout (float): Default timeout in seconds for item dispensing
            detection_mode (str): 'any' (either sensor), 'all' (both sensors), or 'first' (first to detect)
                - 'any': Item is dispensed if ANY sensor detects obstruction (recommended for bin area)
                - 'all': Item is dispensed only if ALL sensors detect obstruction (redundant check)
                - 'first': Item is dispensed when FIRST sensor detects obstruction (fastest detection)
            simulate_detection (bool): If True, simulate successful item detection for testing (no real sensors)
        """
        self.ir_sensor_pins = ir_sensor_pins
        self.default_timeout = default_timeout
        self.detection_mode = detection_mode  # 'any', 'all', or 'first'
        self.simulate_detection = simulate_detection  # For testing without real sensors
        
        # Initialize IR sensors
        self.sensors = {}
        for i, pin in enumerate(ir_sensor_pins):
            sensor_name = f"Bin_IR_{i+1}"
            self.sensors[pin] = IRSensor(pin, sensor_name)
        
        # Monitoring state
        self.running = False
        self.monitor_thread = None
        self._lock = Lock()
        
        # Dispense tracking: slot_id -> {start_time, timeout, callback}
        self.active_dispenses = {}
        self.dispense_queue = Queue()  # For thread-safe dispense requests
        
        # Callbacks
        self._on_item_dispensed = None  # callback(slot_id, success)
        self._on_dispense_timeout = None  # callback(slot_id, elapsed_time)
        self._on_dispense_status = None  # callback(slot_id, status_msg)
        self._on_ir_status_update = None  # callback(sensor_1, sensor_2, detection_mode, last_detection)
        
        print(f"[ItemDispenseMonitor] Initialized with {len(ir_sensor_pins)} IR sensors in bin area")
        print(f"[ItemDispenseMonitor] Detection mode: {detection_mode.upper()}")
        print(f"[ItemDispenseMonitor] Default timeout: {default_timeout}s")
        if simulate_detection:
            print(f"[ItemDispenseMonitor] ⚠️  SIMULATION MODE ENABLED - Items will be marked as dispensed after 1s")
        else:
            print(f"[ItemDispenseMonitor] Using real IR sensor detection")
    
    def start_monitoring(self):
        """Start the item dispense monitoring loop."""
        if not self.running:
            self.running = True
            self.monitor_thread = Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("[ItemDispenseMonitor] Monitoring started")
    
    def stop_monitoring(self):
        """Stop the item dispense monitoring loop."""
        if self.running:
            self.running = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            print("[ItemDispenseMonitor] Monitoring stopped")
    
    def start_dispense(self, slot_id, timeout=None, item_name="Item"):
        """
        Signal start of item dispensing for a slot.
        
        Args:
            slot_id (int): Identifier for the vending slot
            timeout (float, optional): Timeout for this dispense in seconds
            item_name (str): Name of the item being dispensed
        """
        if timeout is None:
            timeout = self.default_timeout
        
        with self._lock:
            self.active_dispenses[slot_id] = {
                'start_time': time.time(),
                'timeout': timeout,
                'item_name': item_name,
                'status': 'DISPENSING'
            }
        
        self._trigger_callback(self._on_dispense_status, 
                              slot_id, f"Dispensing {item_name}... (timeout: {timeout}s)")
        print(f"[ItemDispenseMonitor] Started dispense for slot {slot_id}: {item_name} ({timeout}s timeout)")
    
    def _monitor_loop(self):
        """Main monitoring loop that checks for dispensed items and timeouts."""
        while self.running:
            try:
                current_time = time.time()
                
                with self._lock:
                    slots_to_check = list(self.active_dispenses.keys())
                
                for slot_id in slots_to_check:
                    with self._lock:
                        if slot_id not in self.active_dispenses:
                            continue
                        
                        dispense_info = self.active_dispenses[slot_id]
                        elapsed_time = current_time - dispense_info['start_time']
                        item_name = dispense_info['item_name']
                        timeout = dispense_info['timeout']
                    
                    # In simulate mode, mark as dispensed after 1 second
                    if self.simulate_detection:
                        if elapsed_time >= 1.0:
                            with self._lock:
                                if slot_id in self.active_dispenses:
                                    del self.active_dispenses[slot_id]
                            
                            self._trigger_callback(self._on_item_dispensed, slot_id, True)
                            self._trigger_callback(self._on_dispense_status,
                                                  slot_id, f"✓ {item_name} simulated as dispensed (after {elapsed_time:.1f}s)")
                            print(f"[ItemDispenseMonitor] ✓ Slot {slot_id}: {item_name} simulated as dispensed after {elapsed_time:.1f}s")
                            continue
                    
                    # Read all IR sensors to detect if item has fallen into bin
                    sensor_readings = []
                    for ir_pin in self.ir_sensor_pins:
                        sensor = self.sensors.get(ir_pin)
                        if sensor:
                            item_present = sensor.read()
                            sensor_readings.append((ir_pin, item_present))
                    
                    # Update IR status callback with current sensor state
                    if sensor_readings and self._on_ir_status_update:
                        try:
                            sensor_1 = sensor_readings[0][1] if len(sensor_readings) > 0 else None
                            sensor_2 = sensor_readings[1][1] if len(sensor_readings) > 1 else None
                            self._on_ir_status_update(
                                sensor_1=sensor_1,
                                sensor_2=sensor_2,
                                detection_mode=self.detection_mode,
                                last_detection=None
                            )
                        except Exception as e:
                            print(f"[ItemDispenseMonitor] IR status callback error: {e}")
                    
                    # Check detection based on mode
                    item_detected_absent = self._check_item_detected(sensor_readings)
                    
                    if item_detected_absent:
                        # Item has been successfully detected in the catch area
                        with self._lock:
                            if slot_id in self.active_dispenses:
                                del self.active_dispenses[slot_id]
                        
                        self._trigger_callback(self._on_item_dispensed, slot_id, True)
                        self._trigger_callback(self._on_dispense_status,
                                              slot_id, f"✓ {item_name} detected in catch area!")
                        print(f"[ItemDispenseMonitor] ✓ Slot {slot_id}: {item_name} detected in bin after {elapsed_time:.1f}s")
                        continue
                    
                    # Log sensor status for debugging (True=clear, False=blocked)
                    sensor_status = ", ".join([f"GPIO{pin}={'CLEAR' if present is True else 'BLOCKED' if present is False else 'ERROR'}" 
                                              for pin, present in sensor_readings])
                    
                    # Check for timeout
                    if elapsed_time > timeout:
                        with self._lock:
                            if slot_id in self.active_dispenses:
                                del self.active_dispenses[slot_id]
                        
                        self._trigger_callback(self._on_dispense_timeout, slot_id, elapsed_time)
                        self._trigger_callback(self._on_item_dispensed, slot_id, False)
                        self._trigger_callback(self._on_dispense_status,
                                              slot_id, f"✗ TIMEOUT: {item_name} not detected after {timeout}s! ({sensor_status})")
                        print(f"[ItemDispenseMonitor] ✗ Slot {slot_id}: TIMEOUT - {item_name} not detected after {timeout}s")
                
                time.sleep(0.5)  # Check every 500ms
                
            except Exception as e:
                print(f"[ItemDispenseMonitor] Monitor loop error: {e}")
                time.sleep(0.5)
    
    def _check_item_detected(self, sensor_readings):
        """
        Check if item has been detected based on detection mode.
        
        IR sensors with pull-up resistors:
        - HIGH (True) when no obstruction (beam clear)
        - LOW (False) when item blocks beam
        
        An item falling into the catch area will BLOCK the beam (LOW/False).
        Success is marked when ANY sensor detects item presence (beam blocked).
        
        Args:
            sensor_readings: List of (gpio_pin, item_present) tuples
                where item_present=True means clear, item_present=False means blocked
            
        Returns:
            bool: True if item detected (blocking any sensor), False otherwise
        """
        if not sensor_readings:
            return False
        
        # Filter out None (error) readings
        valid_readings = [(pin, present) for pin, present in sensor_readings if present is not None]
        
        if not valid_readings:
            return False  # All readings are errors
        
        if self.detection_mode == 'any':
            # Item detected if ANY sensor shows obstruction (blocked beam / False)
            # In a bin catch area, item passes through and blocks at least one sensor
            return any(present is False for pin, present in valid_readings)
        
        elif self.detection_mode == 'all':
            # Item detected only if ALL sensors show obstruction (blocked beams)
            return all(present is False for pin, present in valid_readings) and len(valid_readings) > 0
        
        elif self.detection_mode == 'first':
            # Item detected as soon as FIRST sensor shows obstruction (blocked beam)
            return any(present is False for pin, present in valid_readings)
        
        else:
            # Default to 'any' mode
            return any(present is False for pin, present in valid_readings)
    
    def _trigger_callback(self, callback, *args):
        """Safely trigger a callback if registered."""
        if callback:
            try:
                callback(*args)
            except Exception as e:
                print(f"[ItemDispenseMonitor] Callback error: {e}")
    
    def set_on_item_dispensed(self, callback):
        """
        Register callback when item is dispensed.
        
        Args:
            callback: function(slot_id, success) where success is bool
        """
        self._on_item_dispensed = callback
    
    def set_on_dispense_timeout(self, callback):
        """
        Register callback when dispense times out.
        
        Args:
            callback: function(slot_id, elapsed_time_seconds)
        """
        self._on_dispense_timeout = callback
    
    def set_on_dispense_status(self, callback):
        """
        Register callback for status messages.
        
        Args:
            callback: function(slot_id, status_message)
        """
        self._on_dispense_status = callback
    
    def set_on_ir_status_update(self, callback):
        """
        Register callback for IR sensor status updates.
        
        Args:
            callback: function(sensor_1, sensor_2, detection_mode, last_detection)
                     sensor_1/sensor_2: True=present, False=absent, None=unknown
        """
        self._on_ir_status_update = callback
    
    def cancel_dispense(self, slot_id):
        """Cancel active dispense monitoring for a slot."""
        with self._lock:
            if slot_id in self.active_dispenses:
                del self.active_dispenses[slot_id]
        print(f"[ItemDispenseMonitor] Cancelled dispense monitoring for slot {slot_id}")
    
    def get_active_dispenses(self):
        """Get all currently active dispense operations."""
        with self._lock:
            return dict(self.active_dispenses)
    
    def is_dispensing(self, slot_id):
        """Check if a slot is currently being monitored for dispensing."""
        with self._lock:
            return slot_id in self.active_dispenses
    
    def cleanup(self):
        """Clean up resources."""
        self.stop_monitoring()
        try:
            # Cleanup GPIO
            for pin in self.ir_sensor_pins:
                GPIO.cleanup(pin)
            print("[ItemDispenseMonitor] GPIO cleaned up")
        except Exception as e:
            print(f"[ItemDispenseMonitor] Cleanup error: {e}")


def main():
    """Test item dispense monitor."""
    print("=" * 60)
    print("Item Dispense Monitor Test")
    print("=" * 60)
    
    # Create monitor with 2 IR sensors
    monitor = ItemDispenseMonitor(ir_sensor_pins=[6, 5], default_timeout=5.0)
    
    # Register callbacks
    def on_dispensed(slot_id, success):
        status = "SUCCESS" if success else "FAILED"
        print(f"\n>>> DISPENSE {status}: Slot {slot_id}")
    
    def on_timeout(slot_id, elapsed):
        print(f"\n>>> TIMEOUT ALERT: Slot {slot_id} - Item not dispensed after {elapsed:.1f}s!")
    
    def on_status(slot_id, msg):
        print(f"[Slot {slot_id}] {msg}")
    
    monitor.set_on_item_dispensed(on_dispensed)
    monitor.set_on_dispense_timeout(on_timeout)
    monitor.set_on_dispense_status(on_status)
    
    try:
        print("\n[TEST] Starting monitoring...")
        monitor.start_monitoring()
        
        # Simulate dispensing operations
        print("\n[TEST] Simulating dispensing operations...\n")
        
        # Start dispensing slot 1
        monitor.start_dispense(1, timeout=5.0, item_name="Soda Bottle")
        
        # Start dispensing slot 2
        monitor.start_dispense(2, timeout=5.0, item_name="Snack Bag")
        
        print("\n[TEST] Waiting for dispense operations to complete...")
        time.sleep(15)
        
        # Check active dispenses
        active = monitor.get_active_dispenses()
        if active:
            print(f"\n[TEST] Still active: {active}")
        
        print("\n[TEST] ✓ Test completed")
        
    except KeyboardInterrupt:
        print("\n[TEST] Interrupted by user")
    finally:
        print("\n[TEST] Cleaning up...")
        monitor.cleanup()
        print("[TEST] Done")


if __name__ == "__main__":
    main()
