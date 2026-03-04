import tkinter as tk
import time
import threading
from kiosk_app import KioskFrame
from selection_screen import SelectionScreen
from start_order_screen import StartOrderScreen
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
from arduino_serial_utils import detect_arduino_serial_port
try:
    from sensor_data_logger import get_sensor_logger
except Exception:
    get_sensor_logger = None

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

try:
    from dht22_handler import get_shared_serial_reader
except Exception:
    get_shared_serial_reader = None


class MainApp(tk.Tk):
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.cart = []
        self.tec_controller = None  # TEC Peltier module controller
        self.dispense_monitor = None  # Item dispense IR sensor monitor
        self._arduino_reader = None
        self._arduino_sensor_bridge_running = False
        self._arduino_sensor_bridge_thread = None
        self._sensor_data_logger = None
        self._sensor_log_interval_seconds = 15 * 60
        self._next_sensor_snapshot_log_ts = 0.0
        self._sensor_snapshot_lock = threading.Lock()
        self._latest_sensor_snapshot = {
            "sensor1_temp": None,
            "sensor1_humidity": None,
            "sensor2_temp": None,
            "sensor2_humidity": None,
            "ir_sensor1_detection": None,
            "ir_sensor2_detection": None,
            "relay_status": None,
            "target_temp": None,
        }
        self._vend_lock = threading.Lock()  # Ensure only one motor pulse at a time
        self._dispense_track_lock = threading.Lock()
        self._pending_dispense_by_slot = {}  # slot_id -> [item_name, ...]
        self._order_start_ts = None  # Transaction timer start (epoch seconds)

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
        self.currency_symbol = self._normalize_currency_symbol(
            self.config.get("currency_symbol", "\u20b1")
        )
        self.title("Vending Machine UI")
        # Initialize TEC/Dispense/Stock after first paint to reduce startup lag
        self.stock_tracker = None
        try:
            self.after(50, self._init_tec_controller)
        except Exception:
            self._init_tec_controller()
        try:
            self.after(75, self._init_dispense_monitor)
        except Exception:
            self._init_dispense_monitor()
        if STOCK_TRACKER_AVAILABLE:
            try:
                self.after(100, self._init_stock_tracker)
            except Exception:
                self._init_stock_tracker()
        try:
            self.after(120, self._init_arduino_sensor_bridge)
        except Exception:
            self._init_arduino_sensor_bridge()
        
        
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
        # The container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (SelectionScreen, StartOrderScreen, KioskFrame, AdminScreen, AssignItemsScreen, ItemScreen, CartScreen, LogsScreen):
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
            use_esp32_dht = dht22_config.get('use_esp32_serial', True)
            esp32_dht_port = dht22_config.get('esp32_port')
            esp32_dht_baud = dht22_config.get('esp32_baud', 115200)
            tec_via_arduino = tec_config.get('control_via_arduino', True)

            if tec_via_arduino:
                print("[MainApp] TEC control is delegated to Arduino; skipping local TECController init")
                return
            
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
                average_sensors=average_sensors,
                use_esp32_serial=use_esp32_dht,
                esp32_port=esp32_dht_port,
                esp32_baud=esp32_dht_baud
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
        self._arduino_sensor_bridge_running = False
        if self.tec_controller:
            self.tec_controller.cleanup()
        if self.dispense_monitor:
            self.dispense_monitor.cleanup()
        self.destroy()

    def _init_arduino_sensor_bridge(self):
        """Start a lightweight bridge that feeds DHT/IR/TEC status from Arduino serial into status panels."""
        if get_shared_serial_reader is None:
            return
        if self._arduino_sensor_bridge_running:
            return

        try:
            hardware = self.config.get('hardware', {}) if isinstance(self.config, dict) else {}
            tec_cfg = hardware.get('tec_relay', {})
            dht_cfg = hardware.get('dht22_sensors', {})
            ir_cfg = hardware.get('ir_sensors', {})
            bill_cfg = hardware.get('bill_acceptor', {})

            tec_via_arduino = tec_cfg.get('control_via_arduino', True)
            dht_via_serial = dht_cfg.get('use_esp32_serial', True)
            ir_via_serial = ir_cfg.get('use_esp32_serial', True)
            if not (tec_via_arduino or dht_via_serial or ir_via_serial):
                return

            serial_port = (
                dht_cfg.get('esp32_port')
                or ir_cfg.get('esp32_port')
                or bill_cfg.get('serial_port')
            )
            serial_port = detect_arduino_serial_port(preferred_port=serial_port)
            serial_baud = int(
                dht_cfg.get('esp32_baud')
                or ir_cfg.get('esp32_baud')
                or bill_cfg.get('baudrate')
                or 115200
            )

            sensor_log_cfg = hardware.get('sensor_logging', {})
            interval_minutes = sensor_log_cfg.get('dashboard_interval_minutes')
            if interval_minutes is None:
                interval_minutes = sensor_log_cfg.get('interval_minutes', 15)
            try:
                interval_minutes = float(interval_minutes)
            except Exception:
                interval_minutes = 15.0
            self._sensor_log_interval_seconds = max(60.0, interval_minutes * 60.0)
            self._next_sensor_snapshot_log_ts = 0.0
            self._sensor_data_logger = None
            self._ensure_sensor_data_logger()

            self._arduino_reader = get_shared_serial_reader(serial_port, serial_baud)
            if not self._arduino_reader:
                print(f"[MainApp] Arduino sensor bridge: no serial reader on {serial_port}")
                return

            self._arduino_sensor_bridge_running = True
            self._arduino_sensor_bridge_thread = threading.Thread(
                target=self._arduino_sensor_bridge_loop,
                daemon=True
            )
            self._arduino_sensor_bridge_thread.start()
            print(f"[MainApp] Arduino sensor bridge started on {serial_port} @ {serial_baud}")
            print(f"[MainApp] Dashboard sensor snapshots every {int(self._sensor_log_interval_seconds // 60)} minute(s)")
        except Exception as e:
            print(f"[MainApp] Arduino sensor bridge init failed: {e}")

    def _resolve_config_target_temp(self):
        """Resolve TEC target temperature from config, if set."""
        try:
            tec_cfg = (
                self.config.get('hardware', {}).get('tec_relay', {})
                if isinstance(self.config, dict) else {}
            )
            target_temp = tec_cfg.get('target_temp')
            if target_temp is not None:
                return float(target_temp)

            tmin = tec_cfg.get('target_temp_min')
            tmax = tec_cfg.get('target_temp_max')
            if tmin is not None and tmax is not None:
                return (float(tmin) + float(tmax)) / 2.0
        except Exception:
            pass
        return None

    def _ensure_sensor_data_logger(self):
        """Initialize sensor logger lazily so both bridge and transaction paths can use it."""
        if self._sensor_data_logger is not None:
            return self._sensor_data_logger
        try:
            if get_sensor_logger:
                self._sensor_data_logger = get_sensor_logger(logs_dir=get_absolute_path("logs"))
        except Exception as e:
            print(f"[MainApp] Sensor logger init failed: {e}")
        return self._sensor_data_logger

    def _update_latest_sensor_snapshot(self, **updates):
        """Update cached latest sensor readings used for periodic CSV snapshots."""
        try:
            with self._sensor_snapshot_lock:
                for key, value in updates.items():
                    if key in self._latest_sensor_snapshot and value is not None:
                        self._latest_sensor_snapshot[key] = value
        except Exception:
            pass

    def _log_sensor_snapshot_if_due(self):
        """Persist temp/humidity/TEC snapshot for dashboard graphing at configured interval."""
        if not self._ensure_sensor_data_logger():
            return

        now = time.time()
        if now < self._next_sensor_snapshot_log_ts:
            return

        snapshot = None
        try:
            with self._sensor_snapshot_lock:
                snapshot = dict(self._latest_sensor_snapshot)
        except Exception:
            snapshot = None

        if not snapshot:
            return

        has_payload = any(snapshot.get(k) is not None for k in (
            "sensor1_temp",
            "sensor1_humidity",
            "sensor2_temp",
            "sensor2_humidity",
            "relay_status",
        ))
        if not has_payload:
            return

        try:
            self._sensor_data_logger.log_sensor_reading(
                sensor1_temp=snapshot.get("sensor1_temp"),
                sensor1_humidity=snapshot.get("sensor1_humidity"),
                sensor2_temp=snapshot.get("sensor2_temp"),
                sensor2_humidity=snapshot.get("sensor2_humidity"),
                relay_status=snapshot.get("relay_status"),
                target_temp=snapshot.get("target_temp"),
            )
            self._next_sensor_snapshot_log_ts = now + self._sensor_log_interval_seconds
        except Exception as e:
            print(f"[MainApp] Sensor snapshot log error: {e}")

    def _log_ir_transaction_snapshot(self):
        """Persist IR reading only when a dispense transaction callback occurs."""
        if not self._ensure_sensor_data_logger():
            return

        snapshot = None
        try:
            with self._sensor_snapshot_lock:
                snapshot = dict(self._latest_sensor_snapshot)
        except Exception:
            snapshot = None
        if not snapshot:
            return

        try:
            self._sensor_data_logger.log_sensor_reading(
                sensor1_temp=snapshot.get("sensor1_temp"),
                sensor1_humidity=snapshot.get("sensor1_humidity"),
                sensor2_temp=snapshot.get("sensor2_temp"),
                sensor2_humidity=snapshot.get("sensor2_humidity"),
                ir_sensor1_detection=snapshot.get("ir_sensor1_detection"),
                ir_sensor2_detection=snapshot.get("ir_sensor2_detection"),
                relay_status=snapshot.get("relay_status"),
                target_temp=snapshot.get("target_temp"),
            )
        except Exception as e:
            print(f"[MainApp] IR transaction snapshot log error: {e}")

    def _arduino_sensor_bridge_loop(self):
        """Poll shared serial reader and push updates to all status panels."""
        while self._arduino_sensor_bridge_running:
            try:
                if not self._arduino_reader:
                    time.sleep(1)
                    continue

                h1, t1 = self._arduino_reader.get_reading("DHT1")
                h2, t2 = self._arduino_reader.get_reading("DHT2")
                if t1 is not None or h1 is not None:
                    self._update_latest_sensor_snapshot(sensor1_temp=t1, sensor1_humidity=h1)
                    self._on_dht22_update(1, t1, h1)
                if t2 is not None or h2 is not None:
                    self._update_latest_sensor_snapshot(sensor2_temp=t2, sensor2_humidity=h2)
                    self._on_dht22_update(2, t2, h2)

                ir1 = self._arduino_reader.get_ir_state("IR1")
                ir2 = self._arduino_reader.get_ir_state("IR2")
                if ir1 is not None or ir2 is not None:
                    self._update_latest_sensor_snapshot(
                        ir_sensor1_detection=ir1,
                        ir_sensor2_detection=ir2
                    )
                    mode = (
                        self.config.get('hardware', {})
                        .get('ir_sensors', {})
                        .get('detection_mode', 'any')
                        if isinstance(self.config, dict) else 'any'
                    )
                    self._on_ir_status_update(ir1, ir2, mode, None)

                tec_active = self._arduino_reader.get_tec_active()
                if tec_active is not None:
                    target_temp = self._resolve_config_target_temp()
                    self._update_latest_sensor_snapshot(
                        relay_status=bool(tec_active),
                        target_temp=target_temp
                    )

                    current_vals = [v for v in (t1, t2) if v is not None]
                    current_temp = (sum(current_vals) / len(current_vals)) if current_vals else None
                    self._on_tec_status_update(
                        enabled=True,
                        active=bool(tec_active),
                        target_temp=target_temp,
                        current_temp=current_temp
                    )

                # Persist dashboard graph snapshots from live Arduino readings.
                self._log_sensor_snapshot_if_due()
            except Exception:
                pass
            time.sleep(1)

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
            use_esp32_ir = ir_config.get('use_esp32_serial', True)
            serial_port = ir_config.get('esp32_port') or hardware_config.get('bill_acceptor', {}).get('serial_port')
            serial_port = detect_arduino_serial_port(preferred_port=serial_port)
            serial_baud = ir_config.get('esp32_baud', 115200)
            
            self.dispense_monitor = ItemDispenseMonitor(
                ir_sensor_pins=ir_pins,
                default_timeout=timeout,
                detection_mode=detection_mode,
                simulate_detection=simulate_detection,
                use_esp32_serial=use_esp32_ir,
                serial_port=serial_port,
                serial_baud=serial_baud
            )
            
            # Register callbacks for UI alerts
            self.dispense_monitor.set_on_dispense_timeout(self._on_dispense_timeout)
            self.dispense_monitor.set_on_item_dispensed(self._on_item_dispensed)
            self.dispense_monitor.set_on_dispense_status(self._on_dispense_status)
            self.dispense_monitor.set_on_ir_status_update(self._on_ir_status_update)
            
            self.dispense_monitor.start_monitoring()
            print(f"[MainApp] Item Dispense Monitor initialized and started (serial={serial_port}, baud={serial_baud})")
        
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
    
        # Device uses ESP32-controlled MUX boards for slots 1..40
    
    
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
            self._update_latest_sensor_snapshot(
                ir_sensor1_detection=sensor_1,
                ir_sensor2_detection=sensor_2
            )
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

    def _track_pending_dispense(self, slot_id, item_name):
        """Track expected dispense events so callbacks can log item-level outcomes."""
        try:
            with self._dispense_track_lock:
                queue = self._pending_dispense_by_slot.setdefault(int(slot_id), [])
                queue.append(str(item_name or "Unknown Item"))
        except Exception:
            pass

    def _consume_pending_dispense(self, slot_id):
        """Pop oldest pending item for a slot, if present."""
        try:
            sid = int(slot_id)
            with self._dispense_track_lock:
                queue = self._pending_dispense_by_slot.get(sid, [])
                if queue:
                    item_name = queue.pop(0)
                    if not queue:
                        self._pending_dispense_by_slot.pop(sid, None)
                    return item_name
        except Exception:
            pass
        return "Unknown Item"
    
    def _on_dispense_timeout(self, slot_id, elapsed_time):
        """Handle dispense timeout - show alert dialog."""
        self.show_dispense_alert(
            title="⚠️ DISPENSE ERROR",
            message=f"Item from Slot {slot_id}\nfailed to dispense!\n\nTimeout after {elapsed_time:.1f}s",
            severity="error"
        )
    
    def _on_item_dispensed(self, slot_id, success):
        """Handle successful or failed item dispensing."""
        item_name = self._consume_pending_dispense(slot_id)
        # IR data is intentionally logged only on dispense callbacks.
        self._log_ir_transaction_snapshot()
        if success:
            print(f"[MainApp] ✓ Slot {slot_id} dispensed successfully")
            try:
                logger = get_logger()
                logger.log_event(
                    "DISPENSE",
                    f"DISPENSE_RESULT | Slot: {slot_id} | Item: {item_name} | Status: SUCCESS"
                )
            except Exception:
                pass
        else:
            print(f"[MainApp] ✗ Slot {slot_id} dispense FAILED")
            try:
                logger = get_logger()
                logger.log_event(
                    "DISPENSE",
                    f"DISPENSE_RESULT | Slot: {slot_id} | Item: {item_name} | Status: FAILED"
                )
            except Exception:
                pass
    
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
                for idx, slot in enumerate(assigned_slots):
                    if isinstance(slot, dict) and 'terms' in slot:
                        terms = slot.get('terms', [])
                        if len(terms) > term_idx and terms[term_idx]:
                            term_item = dict(terms[term_idx])
                            term_item['_slot_number'] = idx + 1
                            items.append(term_item)
                    elif isinstance(slot, dict) and 'name' in slot:
                        # Legacy format - just add the slot directly
                        slot_item = dict(slot)
                        slot_item['_slot_number'] = idx + 1
                        items.append(slot_item)
        except Exception as e:
            print(f"Error extracting items from slots: {e}")
        
        return items

    def load_items_from_json(self, file_path):
        """Loads item data from a JSON file."""
        try:
            # Use utf-8-sig so files with UTF-8 BOM still parse correctly.
            with open(file_path, "r", encoding="utf-8-sig") as file:
                data = json.load(file)
            # Clamp assigned_items.json to 40 slots if older data exists
            try:
                if isinstance(data, list) and os.path.basename(file_path) == "assigned_items.json":
                    if len(data) > 40:
                        data = data[:40]
                    elif len(data) < 40:
                        data = data + [None] * (40 - len(data))
            except Exception:
                pass
            return data
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
            # Use utf-8-sig so files with UTF-8 BOM still parse correctly.
            with open(file_path, "r", encoding="utf-8-sig") as file:
                return json.load(file)
        except FileNotFoundError:
            print(
                f"Warning: {file_path} not found. Generating a new one with default items."
            )
            default_config = {
                "currency_symbol": "\u20b1",
                "esp32_host": "serial:/dev/ttyS0"
            }
            with open(file_path, "w") as file:
                json.dump(default_config, file, indent=4)
            return default_config
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}.")
            return []

    def _normalize_currency_symbol(self, value):
        """Normalize configured currency symbol for consistent kiosk display."""
        symbol = str(value or "").strip()
        if not symbol:
            return "\u20b1"
        # Normalize common misconfigurations back to peso.
        if symbol in {"$", "US$", "USD", "PHP", "Php", "php"}:
            return "\u20b1"

        # Attempt to repair mojibake sequences back to peso.
        repaired = symbol
        for _ in range(2):
            try:
                candidate = repaired.encode("cp1252").decode("utf-8")
            except Exception:
                break
            if candidate == repaired:
                break
            repaired = candidate
        if repaired == "\u20b1":
            return "\u20b1"

        return symbol

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
        always_fullscreen = bool(self._kiosk_config.get('always_fullscreen', True))

        if page_name == "SelectionScreen" and not always_fullscreen:
            try:
                if is_linux:
                    # On Pi (windowed mode): use normal window with decorations
                    self.attributes("-fullscreen", False)
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
                    # On Pi: force kiosk fullscreen with no decorations
                    self.attributes("-fullscreen", True)
                    self.attributes('-type', 'splash')
                    self.attributes('-zoomed', '1')
                    # Force fullscreen geometry
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

    def show_start_order(self):
        """Show kiosk landing/start screen."""
        self.show_frame("StartOrderScreen")
        self.focus_force()

    def start_order(self):
        """Start a new order session and open kiosk menu."""
        self._order_start_ts = time.time()
        try:
            self.clear_cart()
        except Exception:
            pass
        self.show_kiosk()

    def finish_order_timer(self, status="SUCCESS"):
        """Stop transaction timer and log duration in daily log file."""
        start_ts = self._order_start_ts
        self._order_start_ts = None
        if not start_ts:
            return None
        try:
            duration_sec = max(0.0, float(time.time() - float(start_ts)))
        except Exception:
            return None
        try:
            logger = get_logger()
            logger.log_transaction_time(duration_sec, status=status)
        except Exception as e:
            print(f"[MainApp] Failed to log transaction time: {e}")
        return duration_sec

    def show_item(self, item_data):
        """Passes item data to the ItemScreen and displays it."""
        self.frames["ItemScreen"].set_item(item_data)
        self.show_frame("ItemScreen")

    def show_cart(self):
        """Passes cart data to the CartScreen and displays it."""
        self.frames["CartScreen"].update_cart(self.cart)
        self.show_frame("CartScreen")

    def _item_slot_number(self, item_obj):
        """Return integer slot number for an item payload, if available."""
        try:
            slot_num = item_obj.get("_slot_number")
            if slot_num is None:
                return None
            slot_int = int(slot_num)
            return slot_int if slot_int > 0 else None
        except Exception:
            return None

    def _cart_item_key(self, item_obj):
        """Build a cart identity key using item name + tray/slot number."""
        name = ""
        try:
            name = str(item_obj.get("name", "")).strip()
        except Exception:
            name = ""
        return (name, self._item_slot_number(item_obj))

    def add_to_cart(self, added_item, quantity):
        """Adds an item and its quantity to the cart."""
        # Enforce available stock (do not decrement until payment completes)
        try:
            available = int(added_item.get("quantity", 0))
        except Exception:
            available = 0
        current_in_cart = 0
        added_key = self._cart_item_key(added_item)
        for item_info in self.cart:
            if self._cart_item_key(item_info["item"]) == added_key:
                current_in_cart = item_info["quantity"]
                break
        if available <= current_in_cart:
            return
        # Clamp requested quantity to remaining availability
        if quantity + current_in_cart > available:
            quantity = max(0, available - current_in_cart)
        if quantity <= 0:
            return
        # Check if item is already in cart
        for item_info in self.cart:
            if self._cart_item_key(item_info["item"]) == added_key:
                item_info["quantity"] += quantity
                return  # Exit after updating

        # If not in cart, add as a new entry
        self.cart.append({"item": added_item, "quantity": quantity})

    def remove_from_cart(self, item_to_remove):
        """Removes an item entirely from the cart and restores its quantity."""
        item_found = None
        target_key = self._cart_item_key(item_to_remove)
        for item_info in self.cart:
            if self._cart_item_key(item_info["item"]) == target_key:
                item_found = item_info
                break

        if item_found:
            self.cart.remove(item_found)
            self.show_cart()  # Refresh cart screen

    def increase_cart_item_quantity(self, item_to_increase):
        """Increases an item's quantity in the cart by 1."""
        # Enforce available stock (do not decrement until payment completes)
        try:
            available = int(item_to_increase.get("quantity", 0))
        except Exception:
            available = 0
        target_key = self._cart_item_key(item_to_increase)
        for cart_item_info in self.cart:
            if self._cart_item_key(cart_item_info["item"]) == target_key:
                if cart_item_info["quantity"] < available:
                    cart_item_info["quantity"] += 1
                    self.show_cart()  # Refresh cart screen
                return

    def decrease_cart_item_quantity(self, item_to_decrease):
        """Decreases an item's quantity in the cart by 1."""
        target_key = self._cart_item_key(item_to_decrease)
        for item_info in self.cart:
            if self._cart_item_key(item_info["item"]) == target_key:
                if item_info["quantity"] > 1:
                    item_info["quantity"] -= 1
                    self.show_cart()  # Refresh cart screen
                else:  # If quantity is 1, remove it completely
                    self.remove_from_cart(item_to_decrease)
                return

    def clear_cart(self):
        """Empties the cart."""
        self.cart.clear()

    def get_available_stock(self, item_name):
        """Return available stock for an item based on assigned slots (current term)."""
        if not item_name:
            return 0
        assigned = getattr(self, 'assigned_slots', None)
        if isinstance(assigned, list) and assigned:
            term_idx = getattr(self, 'assigned_term', 0) or 0
            total = 0
            for slot in assigned:
                try:
                    if not slot or not isinstance(slot, dict):
                        continue
                    terms = slot.get('terms', [])
                    if len(terms) > term_idx and terms[term_idx]:
                        if terms[term_idx].get('name') == item_name:
                            total += int(terms[term_idx].get('quantity', 0))
                except Exception:
                    continue
            return max(0, total)
        # Fallback to items list
        for item in getattr(self, 'items', []):
            if item.get('name') == item_name:
                return max(0, int(item.get('quantity', 0)))
        return 0

    def _decrement_assigned_stock(self, item_name, quantity, preferred_slot=None):
        """Decrement stock for an item, optionally targeting a specific slot first."""
        if quantity <= 0:
            return 0
        assigned = getattr(self, 'assigned_slots', None)
        if not isinstance(assigned, list) or not assigned:
            return 0
        term_idx = getattr(self, 'assigned_term', 0) or 0
        # Collect matching slot indices
        matches = []
        for idx, slot in enumerate(assigned):
            try:
                if not slot or not isinstance(slot, dict):
                    continue
                terms = slot.get('terms', [])
                if len(terms) > term_idx and terms[term_idx]:
                    if terms[term_idx].get('name') == item_name:
                        matches.append(idx)
            except Exception:
                continue
        if not matches:
            return 0
        ordered_matches = list(matches)
        try:
            pref = int(preferred_slot) if preferred_slot is not None else None
            pref_idx = (pref - 1) if pref and pref > 0 else None
            if pref_idx in matches:
                # Preserve per-tray behavior when the cart entry came from a known slot.
                ordered_matches = [pref_idx]
        except Exception:
            pass

        remaining = int(quantity)
        # Round-robin decrement across selected matching slots.
        while remaining > 0:
            progressed = False
            for idx in ordered_matches:
                if remaining <= 0:
                    break
                try:
                    entry = assigned[idx]['terms'][term_idx]
                    cur = int(entry.get('quantity', 0))
                    if cur > 0:
                        entry['quantity'] = cur - 1
                        remaining -= 1
                        progressed = True
                except Exception:
                    continue
            if not progressed:
                break
        return int(quantity) - remaining

    def apply_cart_stock_deductions(self, cart_items):
        """Apply stock deductions to assigned slots after successful payment."""
        if not cart_items:
            return
        total_deducted = {}
        for item_info in cart_items:
            try:
                item_obj = item_info.get('item') if isinstance(item_info, dict) else None
                qty = int(item_info.get('quantity', 1)) if isinstance(item_info, dict) else 1
                name = item_obj.get('name') if isinstance(item_obj, dict) else None
                preferred_slot = self._item_slot_number(item_obj) if isinstance(item_obj, dict) else None
                if not name or qty <= 0:
                    continue
                deducted = self._decrement_assigned_stock(name, qty, preferred_slot=preferred_slot)
                total_deducted[name] = total_deducted.get(name, 0) + deducted
            except Exception:
                continue
        # Persist assigned slots to disk
        try:
            with open(self.assigned_items_path, "w") as f:
                json.dump(self.assigned_slots, f, indent=2)
        except Exception as e:
            print(f"[Stock] Failed to save assigned_items.json: {e}")
        # Refresh derived items list and kiosk view
        try:
            self.items = self._extract_items_from_slots(self.assigned_slots)
            kf = self.frames.get("KioskFrame")
            if kf:
                kf.populate_items()
        except Exception:
            pass

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
            # Keep dispensing deterministic: ascending slot order, one slot at a time.
            self.vend_cart_items_organized(checked_out_items)
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

    def _parse_active_slots_from_status(self, status_msg):
        """Parse ESP32 STATUS response ('1,5,12' or 'NONE') into a set of slot numbers."""
        text = str(status_msg or "").strip()
        if not text or text.upper() == "NONE":
            return set()
        active_slots = set()
        for token in text.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                active_slots.add(int(token))
            except Exception:
                continue
        return active_slots

    def _wait_for_slot_rotation_complete(self, host, slot_number, timeout_sec=18.0, poll_interval_sec=0.08, min_inactive_polls=2):
        """
        Wait until slot is no longer active in ESP32 STATUS.
        A valid completion requires seeing slot transition active -> stable inactive.
        Firmware stops the motor after 2 limit-switch pulses (or failsafe timeout).
        """
        try:
            from esp32_client import send_command
        except Exception:
            return False

        deadline = time.time() + max(1.0, float(timeout_sec))
        saw_active = False
        inactive_polls = 0
        required_inactive = max(1, int(min_inactive_polls))
        while time.time() < deadline:
            try:
                status_msg = send_command(host, "STATUS", timeout=1.0)
                active_slots = self._parse_active_slots_from_status(status_msg)
                if int(slot_number) in active_slots:
                    saw_active = True
                    inactive_polls = 0
                else:
                    if saw_active:
                        inactive_polls += 1
                        if inactive_polls >= required_inactive:
                            return True
            except Exception:
                pass
            time.sleep(max(0.05, float(poll_interval_sec)))
        return False

    def vend_slots_for(self, item_name, quantity=1, preferred_slot=None):
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
        pulse_timeout_ms = 15000  # Failsafe timeout; normal stop is 2 limit-switch pulses
        try:
            pulse_timeout_ms = int(
                self.config.get('hardware', {}).get('vend_rotation_failsafe_ms', 15000)
            ) if isinstance(self.config, dict) else 15000
        except Exception:
            pulse_timeout_ms = 15000
        
        # Get dispense timeout from config
        dispense_timeout = self.config.get('hardware', {}).get('ir_sensors', {}).get('dispense_timeout', 15.0) if isinstance(self.config, dict) else 15.0
        try:
            same_slot_pause_ms = int(self.config.get('hardware', {}).get('vend_same_slot_pause_ms', 300))
        except Exception:
            same_slot_pause_ms = 300
        if same_slot_pause_ms < 0:
            same_slot_pause_ms = 0
        
        selected_matches = list(matches)
        try:
            pref_slot = int(preferred_slot) if preferred_slot is not None else None
            if pref_slot and pref_slot in matches:
                selected_matches = [pref_slot]
                print(f'[VEND] Preferred slot {pref_slot} selected for "{item_name}"')
            elif pref_slot:
                print(f'[VEND] WARNING: Preferred slot {pref_slot} is not assigned for "{item_name}", using mapped slots {matches}')
        except Exception:
            pass

        print(f'[VEND] Found {len(selected_matches)} slot(s) for "{item_name}": {selected_matches}')
        print(f'[VEND] Using ESP32 host: {host}, rotation_failsafe_ms: {pulse_timeout_ms}')
        try:
            retry_delay_ms = int(self.config.get('hardware', {}).get('vend_retry_delay_ms', 350))
        except Exception:
            retry_delay_ms = 350
        if retry_delay_ms < 0:
            retry_delay_ms = 0
        try:
            max_attempts = int(self.config.get('hardware', {}).get('vend_max_attempts_total', 0))
        except Exception:
            max_attempts = 0
        if max_attempts < 0:
            max_attempts = 0
        try:
            target_quantity = int(quantity)
        except Exception:
            target_quantity = 1
        if target_quantity <= 0:
            print(f'[VEND] No quantity requested for "{item_name}".')
            return
        
        # Round-robin distribute pulses and keep retrying until required quantity is met.
        successful_dispenses = 0
        total_attempts = 0
        while successful_dispenses < target_quantity:
            slot_number = selected_matches[successful_dispenses % len(selected_matches)]
            total_attempts += 1
            if max_attempts > 0 and total_attempts > max_attempts:
                print(f'[VEND] ERROR: Reached max attempts ({max_attempts}) for "{item_name}" at {successful_dispenses}/{target_quantity}.')
                break
            dispense_completed = False
            try:
                with self._vend_lock:
                    print(f'[VEND] Pulsing slot {slot_number} (2-pulse rotation, failsafe={pulse_timeout_ms}ms) (item: {item_name}, quantity item {successful_dispenses+1}/{target_quantity}, attempt {total_attempts})')
                    
                    # Start monitoring dispense for this slot if dispense monitor is available
                    if self.dispense_monitor:
                        self._track_pending_dispense(slot_number, item_name)
                        self.dispense_monitor.start_dispense(
                            slot_id=slot_number,
                            timeout=dispense_timeout,
                            item_name=item_name
                        )
                        print(f'[VEND] IR sensor monitoring started for slot {slot_number}, timeout={dispense_timeout}s')
                    else:
                        print(f'[VEND] WARNING: Dispense monitor not available - no IR sensor verification')
                    
                    try:
                        # ESP32 controls the MUX boards for slots 1-40
                        from esp32_client import send_command, pulse_slot
                        try:
                            # quick STATUS check
                            status_resp = send_command(host, "STATUS", timeout=1.0)
                            print(f'[VEND] ESP32 STATUS: {status_resp}')
                            # small settle time before pulsing
                            time.sleep(0.05)
                        except Exception as e:
                            print(f'[VEND] WARNING: ESP32 STATUS check failed: {e}')

                        # Attempt pulse and validate response.
                        # Do not retry here: PULSE is non-idempotent and a delayed/lost ACK
                        # can otherwise cause an unintended extra rotation.
                        result = None
                        try:
                            result = pulse_slot(host, slot_number, pulse_timeout_ms, timeout=3.0)
                            print(f'[VEND] Pulse response: {result}')
                        except Exception as e:
                            print(f'[VEND] WARNING: pulse_slot raised: {e}')
                        if not result or "OK" not in str(result).upper():
                            print(f'[VEND] WARNING: pulse response not OK for slot {slot_number}; monitoring completion without retry')

                        if result and "OK" in str(result).upper():
                            print(f'[VEND] SUCCESS: Pulse sent to ESP32 for slot {slot_number}, response: {result}')
                        else:
                            print(f'[VEND] ERROR: ESP32 did not confirm pulse for slot {slot_number}. Response: {result}')
                        # Wait for firmware to finish the rotation (2 limit pulses).
                        wait_timeout_sec = max(5.0, (pulse_timeout_ms / 1000.0) + 2.0)
                        completed = self._wait_for_slot_rotation_complete(
                            host=host,
                            slot_number=slot_number,
                            timeout_sec=wait_timeout_sec
                        )
                        if completed:
                            print(f'[VEND] Slot {slot_number} rotation complete (2 pulses detected).')
                            dispense_completed = True
                        else:
                            print(f'[VEND] WARNING: Slot {slot_number} completion not confirmed before timeout.')
                    except Exception as e:
                        print(f'[VEND] CRITICAL ERROR: Failed to send pulse for slot {slot_number}: {e}')
                        print(f'[VEND]   Slot: {slot_number}')
                        print(f'[VEND]   Rotation failsafe: {pulse_timeout_ms}ms')
                        import traceback
                        traceback.print_exc()
            except Exception as e:
                print(f'[VEND] CRITICAL ERROR: Exception vending slot {slot_number}: {e}')
                import traceback
                traceback.print_exc()

            if dispense_completed:
                successful_dispenses += 1
            else:
                print(f'[VEND] RETRY: "{item_name}" still at {successful_dispenses}/{target_quantity}.')
                if retry_delay_ms > 0:
                    time.sleep(retry_delay_ms / 1000.0)
                continue

            # Apply a brief stop between repeated rotations on the same slot.
            if len(selected_matches) == 1 and successful_dispenses < target_quantity and same_slot_pause_ms > 0:
                print(f'[VEND] Same-slot pause: {same_slot_pause_ms}ms before next rotation on slot {slot_number}.')
                time.sleep(same_slot_pause_ms / 1000.0)

            # Small settle delay to keep MUX switching safe between pulses
            try:
                settle_ms = int(self.config.get('hardware', {}).get('vend_settle_ms', 200))
                if settle_ms > 0:
                    time.sleep(settle_ms / 1000.0)
            except Exception:
                time.sleep(0.2)

        if successful_dispenses < target_quantity:
            print(f'[VEND] INCOMPLETE: "{item_name}" dispensed {successful_dispenses}/{target_quantity}.')
        else:
            print(f'[VEND] COMPLETE: "{item_name}" dispensed {successful_dispenses}/{target_quantity}.')

    def vend_cart_items_organized(self, cart_items):
        """Dispense multiple items organized by slot in ascending order.
        
        This method groups items by their assigned slots and dispenses them slot-by-slot
        in ascending order. For items assigned to the same slot, all are dispensed from
        that slot before moving to the next slot.

        Each dispense is controlled by firmware limit-switch logic:
        2 limit-switch pulses = 1 full spring rotation (with failsafe timeout).
        
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
                preferred_slot = self._item_slot_number(item_obj) if isinstance(item_obj, dict) else None
                
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

                # If checkout item came from a specific tray, keep dispensing on that tray.
                try:
                    if preferred_slot and preferred_slot in item_slots:
                        item_slots = [preferred_slot]
                        print(f'[VEND-ORG] Preferred slot {preferred_slot} selected for "{item_name}"')
                except Exception:
                    pass
                
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
        pulse_timeout_ms = 15000  # Failsafe timeout; normal stop is 2 limit-switch pulses
        try:
            pulse_timeout_ms = int(
                self.config.get('hardware', {}).get('vend_rotation_failsafe_ms', 15000)
            ) if isinstance(self.config, dict) else 15000
        except Exception:
            pulse_timeout_ms = 15000
        
        # Get dispense timeout from config
        dispense_timeout = self.config.get('hardware', {}).get('ir_sensors', {}).get('dispense_timeout', 15.0) if isinstance(self.config, dict) else 15.0
        try:
            same_slot_pause_ms = int(self.config.get('hardware', {}).get('vend_same_slot_pause_ms', 300))
        except Exception:
            same_slot_pause_ms = 300
        if same_slot_pause_ms < 0:
            same_slot_pause_ms = 0
        try:
            retry_delay_ms = int(self.config.get('hardware', {}).get('vend_retry_delay_ms', 350))
        except Exception:
            retry_delay_ms = 350
        if retry_delay_ms < 0:
            retry_delay_ms = 0
        try:
            max_attempts_per_slot = int(self.config.get('hardware', {}).get('vend_max_attempts_per_slot', 0))
        except Exception:
            max_attempts_per_slot = 0
        if max_attempts_per_slot < 0:
            max_attempts_per_slot = 0
        
        print(f'[VEND-ORG] Using ESP32 host: {host}, rotation_failsafe_ms: {pulse_timeout_ms}')
        
        # Dispense each slot completely before moving to the next.
        # Only move forward when required count is confirmed for the current slot.
        total_required = sum(len(v) for v in slot_to_items.values())
        total_dispensed = 0

        for slot_number in sorted_slots:
            items_for_slot = slot_to_items[slot_number]
            required_for_slot = len(items_for_slot)
            dispensed_for_slot = 0
            attempts_for_slot = 0
            print(f'[VEND-ORG] Processing slot {slot_number}: required {required_for_slot} item(s)')

            while dispensed_for_slot < required_for_slot:
                attempts_for_slot += 1
                if max_attempts_per_slot > 0 and attempts_for_slot > max_attempts_per_slot:
                    print(f'[VEND-ORG] ERROR: Slot {slot_number} hit max attempts ({max_attempts_per_slot}) at {dispensed_for_slot}/{required_for_slot}.')
                    break
                item_entry = items_for_slot[dispensed_for_slot]
                item_name = item_entry.get('name', 'Unknown')
                dispense_completed = False
                try:
                    with self._vend_lock:
                        print(f'[VEND-ORG] Pulsing slot {slot_number} (2-pulse rotation, failsafe={pulse_timeout_ms}ms) (item: {item_name}, dispense {dispensed_for_slot+1}/{required_for_slot}, attempt {attempts_for_slot})')

                        # Start monitoring dispense for this slot if available
                        if self.dispense_monitor:
                            self._track_pending_dispense(slot_number, item_name)
                            self.dispense_monitor.start_dispense(
                                slot_id=slot_number,
                                timeout=dispense_timeout,
                                item_name=item_name
                            )
                            print(f'[VEND-ORG] IR sensor monitoring started for slot {slot_number}, timeout={dispense_timeout}s')
                        else:
                            print(f'[VEND-ORG] WARNING: Dispense monitor not available - no IR sensor verification')

                        try:
                            # ESP32 controls the MUX boards for slots 1-40
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
                                result = pulse_slot(host, slot_number, pulse_timeout_ms, timeout=3.0)
                                print(f'[VEND-ORG] Pulse response: {result}')
                            except Exception as e:
                                print(f'[VEND-ORG] WARNING: pulse_slot raised: {e}')

                            # Do not retry here: PULSE is non-idempotent and a delayed/lost ACK
                            # can otherwise cause an unintended extra rotation.
                            if not result or "OK" not in str(result).upper():
                                print(f'[VEND-ORG] WARNING: pulse response not OK for slot {slot_number}; monitoring completion without retry')

                            if result and "OK" in str(result).upper():
                                print(f'[VEND-ORG] SUCCESS: Pulse sent to ESP32 for slot {slot_number}, response: {result}')
                            else:
                                print(f'[VEND-ORG] ERROR: ESP32 did not confirm pulse for slot {slot_number}. Response: {result}')
                            # Wait for firmware to finish the rotation (2 limit pulses).
                            wait_timeout_sec = max(5.0, (pulse_timeout_ms / 1000.0) + 2.0)
                            completed = self._wait_for_slot_rotation_complete(
                                host=host,
                                slot_number=slot_number,
                                timeout_sec=wait_timeout_sec
                            )
                            if completed:
                                print(f'[VEND-ORG] Slot {slot_number} rotation complete (2 pulses detected).')
                                dispense_completed = True
                            else:
                                print(f'[VEND-ORG] WARNING: Slot {slot_number} completion not confirmed before timeout.')
                        except Exception as e:
                            print(f'[VEND-ORG] CRITICAL ERROR: Failed to send pulse for slot {slot_number}: {e}')
                            import traceback
                            traceback.print_exc()

                except Exception as e:
                    print(f'[VEND-ORG] CRITICAL ERROR: Exception vending slot {slot_number}: {e}')
                    import traceback
                    traceback.print_exc()

                if dispense_completed:
                    dispensed_for_slot += 1
                    total_dispensed += 1
                else:
                    print(f'[VEND-ORG] RETRY: Slot {slot_number} still at {dispensed_for_slot}/{required_for_slot}.')
                    if retry_delay_ms > 0:
                        time.sleep(retry_delay_ms / 1000.0)
                    continue

                # Same-slot multi-vend: stop briefly after each full rotation before next.
                if dispensed_for_slot < required_for_slot and same_slot_pause_ms > 0:
                    print(f'[VEND-ORG] Same-slot pause: {same_slot_pause_ms}ms before next rotation on slot {slot_number}.')
                    time.sleep(same_slot_pause_ms / 1000.0)

                # Small settle delay to keep MUX switching safe between pulses
                try:
                    settle_ms = int(self.config.get('hardware', {}).get('vend_settle_ms', 200))
                    if settle_ms > 0:
                        time.sleep(settle_ms / 1000.0)
                except Exception:
                    time.sleep(0.2)

            print(f'[VEND-ORG] Slot {slot_number} summary: {dispensed_for_slot}/{required_for_slot} dispensed in {attempts_for_slot} attempt(s).')

        if total_dispensed < total_required:
            print(f'[VEND-ORG] INCOMPLETE: Dispensed {total_dispensed}/{total_required} requested item(s).')
        else:
            print(f'[VEND-ORG] COMPLETE: Dispensed {total_dispensed}/{total_required} requested item(s).')

    def update_item(self, original_item_name, updated_item_data):
        """Update price/quantity in assigned slots, then refresh admin and kiosk views."""
        try:
            price_val = float(updated_item_data.get("price", 0))
            qty_val = int(updated_item_data.get("quantity", 0))
        except Exception:
            # If values are invalid, do not apply update.
            return

        slot_number = updated_item_data.get("_slot_number")
        term_idx = getattr(self, "assigned_term", 0) or 0
        updated_in_slots = False

        # Primary path: update assigned slot data (source of truth for UI).
        if isinstance(getattr(self, "assigned_slots", None), list) and self.assigned_slots:
            target_indices = []
            try:
                if slot_number is not None:
                    slot_idx = int(slot_number) - 1
                    if 0 <= slot_idx < len(self.assigned_slots):
                        target_indices = [slot_idx]
            except Exception:
                target_indices = []

            # Fallback: locate by item name in current term.
            if not target_indices:
                for idx, slot in enumerate(self.assigned_slots):
                    if isinstance(slot, dict) and isinstance(slot.get("terms"), list):
                        terms = slot.get("terms") or []
                        if len(terms) > term_idx and isinstance(terms[term_idx], dict):
                            if terms[term_idx].get("name") == original_item_name:
                                target_indices = [idx]
                                break
                    elif isinstance(slot, dict) and slot.get("name") == original_item_name:
                        target_indices = [idx]
                        break

            for idx in target_indices:
                slot = self.assigned_slots[idx]
                if isinstance(slot, dict) and isinstance(slot.get("terms"), list):
                    terms = slot.get("terms") or []
                    while len(terms) <= term_idx:
                        terms.append(None)
                    if not isinstance(terms[term_idx], dict):
                        terms[term_idx] = {}
                    terms[term_idx]["price"] = price_val
                    terms[term_idx]["quantity"] = qty_val
                    updated_in_slots = True
                elif isinstance(slot, dict):
                    slot["price"] = price_val
                    slot["quantity"] = qty_val
                    updated_in_slots = True

            if updated_in_slots:
                try:
                    with open(self.assigned_items_path, "w", encoding="utf-8") as f:
                        json.dump(self.assigned_slots, f, indent=2)
                except Exception as e:
                    print(f"[MainApp] Failed to save assigned slots: {e}")

                # Rebuild flattened list used by Admin/Kiosk and keep legacy file in sync.
                self.items = self._extract_items_from_slots(self.assigned_slots)
                try:
                    self.save_items_to_json()
                except Exception:
                    pass
            else:
                # Legacy fallback path.
                for i, item in enumerate(self.items):
                    if item.get("name") == original_item_name:
                        merged = dict(item)
                        merged.update(updated_item_data)
                        merged["price"] = price_val
                        merged["quantity"] = qty_val
                        self.items[i] = merged
                        break
                self.save_items_to_json()

        # Refresh UI views immediately.
        try:
            self.frames["AdminScreen"].populate_items()
        except Exception:
            pass
        try:
            self.frames["KioskFrame"].populate_items()
        except Exception:
            pass

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
        # From StartOrder, go back to Selection
        elif self.active_frame_name in ["StartOrderScreen"]:
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
