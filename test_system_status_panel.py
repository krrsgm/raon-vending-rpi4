"""
Test script for System Status Panel

Tests the real-time system status display widget.
"""

import tkinter as tk
import time
from system_status_panel import SystemStatusPanel


def test_status_panel():
    """Test the system status panel with simulated updates."""
    
    root = tk.Tk()
    root.title("System Status Panel Test")
    root.geometry("1024x200")
    
    # Create main frame
    main_frame = tk.Frame(root, bg='#f0f4f8')
    main_frame.pack(fill='both', expand=True)
    
    # Add some dummy content at top
    title = tk.Label(main_frame, text="Vending Machine - System Status Display Test", 
                     font=('Helvetica', 16, 'bold'), bg='#f0f4f8')
    title.pack(pady=10)
    
    # Create status panel
    status_panel = SystemStatusPanel(main_frame, controller=None)
    status_panel.pack(fill='x', expand=True)
    
    # Simulate sensor data updates
    def simulate_updates():
        """Simulate real hardware updates."""
        import random
        iteration = 0
        
        while True:
            try:
                iteration += 1
                
                # Simulate DHT22 readings
                if iteration % 3 == 0:  # Update every 3 seconds
                    temp1 = 22.5 + random.uniform(-1, 1)
                    humid1 = 45.0 + random.uniform(-5, 5)
                    temp2 = 23.0 + random.uniform(-1, 1)
                    humid2 = 47.0 + random.uniform(-5, 5)
                    
                    status_panel.update_dht22_reading(1, temp1, humid1)
                    status_panel.update_dht22_reading(2, temp2, humid2)
                
                # Simulate TEC status
                if iteration % 2 == 0:  # Update every 2 seconds
                    current_temp = 20.0 + random.uniform(-2, 5)
                    is_active = current_temp > 12
                    status_panel.update_tec_status(
                        enabled=True,
                        active=is_active,
                        target_temp=10.0,
                        current_temp=current_temp
                    )
                
                # Simulate IR sensor status
                if iteration % 4 == 0:  # Update every 4 seconds
                    s1 = random.choice([True, False, None])
                    s2 = random.choice([True, False, None])
                    status_panel.update_ir_status(
                        sensor_1=s1,
                        sensor_2=s2,
                        detection_mode='any',
                        last_detection=None
                    )
                
                # Simulate health updates
                if iteration % 5 == 0:
                    health = random.choice(['operational', 'warning', 'error'])
                    status_panel.set_system_health(health)
                
                time.sleep(1)
                
            except Exception as e:
                print(f"Update error: {e}")
                time.sleep(1)
    
    # Start simulation in background thread
    import threading
    sim_thread = threading.Thread(target=simulate_updates, daemon=True)
    sim_thread.start()
    
    # Run GUI
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nTest closed")
        root.destroy()


if __name__ == "__main__":
    print("Starting System Status Panel Test...")
    print("Watch the panel update with simulated sensor data")
    print("Press Ctrl+C to exit")
    test_status_panel()
