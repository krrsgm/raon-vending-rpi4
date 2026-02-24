import tkinter as tk
import time
from kiosk_app import KioskFrame
from selection_screen import SelectionScreen
import json
from admin_screen import AdminScreen
from assign_items_screen import AssignItemsScreen
from item_screen import ItemScreen
from cart_screen import CartScreen
from logs_screen import LogsScreen
from fix_paths import get_absolute_path
from daily_sales_logger import get_logger
import subprocess
import platform
import os
import sys

# Stock Tracker for inventory management
try:
    from stock_tracker import get_tracker
    STOCK_TRACKER_AVAILABLE = True
except ImportError:
    STOCK_TRACKER_AVAILABLE = False
    print("[MainApp] WARNING: stock_tracker not available")

# TEC Controller for Peltier module
try:
    from tec_controller import TECController
    TEC_AVAILABLE = True
except Exception as e:
    TEC_AVAILABLE = False
    print(f"TEC Controller not available: {e}")

# Item Dispense Monitor with IR sensors
try:
    from item_dispense_monitor import ItemDispenseMonitor
    DISPENSE_MONITOR_AVAILABLE = True
except Exception as e:
    DISPENSE_MONITOR_AVAILABLE = False
    print(f"Item Dispense Monitor not available: {e}")


class MainApp(tk.Tk):
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.cart = []
        self.tec_controller = None  # TEC Peltier module controller
        self.dispense_monitor = None  # Item dispense IR sensor monitor

        # Start in fullscreen mode for kiosk display
        self.is_fullscreen = True
        # Set window title
        self.title("RAON Vending Machine")
        
        # Bind Escape globally so it works in all frames
        self.bind_all("<Escape>", self.handle_escape)
        
        # Special handling for Raspberry Pi
        if platform.system() == "Linux":
            # Remove window decorations and go fullscreen on Pi
            self.attributes('-type', 'splash')  # Splash window = no decorations
            self.attributes('-zoomed', '1')      # Fullscreen on Pi
        else:
            # On Windows: use override redirect for fullscreen effect (no decorations)
            self.overrideredirect(True)  # Remove window decorations and title bar
        
        # Load config first
        self.config_path = get_absolute_path("config.json")
        self.config = self.load_config_from_json(self.config_path)
        
        # Load items from assigned_items.json (the primary data source)
        self.assigned_items_path = get_absolute_path("assigned_items.json")
        self.assigned_slots = self.load_items_from_json(self.assigned_items_path)
        
        # For backward compatibility, also populate items array
        # Extract items from assigned slots for display in admin and kiosk
        self.items = self._extract_items_from_slots(self.assigned_slots)
        self.items_file_path = get_absolute_path("item_list.json")  # For legacy support
        self.currency_symbol = self.config.get("currency_symbol", "$")
        self.title("Vending Machine UI")
        # Initialize TEC Controller if enabled in config
        self._init_tec_controller()
        
        # Initialize Item Dispense Monitor if enabled in config
        self._init_dispense_monitor()
        
        # Initialize Stock Tracker for inventory management
        self.stock_tracker = None
        if STOCK_TRACKER_AVAILABLE:
            self._init_stock_tracker()
        
        
        # Apply fullscreen and rotation according to config
        # Apply fullscreen and rotation according to config
        always_fs = bool(self.config.get('always_fullscreen', True))
        allow_admin_deco = bool(self.config.get('allow_decorations_for_admin', False))
        rotate_disp = str(self.config.get('rotate_display', 'right'))

        self._kiosk_config = {
            'always_fullscreen': always_fs,
            'allow_admin_decorations': allow_admin_deco,
            'rotate_display': rotate_disp
        }

        # Do not force fullscreen here; per-page logic in show_frame will
        # apply fullscreen/decoration behavior so the SelectionScreen can
        # show window controls (minimize/maximize) on startup.

        # Attempt display rotation if configured
        def apply_rotation(direction):
            valid = {'normal': 'normal', 'right': 'right', 'left': 'left', 'inverted': 'inverted'}
            d = valid.get(direction, None)
            if not d:
                return
            try:
                if platform.system() == "Linux" and os.getenv("DISPLAY"):
                    # Use xrandr to rotate screen (non-persistent)
                    subprocess.run(["xrandr", "-o", d], check=False)
            except Exception as e:
                print(f"Rotation failed: {e}")

        if rotate_disp:
            # schedule shortly after startup so X is ready
            self.after(300, lambda: apply_rotation(rotate_disp))

        # Bind keys on the root window so they work regardless of focus.
        # F11 is kept as a no-op toggle that re-applies fullscreen state.
        try:
            self.bind("<F11>", self.toggle_fullscreen)
        except Exception:
            pass

        # Bind Escape globally so it works even when the window is undecorated
        # or when focus shifts to child widgets or modal dialogs.
        try:
            self.bind_all("<Escape>", self.handle_escape)
        except Exception:
            pass
        # Attempt to rotate the display 90 degrees to the right (if running under X on Linux).
        # This uses `xrandr -o right` and will only run when a DISPLAY is available.
        try:
            if platform.system() == "Linux" and os.getenv("DISPLAY"):
                # Run after a short delay so X is ready
                self.after(200, lambda: subprocess.run(["xrandr", "-o", "right"]))
        except Exception as e:
            print(f"Display rotation request failed: {e}")

        # The container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (SelectionScreen, KioskFrame, AdminScreen, AssignItemsScreen, ItemScreen, CartScreen, LogsScreen):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            # put all of the pages in the same location;
            # the one on the top of the stacking order
            # will be the one that is visible.
            frame.grid(row=0, column=0, sticky="nsew")

        self.active_frame_name = None
        self.show_frame("SelectionScreen")

    def _init_tec_controller(self):
        """Initialize TEC Peltier module controller if enabled."""
        if not TEC_AVAILABLE:
            return
        
        try:
            hardware_config = self.config.get('hardware', {})
            tec_config = hardware_config.get('tec_relay', {})
            
            if not tec_config.get('enabled', False):
                print("[MainApp] TEC controller disabled in config")
                return
            
            # Get both DHT22 sensor pins
            dht22_config = hardware_config.get('dht22_sensors', {})
            sensor_pins = [
                dht22_config.get('sensor_1', {}).get('gpio_pin', 27),
                dht22_config.get('sensor_2', {}).get('gpio_pin', 22)
            ]
            
            relay_pin = tec_config.get('gpio_pin', 26)
            average_sensors = tec_config.get('average_sensors', True)

            # Prefer explicit temperature range if provided, otherwise fall back
            # to legacy target_temp + hysteresis behavior for backward compatibility.
            target_min = tec_config.get('target_temp_min')
            target_max = tec_config.get('target_temp_max')
            if target_min is None or target_max is None:
                # fallback to legacy single target + hysteresis
                target_temp = tec_config.get('target_temp', None)
                hysteresis = tec_config.get('hysteresis', None)
            else:
                target_temp = None
                hysteresis = None

            humidity_threshold = tec_config.get('humidity_threshold', None)

            self.tec_controller = TECController(
                sensor_pins=sensor_pins,
                relay_pin=relay_pin,
                target_temp=target_temp,
                temp_hysteresis=hysteresis,
                target_temp_min=target_min,
                target_temp_max=target_max,
                humidity_threshold=humidity_threshold,
                average_sensors=average_sensors
            )
            
            # Register status callback for UI panel
            self.tec_controller.set_on_status_update(self._on_tec_status_update)
            # Register per-DHT updates for detailed sensor display
            try:
                self.tec_controller.set_on_dht_update(self._on_dht22_update)
            except Exception:
                pass
            
            self.tec_controller.start()
            print("[MainApp] TEC controller initialized and started")
            
            # Register cleanup on window close
            self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        except Exception as e:
            print(f"[MainApp] Failed to initialize TEC controller: {e}")
            self.tec_controller = None

    def _on_closing(self):
        """Handle window closing event - cleanup TEC controller and dispense monitor."""
        if self.tec_controller:
            self.tec_controller.cleanup()
        if self.dispense_monitor:
            self.dispense_monitor.cleanup()
        self.destroy()

    def _init_dispense_monitor(self):
        """Initialize Item Dispense Monitor with IR sensors if enabled."""
        if not DISPENSE_MONITOR_AVAILABLE:
            return
        
        try:
            hardware_config = self.config.get('hardware', {})
            ir_config = hardware_config.get('ir_sensors', {})
            
            # Get IR sensor pins
            ir_pins = [
                ir_config.get('sensor_1', {}).get('gpio_pin', 6),
                ir_config.get('sensor_2', {}).get('gpio_pin', 5)
            ]
            
            timeout = ir_config.get('dispense_timeout', 10.0)
            detection_mode = ir_config.get('detection_mode', 'any')  # 'any', 'all', or 'first'
            simulate_detection = ir_config.get('simulate_detection', False)  # For testing
            
            self.dispense_monitor = ItemDispenseMonitor(
                ir_sensor_pins=ir_pins,
                default_timeout=timeout,
                detection_mode=detection_mode,
                simulate_detection=simulate_detection
            )
            
            # Register callbacks for UI alerts
            self.dispense_monitor.set_on_dispense_timeout(self._on_dispense_timeout)
            self.dispense_monitor.set_on_item_dispensed(self._on_item_dispensed)
            self.dispense_monitor.set_on_dispense_status(self._on_dispense_status)
            self.dispense_monitor.set_on_ir_status_update(self._on_ir_status_update)
            
            self.dispense_monitor.start_monitoring()
            print("[MainApp] Item Dispense Monitor initialized and started")
        
        except Exception as e:
            print(f"[MainApp] Failed to initialize Dispense Monitor: {e}")
            self.dispense_monitor = None
    
    def _init_stock_tracker(self):
        """Initialize Stock Tracker for inventory management."""
        try:
            web_app_host = self.config.get('web_app_host', 'localhost')
            web_app_port = self.config.get('web_app_port', 5000)
            machine_id = self.config.get('machine_id', 'RAON-001')
            
            self.stock_tracker = get_tracker(
                host=web_app_host,
                port=web_app_port,
                machine_id=machine_id
            )
            print(f"[MainApp] Stock Tracker initialized: {machine_id} -> {web_app_host}:{web_app_port}")
        except Exception as e:
            print(f"[MainApp] Failed to initialize Stock Tracker: {e}")
            self.stock_tracker = None
    
    # MUX4 support removed — device supports only slots 1..48
    
    
    def _on_tec_status_update(self, enabled, active, target_temp, current_temp):
        """Handle TEC controller status updates - update status panel."""
        try:
            # Update all frames that expose a status_panel so UI shows
            # sensor/TEC updates regardless of which view is active.
            for frame in self.frames.values():
                try:
                    if hasattr(frame, 'status_panel') and frame.status_panel:
                        # Schedule widget updates on the main/UI thread
                        try:
                            frame.after(0, lambda f=frame, e=enabled, a=active, t=target_temp, c=current_temp: f.status_panel.update_tec_status(enabled=e, active=a, target_temp=t, current_temp=c))
                        except Exception:
                            # Fallback: direct call if scheduling fails
                            frame.status_panel.update_tec_status(enabled=enabled, active=active, target_temp=target_temp, current_temp=current_temp)
                except Exception:
                    pass
            
            # Log temperature periodically (not on every update to avoid spam)
            try:
                logger = get_logger()
                # Only log if this is a significant change or periodic (checked by logger)
                logger.log_temperature(
                    sensor_1_temp=current_temp,
                    relay_status=active,
                    target_temp=target_temp
                )
            except Exception as e:
                print(f"[MainApp] Error logging temperature: {e}")
        except Exception as e:
            print(f"[MainApp] Error updating TEC status panel: {e}")
    
    def _on_dht22_update(self, sensor_number, temp, humidity):
        """Handle DHT22 sensor updates - update status panel."""
        try:
            # Update all frames that expose a status_panel so UI shows
            # DHT readings regardless of which view is active.
            # Debug: notify console that a DHT22 update was received
            try:
                print(f"[MainApp] DHT22 update: sensor={sensor_number} temp={temp} hum={humidity}")
            except Exception:
                pass

            for frame in self.frames.values():
                try:
                    if hasattr(frame, 'status_panel') and frame.status_panel:
                        try:
                            frame.after(0, lambda f=frame, s=sensor_number, tt=temp, hh=humidity: f.status_panel.update_dht22_reading(sensor_number=s, temp=tt, humidity=hh))
                        except Exception:
                            frame.status_panel.update_dht22_reading(sensor_number=sensor_number, temp=temp, humidity=humidity)
                except Exception:
                    pass
            
            # Log temperature reading (DHT22 updates less frequently)
            try:
                logger = get_logger()
                if sensor_number == 1:
                    logger.log_temperature(sensor_1_temp=temp)
                elif sensor_number == 2:
                    logger.log_temperature(sensor_2_temp=temp)
            except Exception as e:
                pass  # Silently ignore logging errors
        except Exception as e:
            print(f"[MainApp] Error updating DHT22 status panel: {e}")
    
    def _on_ir_status_update(self, sensor_1, sensor_2, detection_mode, last_detection):
        """Handle IR sensor status updates - update status panel."""
        try:
            # Update all frames that expose a status_panel so UI shows
            # IR updates regardless of which view is active.
            for frame in self.frames.values():
                try:
                    if hasattr(frame, 'status_panel') and frame.status_panel:
                        try:
                            frame.after(0, lambda f=frame, s1=sensor_1, s2=sensor_2, dm=detection_mode, ld=last_detection: f.status_panel.update_ir_status(sensor_1=s1, sensor_2=s2, detection_mode=dm, last_detection=ld))
                        except Exception:
                            frame.status_panel.update_ir_status(sensor_1=sensor_1, sensor_2=sensor_2, detection_mode=detection_mode, last_detection=last_detection)
                except Exception:
                    pass
        except Exception as e:
            print(f"[MainApp] Error updating IR status panel: {e}")
    
    def _on_dispense_timeout(self, slot_id, elapsed_time):
        """Handle dispense timeout - show alert dialog."""
        self.show_dispense_alert(
            title="⚠️ DISPENSE ERROR",
            message=f"Item from Slot {slot_id}\nfailed to dispense!\n\nTimeout after {elapsed_time:.1f}s",
            severity="error"
        )
    
    def _on_item_dispensed(self, slot_id, success):
        """Handle successful or failed item dispensing."""
        if success:
            print(f"[MainApp] ✓ Slot {slot_id} dispensed successfully")
        else:
            print(f"[MainApp] ✗ Slot {slot_id} dispense FAILED")
    
    def _on_dispense_status(self, slot_id, status_msg):
        """Handle status messages from dispense monitor."""
        print(f"[MainApp] Slot {slot_id}: {status_msg}")
    
    def show_dispense_alert(self, title, message, severity="warning"):
        """
        Show a dispense alert dialog on the screen.
        
        Args:
            title (str): Alert title
            message (str): Alert message
            severity (str): 'error', 'warning', or 'info'
        """
        from tkinter import messagebox
        
        if severity == "error":
            messagebox.showerror(title, message)
        elif severity == "warning":
            messagebox.showwarning(title, message)
        else:
            messagebox.showinfo(title, message)

    def _extract_items_from_slots(self, assigned_slots):
        """Extract items from assigned slots for display in admin/kiosk screens.
        
        Converts the slot structure (with terms) into a flat list of items.
        Uses the currently selected term (default 0 = Term 1).
        """
        items = []
        try:
            term_idx = getattr(self, 'assigned_term', 0) or 0
            
            if isinstance(assigned_slots, list):
                for slot in assigned_slots:
                    if isinstance(slot, dict) and 'terms' in slot:
                        terms = slot.get('terms', [])
                        if len(terms) > term_idx and terms[term_idx]:
                            items.append(terms[term_idx])
                    elif isinstance(slot, dict) and 'name' in slot:
                        # Legacy format - just add the slot directly
                        items.append(slot)
        except Exception as e:
            print(f"Error extracting items from slots: {e}")
        
        return items

    def load_items_from_json(self, file_path):
        """Loads item data from a JSON file."""
        try:
            with open(file_path, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            print(
                f"Warning: {file_path} not found. Generating a new one with default items."
            )
            default_items = []
            with open(file_path, "w") as file:
                json.dump(default_items, file, indent=4)
            return default_items
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}.")
            return []

    def load_config_from_json(self, file_path):
        """Loads item data from a JSON file."""
        try:
            with open(file_path, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            print(
                f"Warning: {file_path} not found. Generating a new one with default items."
            )
            default_config = {
                "currency_symbol": "$",
                "esp32_host": "serial:/dev/ttyS0"
            }
            with open(file_path, "w") as file:
                json.dump(default_config, file, indent=4)
            return default_config
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}.")
            return []

    def save_items_to_json(self):
        """Saves the current item list to the JSON file."""
        with open(self.items_file_path, "w") as file:
            json.dump(self.items, file, indent=4)

    def toggle_fullscreen(self, event=None):
        """Toggles fullscreen mode for the SelectionScreen."""
        if self.active_frame_name == "SelectionScreen":
            self.is_fullscreen = not self.is_fullscreen
            if self.is_fullscreen:
                self.attributes("-fullscreen", True)
                self.overrideredirect(True)
            else:
                self.attributes("-fullscreen", False)
                self.overrideredirect(False)
                self.state('normal')
                # Set a reasonable default size
                width = min(1024, self.winfo_screenwidth() - 100)
                height = min(768, self.winfo_screenheight() - 100)
                x = (self.winfo_screenwidth() - width) // 2
                y = (self.winfo_screenheight() - height) // 2
                self.geometry(f"{width}x{height}+{x}+{y}")

    def show_frame(self, page_name):
        """Show a frame for the given page name"""
        frame = self.frames[page_name]
        self.active_frame_name = page_name

        # Handle window state differently for Linux/Raspberry Pi
        is_linux = platform.system() == "Linux"

        if page_name == "SelectionScreen":
            try:
                if is_linux:
                    # On Pi: use normal window with decorations
                    self.attributes('-type', 'normal')
                    self.attributes('-zoomed', '0')
                    self.state('normal')
                else:
                    # On Windows: standard window control
                    self.overrideredirect(False)
                    self.attributes("-fullscreen", False)
                
                # Set a reasonable default size
                width = min(1024, self.winfo_screenwidth() - 100)
                height = min(768, self.winfo_screenheight() - 100)
                x = (self.winfo_screenwidth() - width) // 2
                y = (self.winfo_screenheight() - height) // 2
                self.geometry(f"{width}x{height}+{x}+{y}")
            except Exception as e:
                print(f"Error setting window state: {e}")
        else:
            try:
                if is_linux:
                    # On Pi: use splash window type and zoomed state
                    self.attributes('-type', 'splash')
                    self.attributes('-zoomed', '1')
                    # Force fullscreen size
                    self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
                else:
                    # On Windows: use standard fullscreen
                    self.attributes("-fullscreen", True)
                    self.overrideredirect(True)
                    self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
            except Exception as e:
                print(f"Error setting fullscreen: {e}")

        # Raise the frame and ensure it has focus
        frame.tkraise()
        self.update_idletasks()  # Process any pending window manager tasks
        
        # Single focus attempt - avoid potential recursion
        focus_set = False
        for focus_method in [self.focus_force, self.focus_set, frame.focus_set]:
            if not focus_set:
                try:
                    focus_method()
                    focus_set = True
                except Exception:
                    pass

        frame.event_generate("<<ShowFrame>>")
        frame.tkraise()
        # Force focus back to the main window so global bindings (Escape) are received
        if not focus_set:
            try:
                self.focus_force()
            except Exception:
                pass

    def set_kiosk_mode(self, enable: bool):
        """Enable or disable kiosk mode: fullscreen and no window decorations.

        When enabled the window becomes fullscreen and window manager
        decorations (title bar) are removed. When disabled, decorations
        are restored and fullscreen is disabled.
        """
        if enable:
            self.is_fullscreen = True
            # Try to remove window decorations first, then set fullscreen
            try:
                self.overrideredirect(True)
            except Exception:
                pass
            try:
                self.attributes("-fullscreen", True)
            except Exception:
                pass
            # Ensure geometry covers the entire screen
            try:
                self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
            except Exception:
                pass
        else:
            # Restore decorations and exit fullscreen
            try:
                self.attributes("-fullscreen", False)
            except Exception:
                pass
            try:
                self.overrideredirect(False)
            except Exception:
                pass
            # Optionally set a sensible windowed geometry
            try:
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                width = screen_width // 2
                height = screen_height
                x = screen_width // 2
                self.geometry(f"{width}x{height}+{x}+0")
            except Exception:
                pass

    def show_kiosk(self):
        """Show the kiosk interface and reset its state."""
        self.frames["KioskFrame"].reset_state()
        # First update the frame name
        self.active_frame_name = "KioskFrame"
        # Then show the frame (which will make it fullscreen)
        self.show_frame("KioskFrame")
        # Force focus back to main window for key bindings
        self.focus_force()

    def show_item(self, item_data):
        """Passes item data to the ItemScreen and displays it."""
        self.frames["ItemScreen"].set_item(item_data)
        self.show_frame("ItemScreen")

    def show_cart(self):
        """Passes cart data to the CartScreen and displays it."""
        self.frames["CartScreen"].update_cart(self.cart)
        self.show_frame("CartScreen")

    def add_to_cart(self, added_item, quantity):
        """Adds an item and its quantity to the cart."""
        # Check if item is already in cart
        for item_info in self.cart:
            if item_info["item"]["name"] == added_item["name"]:
                item_info["quantity"] += quantity
                return  # Exit after updating

        # If not in cart, add as a new entry
        self.cart.append({"item": added_item, "quantity": quantity})

    def remove_from_cart(self, item_to_remove):
        """Removes an item entirely from the cart and restores its quantity."""
        item_found = None
        for item_info in self.cart:
            if item_info["item"]["name"] == item_to_remove["name"]:
                item_found = item_info
                break

        if item_found:
            self.increase_item_quantity(item_found["item"], item_found["quantity"])
            self.cart.remove(item_found)
            self.show_cart()  # Refresh cart screen

    def increase_cart_item_quantity(self, item_to_increase):
        """Increases an item's quantity in the cart by 1."""
        # First, check if there is available stock
        for master_item in self.items:
            if master_item["name"] == item_to_increase["name"]:
                if master_item["quantity"] > 0:
                    master_item["quantity"] -= 1  # Reduce from master list
                    # Now, increase in cart
                    for cart_item_info in self.cart:
                        if cart_item_info["item"]["name"] == item_to_increase["name"]:
                            cart_item_info["quantity"] += 1
                            self.show_cart()  # Refresh cart screen
                            return

    def decrease_cart_item_quantity(self, item_to_decrease):
        """Decreases an item's quantity in the cart by 1."""
        for item_info in self.cart:
            if item_info["item"]["name"] == item_to_decrease["name"]:
                if item_info["quantity"] > 1:
                    item_info["quantity"] -= 1
                    self.increase_item_quantity(item_to_decrease, 1)
                    self.show_cart()  # Refresh cart screen
                else:  # If quantity is 1, remove it completely
                    self.remove_from_cart(item_to_decrease)
                return

    def clear_cart(self):
        """Empties the cart."""
        self.cart.clear()

    def handle_checkout(self, checked_out_items):
        """
        Processes items at checkout. In a real app, this would handle payment.
        Here, we simulate a potential failure.
        Returns True on success, False on failure.
        """

        # TODO: Replace this simulation with real payment processing logic.
        import random

        # Simulate a 50% chance of checkout failure
        if random.random() < 0.5:
            print("Checkout failed. (Simulated)")
            return False

        print("Checkout successful. Items processed:", checked_out_items)
        self.save_items_to_json()  # Persist the new quantities
        # Attempt to vend physical slots for items that were checked out
        try:
            for it in checked_out_items:
                # support both {'item': {...}, 'quantity': n} and simple dicts
                if isinstance(it, dict) and 'item' in it and 'quantity' in it:
                    item_obj = it['item']
                    qty = int(it['quantity'])
                else:
                    item_obj = it
                    qty = 1
                name = item_obj.get('name') if isinstance(item_obj, dict) else None
                if name:
                    try:
                        self.vend_slots_for(name, qty)
                    except Exception as e:
                        print(f"Vend error for {name}: {e}")
        except Exception:
            pass

        return True

    def reduce_item_quantity(self, item, quantity):
        """Reduces the quantity of the item in the KioskFrame."""
        kiosk_frame = self.frames["KioskFrame"]
        for index in range(len(kiosk_frame.items)):
            kiosk_item = kiosk_frame.items[index]
            if kiosk_item["name"] == item["name"]:
                print(f"Reducing {item['name']} quantity by {quantity}")
                self.items[index]["quantity"] -= quantity

    def increase_item_quantity(self, item, quantity):
        """Increases the quantity of an item in the master item list."""
        for master_item in self.items:
            if master_item["name"] == item["name"]:
                master_item["quantity"] += quantity
                return

    def add_item(self, new_item_data):
        """
        Adds a new item to the master list if the name doesn't already exist.
        Saves to JSON on success. Returns True on success, False on failure.
        """
        new_item_name = new_item_data.get("name", "").strip()
        # Check for existing item with the same name (case-insensitive)
        if any(item.get("name", "").strip().lower() == new_item_name.lower() for item in self.items):
            return False  # Item with this name already exists

        self.items.append(new_item_data)
        self.save_items_to_json()
        # Refresh screens that show items
        self.frames["AdminScreen"].populate_items()
        self.frames["KioskFrame"].populate_items()
        return True

    def vend_slots_for(self, item_name, quantity=1):
        """Find assigned slots for item_name and pulse the ESP32 outputs.

        This function looks at `self.assigned_slots` (populated by AssignItemsScreen)
        and finds all slot indices mapped to `item_name`. It sends PULSE commands
        to the ESP32 host configured under `config['esp32_host']` (fallbacks to
        '192.168.4.1' in AP mode). Pulses are distributed round-robin across
        matching slots.
        
        Also monitors dispensing using IR sensors if dispense monitor is available.
        """
        assigned = getattr(self, 'assigned_slots', None)
        if not assigned:
            print('[VEND] ERROR: No assigned_slots available to vend from')
            return
        # find matching indices (1-based slot numbers)
        matches = []
        for idx, slot in enumerate(assigned):
            if not slot:
                continue

            # Legacy single-slot format: {'name': 'Item Name', ...}
            if isinstance(slot, dict) and slot.get('name'):
                if slot.get('name') == item_name:
                    matches.append(idx+1)
                    continue

            # New 'terms' format: slot contains a list under 'terms' for multiple
            # display terms. Use the currently selected `assigned_term` index
            # (default 0) to pick the active term for comparison.
            if isinstance(slot, dict) and 'terms' in slot:
                terms = slot.get('terms', [])
                term_idx = getattr(self, 'assigned_term', 0) or 0
                if isinstance(terms, list) and len(terms) > term_idx:
                    term_entry = terms[term_idx]
                    if isinstance(term_entry, dict):
                        term_name = term_entry.get('name')
                        if term_name and term_name == item_name:
                            matches.append(idx+1)
                            continue
        if not matches:
            print(f'[VEND] ERROR: No physical slots assigned for item "{item_name}"')
            print(f'[VEND] Available slots: {[s.get("name") if isinstance(s, dict) else None for s in assigned]}')
            return
        host = self.config.get('esp32_host') if isinstance(self.config, dict) else None
        if not host:
            host = '192.168.4.1'  # common AP fallback; set in config for your network
        pulse_ms = 4000  # Motor pulse duration in milliseconds
        
        # Get dispense timeout from config
        dispense_timeout = self.config.get('hardware', {}).get('ir_sensors', {}).get('dispense_timeout', 15.0) if isinstance(self.config, dict) else 15.0
        
        print(f'[VEND] Found {len(matches)} slots for "{item_name}": {matches}')
        print(f'[VEND] Using ESP32 host: {host}, pulse_ms: {pulse_ms}')
        
        # Round-robin distribute pulses
        for i in range(quantity):
            slot_number = matches[i % len(matches)]
            try:
                print(f'[VEND] Pulsing slot {slot_number} for {pulse_ms}ms (item: {item_name}, quantity item {i+1}/{quantity})')
                
                # Start monitoring dispense for this slot if dispense monitor is available
                if self.dispense_monitor:
                    self.dispense_monitor.start_dispense(
                        slot_id=slot_number,
                        timeout=dispense_timeout,
                        item_name=item_name
                    )
                    print(f'[VEND] IR sensor monitoring started for slot {slot_number}, timeout={dispense_timeout}s')
                else:
                    print(f'[VEND] WARNING: Dispense monitor not available - no IR sensor verification')
                
                try:
                    # Check if slot is in MUX4 range (49-64)
                    if 49 <= slot_number <= 64 and self.mux4_controller:
                        # For MUX4 slots, Raspberry Pi controls selectors and SIG
                        print(f'[VEND] MUX4 slot detected - selecting channel + pulsing on Raspberry Pi')
                        self.mux4_controller.pulse_channel(slot_number, pulse_ms)
                        print(f'[VEND] SUCCESS: Pulse sent via MUX4 controller for slot {slot_number}')
                    else:
                        # For slots 1-48, ESP32 controls everything
                        # Mirror test_motor: verify ESP32 reachable via STATUS before pulsing
                        from esp32_client import send_command, pulse_slot
                        try:
                            is_ok = False
                            # quick STATUS check
                            status_resp = send_command(host, "STATUS", timeout=1.0)
                            print(f'[VEND] ESP32 STATUS: {status_resp}')
                            # small settle time before pulsing
                            time.sleep(0.05)
                        except Exception as e:
                            print(f'[VEND] WARNING: ESP32 STATUS check failed: {e}')

                        # Attempt pulse and validate response; retry once on non-OK
                        result = None
                        try:
                            result = pulse_slot(host, slot_number, pulse_ms, timeout=3.0)
                            print(f'[VEND] Pulse response: {result}')
                        except Exception as e:
                            print(f'[VEND] WARNING: pulse_slot raised: {e}')
                        # If response not OK, retry once after a brief pause
                        if not result or "OK" not in str(result).upper():
                            print(f'[VEND] Info: pulse response not OK, retrying once for slot {slot_number}')
                            try:
                                time.sleep(0.05)
                                result = pulse_slot(host, slot_number, pulse_ms, timeout=3.0)
                                print(f'[VEND] Retry pulse response: {result}')
                            except Exception as e:
                                print(f'[VEND] Retry failed: {e}')

                        if result and "OK" in str(result).upper():
                            print(f'[VEND] SUCCESS: Pulse sent to ESP32 for slot {slot_number}, response: {result}')
                        else:
                            print(f'[VEND] ERROR: ESP32 did not confirm pulse for slot {slot_number}. Response: {result}')
                except Exception as e:
                    print(f'[VEND] CRITICAL ERROR: Failed to send pulse for slot {slot_number}: {e}')
                    print(f'[VEND]   Slot: {slot_number}')
                    print(f'[VEND]   Pulse duration: {pulse_ms}ms')
                    import traceback
                    traceback.print_exc()
            except Exception as e:
                print(f'[VEND] CRITICAL ERROR: Exception vending slot {slot_number}: {e}')
                import traceback
                traceback.print_exc()

    def vend_cart_items_organized(self, cart_items):
        """Dispense multiple items organized by slot in ascending order.
        
        This method groups items by their assigned slots and dispenses them slot-by-slot
        in ascending order. For items assigned to the same slot, all are dispensed from
        that slot before moving to the next slot. Each item gets 4 seconds (4000ms) to dispense.
        
        Args:
            cart_items (list): List of dicts with 'item' (item object) and 'quantity' (int)
        """
        if not cart_items:
            print('[VEND-ORG] ERROR: No items to vend')
            return
            
        assigned = getattr(self, 'assigned_slots', None)
        if not assigned:
            print('[VEND-ORG] ERROR: No assigned_slots available to vend from')
            return
        
        # Build a mapping: slot_number -> list of (item_name, quantity) tuples
        slot_to_items = {}
        
        for item_entry in cart_items:
            try:
                item_obj = item_entry.get('item') if isinstance(item_entry, dict) else None
                qty = int(item_entry.get('quantity', 1)) if isinstance(item_entry, dict) else 1
                
                if not item_obj or not item_obj.get('name'):
                    print(f'[VEND-ORG] WARNING: Invalid item entry: {item_entry}')
                    continue
                    
                item_name = item_obj.get('name')
                
                # Find all slots assigned to this item
                item_slots = []
                for idx, slot in enumerate(assigned):
                    if not slot:
                        continue
                    
                    # Legacy single-slot format
                    if isinstance(slot, dict) and slot.get('name'):
                        if slot.get('name') == item_name:
                            item_slots.append(idx + 1)
                            continue
                    
                    # New 'terms' format
                    if isinstance(slot, dict) and 'terms' in slot:
                        terms = slot.get('terms', [])
                        term_idx = getattr(self, 'assigned_term', 0) or 0
                        if isinstance(terms, list) and len(terms) > term_idx:
                            term_entry = terms[term_idx]
                            if isinstance(term_entry, dict):
                                term_name = term_entry.get('name')
                                if term_name and term_name == item_name:
                                    item_slots.append(idx + 1)
                                    continue
                
                if not item_slots:
                    print(f'[VEND-ORG] ERROR: No physical slots assigned for item "{item_name}"')
                    continue
                
                # Add all quantities for this item to its respective slots
                # If item is in multiple slots, distribute quantities round-robin
                for i in range(qty):
                    slot_num = item_slots[i % len(item_slots)]
                    if slot_num not in slot_to_items:
                        slot_to_items[slot_num] = []
                    slot_to_items[slot_num].append({
                        'name': item_name,
                        'count': 1  # Each entry represents 1 dispense
                    })
                    
                print(f'[VEND-ORG] Item "{item_name}" (qty: {qty}) assigned to slots: {item_slots}')
                    
            except Exception as e:
                print(f'[VEND-ORG] ERROR processing item entry: {e}')
                import traceback
                traceback.print_exc()
                continue
        
        if not slot_to_items:
            print('[VEND-ORG] ERROR: No items could be mapped to slots')
            return
        
        # Sort slots in ascending order
        sorted_slots = sorted(slot_to_items.keys())
        print(f'[VEND-ORG] Dispensing from slots in order: {sorted_slots}')
        print(f'[VEND-ORG] Slot-to-items mapping: {slot_to_items}')
        
        host = self.config.get('esp32_host') if isinstance(self.config, dict) else None
        if not host:
            host = '192.168.4.1'
        pulse_ms = 4000  # 4 seconds per item as requested
        
        # Get dispense timeout from config
        dispense_timeout = self.config.get('hardware', {}).get('ir_sensors', {}).get('dispense_timeout', 15.0) if isinstance(self.config, dict) else 15.0
        
        print(f'[VEND-ORG] Using ESP32 host: {host}, pulse_ms: {pulse_ms}')
        
        # Dispense each slot completely before moving to the next
        for slot_number in sorted_slots:
            items_for_slot = slot_to_items[slot_number]
            print(f'[VEND-ORG] Processing slot {slot_number}: {len(items_for_slot)} item(s) to dispense')
            
            for item_entry in items_for_slot:
                item_name = item_entry.get('name', 'Unknown')
                try:
                    print(f'[VEND-ORG] Pulsing slot {slot_number} for {pulse_ms}ms (item: {item_name})')
                    
                    # Start monitoring dispense for this slot if available
                    if self.dispense_monitor:
                        self.dispense_monitor.start_dispense(
                            slot_id=slot_number,
                            timeout=dispense_timeout,
                            item_name=item_name
                        )
                        print(f'[VEND-ORG] IR sensor monitoring started for slot {slot_number}, timeout={dispense_timeout}s')
                    else:
                        print(f'[VEND-ORG] WARNING: Dispense monitor not available - no IR sensor verification')
                    
                    try:
                        # Check if slot is in MUX4 range (49-64)
                        if 49 <= slot_number <= 64 and self.mux4_controller:
                            print(f'[VEND-ORG] MUX4 slot detected - selecting channel + pulsing on Raspberry Pi')
                            self.mux4_controller.pulse_channel(slot_number, pulse_ms)
                            print(f'[VEND-ORG] SUCCESS: Pulse sent via MUX4 controller for slot {slot_number}')
                        else:
                            # For slots 1-48, ESP32 controls everything
                            from esp32_client import send_command, pulse_slot
                            try:
                                # Quick STATUS check
                                status_resp = send_command(host, "STATUS", timeout=1.0)
                                print(f'[VEND-ORG] ESP32 STATUS: {status_resp}')
                                # Small settle time before pulsing
                                time.sleep(0.05)
                            except Exception as e:
                                print(f'[VEND-ORG] WARNING: ESP32 STATUS check failed: {e}')
                            
                            # Attempt pulse and validate response
                            result = None
                            try:
                                result = pulse_slot(host, slot_number, pulse_ms, timeout=3.0)
                                print(f'[VEND-ORG] Pulse response: {result}')
                            except Exception as e:
                                print(f'[VEND-ORG] WARNING: pulse_slot raised: {e}')
                            
                            # Retry if not OK
                            if not result or "OK" not in str(result).upper():
                                print(f'[VEND-ORG] Info: pulse response not OK, retrying once for slot {slot_number}')
                                try:
                                    time.sleep(0.05)
                                    result = pulse_slot(host, slot_number, pulse_ms, timeout=3.0)
                                    print(f'[VEND-ORG] Retry pulse response: {result}')
                                except Exception as e:
                                    print(f'[VEND-ORG] Retry failed: {e}')
                            
                            if result and "OK" in str(result).upper():
                                print(f'[VEND-ORG] SUCCESS: Pulse sent to ESP32 for slot {slot_number}, response: {result}')
                            else:
                                print(f'[VEND-ORG] ERROR: ESP32 did not confirm pulse for slot {slot_number}. Response: {result}')
                    except Exception as e:
                        print(f'[VEND-ORG] CRITICAL ERROR: Failed to send pulse for slot {slot_number}: {e}')
                        import traceback
                        traceback.print_exc()
                        
                except Exception as e:
                    print(f'[VEND-ORG] CRITICAL ERROR: Exception vending slot {slot_number}: {e}')
                    import traceback
                    traceback.print_exc()

    def update_item(self, original_item_name, updated_item_data):
        """Updates an existing item in the master list and saves to JSON."""
        for i, item in enumerate(self.items):
            if item["name"] == original_item_name:
                self.items[i] = updated_item_data
                break
        self.save_items_to_json()
        self.frames["AdminScreen"].populate_items()
        self.frames["KioskFrame"].populate_items()

    def remove_item(self, item_to_remove):
        """Removes an item from the master list and saves to JSON."""
        self.items.remove(item_to_remove)
        self.save_items_to_json()
        self.frames["AdminScreen"].populate_items()

    def show_admin(self):
        self.show_frame("AdminScreen")

    def show_assign_items(self):
        """Show the AssignItemsScreen and ensure it loads the latest slots."""
        frame = self.frames.get("AssignItemsScreen")
        if frame:
            try:
                frame.load_slots()
            except Exception:
                pass
        self.show_frame("AssignItemsScreen")

    def handle_escape(self, event=None):
        """Handle Escape key press for navigation."""
        print(f"Escape pressed in frame: {self.active_frame_name}")  # Debug print
        
        if self.grab_current():
            return

        # From Item/Cart screens, go back to Kiosk
        if self.active_frame_name in ["ItemScreen", "CartScreen"]:
            self.show_kiosk()  # Use show_kiosk instead of show_frame
        # From Admin/AssignItems go back to Selection
        elif self.active_frame_name in ["AdminScreen", "AssignItemsScreen"]:
            self.show_frame("SelectionScreen")
        # From Kiosk go back to Selection
        elif self.active_frame_name in ["KioskFrame"]:
            # Handle window state in show_frame
            self.show_frame("SelectionScreen")
        # Only exit app from SelectionScreen
        elif self.active_frame_name in ["SelectionScreen"]:
            self.destroy()
        else:
            # Safe default - go back to SelectionScreen
            self.show_frame("SelectionScreen")


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()