"""TEC (Thermoelectric Cooler) Peltier Module Controller

Controls a TEC Peltier module based on DHT22 temperature readings.
Maintains a target temperature range by enabling/disabling the TEC.
"""

try:
    import RPi.GPIO as GPIO
except Exception:
    # Not running on Raspberry Pi / RPi.GPIO unavailable — use a local mock so the UI can run
    import rpi_gpio_mock as GPIO

import time
import threading
from threading import Thread, Lock
from dht22_handler import DHT22Sensor


class TECController:
    """
    Controls a TEC Peltier module via GPIO relay.
    
    Monitors DHT22 sensors and automatically enables/disables the TEC
    to maintain a target temperature range.
    Can monitor single sensor or average multiple sensors.
    """
    
    def __init__(self, sensor_pins=[27, 22], relay_pin=26, target_temp=10.0, temp_hysteresis=1.0, average_sensors=True):
        """
        Initialize TEC controller.
        
        Args:
            sensor_pins (list): GPIO pins for DHT22 temperature sensors (default [GPIO27, GPIO22])
            relay_pin (int): GPIO pin for TEC relay control (default GPIO26)
            target_temp (float): Target temperature in Celsius (default 10°C)
            temp_hysteresis (float): Temperature range tolerance (default ±1°C)
            average_sensors (bool): If True, average multiple sensor readings; if False, use highest temp
        """
        self.relay_pin = relay_pin
        self.target_temp = target_temp
        self.temp_hysteresis = temp_hysteresis
        self.average_sensors = average_sensors
        
        # Temperature thresholds
        self.temp_on = target_temp + temp_hysteresis  # Turn on if temp exceeds this
        self.temp_off = target_temp - temp_hysteresis  # Turn off if temp falls below this
        
        # Initialize sensors
        self.sensors = [DHT22Sensor(pin=pin) for pin in sensor_pins]
        self.sensor_pins = sensor_pins
        
        # GPIO setup
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.relay_pin, GPIO.OUT, initial=GPIO.LOW)  # TEC off initially
        
        # State tracking
        self.is_enabled = False
        self.current_temp = None
        self.current_humidity = None
        self.sensor_temps = {}  # Track individual sensor temps
        self.sensor_humidities = {}  # Track individual sensor humidities
        self.last_update_time = 0
        self.running = False
        self.control_thread = None
        self._lock = Lock()
        
        # Callbacks for UI updates
        self._on_status_update = None  # Called with (enabled, current_temp, target_temp)
        self._on_dht_update = None  # Called with (sensor_number, temperature, humidity)
        
        sensor_list = ", ".join([f"GPIO{pin}" for pin in sensor_pins])
    def _control_loop(self):
        """Main control loop that monitors temperature and controls TEC."""
        while self.running:
            try:
                # Read temperatures from all DHT22 sensors
                temps = []
                humidities = []
                
                for i, sensor in enumerate(self.sensors):
                    humidity, temperature = sensor.read()
                    pin = self.sensor_pins[i]
                    
                    if temperature is not None:
                        temps.append(temperature)
                        humidities.append(humidity)
                        with self._lock:
                            self.sensor_temps[pin] = temperature
                            self.sensor_humidities[pin] = humidity
                
                # Calculate control temperature based on mode
                if temps:
                    if self.average_sensors:
                        control_temp = sum(temps) / len(temps)
                        humidity_avg = sum(humidities) / len(humidities) if humidities else None
                    else:
                        # Use highest temperature (most conservative for cooling)
                        control_temp = max(temps)
                        humidity_avg = max(humidities) if humidities else None
                    
                    with self._lock:
                        self.current_temp = control_temp
                        self.current_humidity = humidity_avg
                        self.last_update_time = time.time()
                    
                    # Call status callback if registered
                    if self._on_status_update:
                        try:
                            self._on_status_update(
                                enabled=self.is_enabled,
                                active=self.is_enabled,
                                target_temp=self.target_temp,
                                current_temp=control_temp
                            )
                        except Exception as e:
                            print(f"[TECController] Callback error: {e}")

                # After updating aggregated status, notify per-sensor readings if callback is set
                try:
                    if self._on_dht_update:
                        # Notify for each sensor with its latest reading
                        for idx, pin in enumerate(self.sensor_pins):
                            temp = None
                            humid = None
                            with self._lock:
                                temp = self.sensor_temps.get(pin)
                                humid = self.sensor_humidities.get(pin)
                            try:
                                # sensor_number: 1-based index
                                self._on_dht_update(idx+1, temp, humid)
                            except Exception:
                                pass
                except Exception:
                    pass
                    
                    # Control logic: Hysteresis-based on/off control
                    with self._lock:
                        if self.is_enabled:
                            # TEC is on - turn off if temp falls below threshold
                            if control_temp < self.temp_off:
                                self._tec_off()
                                print(f"[TECController] TEC OFF: Temp {control_temp:.1f}°C ≤ {self.temp_off}°C")
                        else:
                            # TEC is off - turn on if temp exceeds threshold
                            if control_temp > self.temp_on:
                                self._tec_on()
                                print(f"[TECController] TEC ON: Temp {control_temp:.1f}°C ≥ {self.temp_on}°C")
                
                # Update interval (2 second minimum for DHT22)
                time.sleep(2)
                
            except Exception as e:
                print(f"[TECController] Control loop error: {e}")
                time.sleep(2)
    
    def _tec_on(self):
        """Turn on TEC Peltier module."""
        if not self.is_enabled:
            GPIO.output(self.relay_pin, GPIO.HIGH)
            self.is_enabled = True
    
    def _tec_off(self):
        """Turn off TEC Peltier module."""
        if self.is_enabled:
            GPIO.output(self.relay_pin, GPIO.LOW)
            self.is_enabled = False
    
    def start(self):
        """Start the TEC control loop in a background thread."""
        if not self.running:
            self.running = True
            self.control_thread = Thread(target=self._control_loop, daemon=True)
            self.control_thread.start()
            print("[TECController] Control loop started")
    
    def stop(self):
        """Stop the TEC control loop and turn off TEC."""
        if self.running:
            self.running = False
            self._tec_off()
    
    def set_on_status_update(self, callback):
        """
        Set callback for TEC status updates.
        
        Args:
            callback: Function called with (enabled, active, target_temp, current_temp)
        """
        self._on_status_update = callback

    def set_on_dht_update(self, callback):
        """
        Set callback for individual DHT22 sensor updates.

        Args:
            callback: Function called with (sensor_number, temperature, humidity)
        """
        self._on_dht_update = callback
    
    def get_status(self):
        """Get current TEC status."""
        with self._lock:
            return {
                'enabled': self.is_enabled,
                'current_temp': self.current_temp,
                'current_humidity': self.current_humidity,
                'sensor_temps': dict(self.sensor_temps),
                'sensor_humidities': dict(self.sensor_humidities),
                'target_temp': self.target_temp,
                'hysteresis': self.temp_hysteresis,
                'temp_on_threshold': self.temp_on,
                'temp_off_threshold': self.temp_off,
                'last_update': self.last_update_time,
                'average_sensors': self.average_sensors
            }
    
    def set_hysteresis(self, hysteresis):
        """Update the temperature hysteresis."""
        with self._lock:
            self.temp_hysteresis = hysteresis
            self.temp_on = self.target_temp + hysteresis
            self.temp_off = self.target_temp - hysteresis
            print(f"[TECController] Hysteresis updated to ±{hysteresis}°C")
    
    def manual_on(self):
        """Manually turn on TEC (overrides automatic control)."""
        self._tec_on()
        print("[TECController] TEC manually turned ON")
    
    def manual_off(self):
        """Manually turn off TEC (overrides automatic control)."""
        self._tec_off()
        print("[TECController] TEC manually turned OFF")
    
    def cleanup(self):
        """Clean up GPIO and stop control loop."""
        self.stop()
        try:
            GPIO.cleanup(self.relay_pin)
            print("[TECController] GPIO cleaned up")
        except Exception as e:
            print(f"[TECController] Cleanup error: {e}")


def main():
    """Test TEC controller."""
    # Create TEC controller with 2 DHT22 sensors
    # Target: 10°C (freezing point)
    # Hysteresis: ±1°C (activates between 9-11°C)
    # Average both sensor readings for robust control
    tec = TECController(
        sensor_pins=[27, 22],  # GPIO27 Sensor 1, GPIO22 Sensor 2
        relay_pin=26,
        target_temp=10.0,
        temp_hysteresis=1.0,
        average_sensors=True  # Use average of both sensors
    )
    
    try:
        tec.start()
        
        # Display status every 5 seconds
        while True:
            time.sleep(5)
            status = tec.get_status()
            print(f"\nTEC Status:")
            print(f"  Enabled: {status['enabled']}")
            print(f"  Current Temp: {status['current_temp']:.1f}°C" if status['current_temp'] else "  Current Temp: N/A")
            print(f"  Current Humidity: {status['current_humidity']:.1f}%" if status['current_humidity'] else "  Current Humidity: N/A")
            print(f"  Target: {status['target_temp']}°C")
            print(f"  Operating Range: {status['temp_off_threshold']:.1f}°C - {status['temp_on_threshold']:.1f}°C")
    
    except KeyboardInterrupt:
        print("\n[TECController] Shutting down...")
    finally:
        tec.cleanup()


if __name__ == "__main__":
    main()
