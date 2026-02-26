"""
System Status Panel - Real-time hardware and monitoring status display

Displays:
- DHT22 sensor readings (temperature/humidity)
- TEC Peltier controller status
- IR sensor status (bin detection)
- Payment system status
- Overall system health
"""

import tkinter as tk
from tkinter import ttk
import threading
import time


class SystemStatusPanel(tk.Frame):
    """
    Real-time system status display widget for the vending machine.
    Shows hardware status, sensor readings, and system health indicators.
    """
    
    def __init__(self, master=None, controller=None, **kwargs):
        super().__init__(master, **kwargs)
        self.controller = controller
        self.configure(bg='#2c3e50', height=100)
        self.pack_propagate(False)
        
        # Status data (will be updated by callbacks)
        self.dht22_data = {
            'sensor_1': {'temp': None, 'humidity': None},
            'sensor_2': {'temp': None, 'humidity': None}
        }
        self.tec_status = {
            'enabled': False,
            'active': False,
            'target_temp': None,
            'current_temp': None
        }
        self.ir_status = {
            'sensor_1': None,  # True=present, False=absent
            'sensor_2': None,
            'detection_mode': 'any',
            'last_detection': None
        }
        self.system_health = 'operational'  # 'operational', 'warning', 'error'
        self.start_time = time.time()
        
        # Lock for thread-safe updates
        self._lock = threading.Lock()
        
        # Create UI
        self.create_widgets()
        
        # Start periodic update loop on Tk main thread
        self.update_job = None
        self.start_update_loop()
    
    def create_widgets(self):
        """Create the status panel layout."""
        # Main container with padding
        main_container = tk.Frame(self, bg='#2c3e50')
        main_container.pack(fill='both', expand=True, padx=8, pady=6)
        
        # Title bar with developer names
        title_frame = tk.Frame(main_container, bg='#2c3e50')
        title_frame.pack(fill='x', pady=(0, 8))
        
        # Left: System status title
        title_label = tk.Label(
            title_frame,
            text='🔧 SYSTEM STATUS',
            font=('Helvetica', 10, 'bold'),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        title_label.pack(side='left')
        
        # Center: Developer names (if available)
        cfg = getattr(self.controller, 'config', {}) if self.controller else {}
        group_members = cfg.get('group_members', [])
        if group_members and isinstance(group_members, list):
            members_text = ' • '.join(group_members)
            members_label = tk.Label(
                title_frame,
                text=members_text,
                font=('Helvetica', 8),
                bg='#2c3e50',
                fg='#95a5a6'
            )
            members_label.pack(side='left', padx=12)
        
        # Status indicator dot
        self.status_indicator = tk.Label(
            title_frame,
            text='●',
            font=('Helvetica', 14),
            bg='#2c3e50',
            fg='#27ae60'  # Green for operational
        )
        self.status_indicator.pack(side='right')
        
        # Content frame with horizontal sections
        content_frame = tk.Frame(main_container, bg='#2c3e50')
        content_frame.pack(fill='both', expand=True)
        
        # Left section: DHT22 Sensors
        self.create_dht22_section(content_frame)
        
        # Center section: TEC Peltier
        self.create_tec_section(content_frame)
        
        # Right section: IR Sensors
        self.create_ir_section(content_frame)
        
        # Far right section: Overall Health
        self.create_health_section(content_frame)
    
    def create_dht22_section(self, parent):
        """Create DHT22 sensor reading section."""
        section = tk.Frame(parent, bg='#34495e', relief='raised', bd=1)
        section.pack(side='left', fill='both', expand=True, padx=(0, 6))
        
        # Header
        header = tk.Label(
            section,
            text='🌡️ ENVIRONMENT',
            font=('Helvetica', 9, 'bold'),
            bg='#34495e',
            fg='#3498db'
        )
        header.pack(anchor='w', padx=6, pady=(4, 2))
        
        # Sensor 1
        s1_frame = tk.Frame(section, bg='#34495e')
        s1_frame.pack(fill='x', padx=6, pady=1)
        
        tk.Label(s1_frame, text='S1:', font=('Helvetica', 8), bg='#34495e', fg='#bdc3c7').pack(side='left', padx=(0, 4))
        
        self.dht22_s1_label = tk.Label(
            s1_frame,
            text='Temp: --°C',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#ecf0f1'
        )
        self.dht22_s1_label.pack(side='left')
        
        tk.Label(s1_frame, text='|', bg='#34495e', fg='#555').pack(side='left', padx=3)
        
        self.dht22_s1_humid = tk.Label(
            s1_frame,
            text='Humid: --%',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#ecf0f1'
        )
        self.dht22_s1_humid.pack(side='left')
        
        # Sensor 2
        s2_frame = tk.Frame(section, bg='#34495e')
        s2_frame.pack(fill='x', padx=6, pady=1)
        
        tk.Label(s2_frame, text='S2:', font=('Helvetica', 8), bg='#34495e', fg='#bdc3c7').pack(side='left', padx=(0, 4))
        
        self.dht22_s2_label = tk.Label(
            s2_frame,
            text='Temp: --°C',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#ecf0f1'
        )
        self.dht22_s2_label.pack(side='left')
        
        tk.Label(s2_frame, text='|', bg='#34495e', fg='#555').pack(side='left', padx=3)
        
        self.dht22_s2_humid = tk.Label(
            s2_frame,
            text='Humid: --%',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#ecf0f1'
        )
        self.dht22_s2_humid.pack(side='left')
    
    def create_tec_section(self, parent):
        """Create TEC Peltier controller section."""
        section = tk.Frame(parent, bg='#34495e', relief='raised', bd=1)
        section.pack(side='left', fill='both', expand=True, padx=(0, 6))
        
        # Header
        header = tk.Label(
            section,
            text='❄️ TEC COOLER',
            font=('Helvetica', 9, 'bold'),
            bg='#34495e',
            fg='#3498db'
        )
        header.pack(anchor='w', padx=6, pady=(4, 2))
        
        # Status and target
        status_frame = tk.Frame(section, bg='#34495e')
        status_frame.pack(fill='x', padx=6, pady=1)
        
        self.tec_status_label = tk.Label(
            status_frame,
            text='Status: OFF',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#e74c3c'
        )
        self.tec_status_label.pack(side='left')
        
        tk.Label(status_frame, text='|', bg='#34495e', fg='#555').pack(side='left', padx=3)
        
        self.tec_target_label = tk.Label(
            status_frame,
            text='Target: --°C',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#ecf0f1'
        )
        self.tec_target_label.pack(side='left')
        
        # Current temperature
        temp_frame = tk.Frame(section, bg='#34495e')
        temp_frame.pack(fill='x', padx=6, pady=1)
        
        tk.Label(temp_frame, text='Current:', font=('Helvetica', 8), bg='#34495e', fg='#bdc3c7').pack(side='left', padx=(0, 4))
        
        self.tec_current_label = tk.Label(
            temp_frame,
            text='--°C',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#ecf0f1'
        )
        self.tec_current_label.pack(side='left')
    
    def create_ir_section(self, parent):
        """Create IR sensor section."""
        section = tk.Frame(parent, bg='#34495e', relief='raised', bd=1)
        section.pack(side='left', fill='both', expand=True, padx=(0, 6))
        
        # Header
        header = tk.Label(
            section,
            text='📡 IR SENSORS',
            font=('Helvetica', 9, 'bold'),
            bg='#34495e',
            fg='#3498db'
        )
        header.pack(anchor='w', padx=6, pady=(4, 2))
        
        # Sensor 1
        s1_frame = tk.Frame(section, bg='#34495e')
        s1_frame.pack(fill='x', padx=6, pady=1)
        
        self.ir_s1_indicator = tk.Label(
            s1_frame,
            text='●',
            font=('Helvetica', 10),
            bg='#34495e',
            fg='#95a5a6'  # Gray for unknown
        )
        self.ir_s1_indicator.pack(side='left', padx=(0, 4))
        
        self.ir_s1_label = tk.Label(
            s1_frame,
            text='S1: --',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#ecf0f1'
        )
        self.ir_s1_label.pack(side='left')
        
        # Sensor 2
        s2_frame = tk.Frame(section, bg='#34495e')
        s2_frame.pack(fill='x', padx=6, pady=1)
        
        self.ir_s2_indicator = tk.Label(
            s2_frame,
            text='●',
            font=('Helvetica', 10),
            bg='#34495e',
            fg='#95a5a6'  # Gray for unknown
        )
        self.ir_s2_indicator.pack(side='left', padx=(0, 4))
        
        self.ir_s2_label = tk.Label(
            s2_frame,
            text='S2: --',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#ecf0f1'
        )
        self.ir_s2_label.pack(side='left')
        
        # Mode
        mode_frame = tk.Frame(section, bg='#34495e')
        mode_frame.pack(fill='x', padx=6, pady=(1, 0))
        
        self.ir_mode_label = tk.Label(
            mode_frame,
            text='Mode: any',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#f39c12'
        )
        self.ir_mode_label.pack(side='left')
    
    def create_health_section(self, parent):
        """Create overall health section."""
        section = tk.Frame(parent, bg='#34495e', relief='raised', bd=1)
        section.pack(side='left', fill='both', expand=True)
        
        # Header
        header = tk.Label(
            section,
            text='⚙️ SYSTEM',
            font=('Helvetica', 9, 'bold'),
            bg='#34495e',
            fg='#3498db'
        )
        header.pack(anchor='w', padx=6, pady=(4, 2))
        
        # Health status
        health_frame = tk.Frame(section, bg='#34495e')
        health_frame.pack(fill='x', padx=6, pady=1)
        
        self.health_indicator = tk.Label(
            health_frame,
            text='●',
            font=('Helvetica', 10),
            bg='#34495e',
            fg='#27ae60'
        )
        self.health_indicator.pack(side='left', padx=(0, 4))
        
        self.health_label = tk.Label(
            health_frame,
            text='Operational',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#ecf0f1'
        )
        self.health_label.pack(side='left')
        
        # Uptime
        uptime_frame = tk.Frame(section, bg='#34495e')
        uptime_frame.pack(fill='x', padx=6, pady=1)
        
        self.uptime_label = tk.Label(
            uptime_frame,
            text='Uptime: 00:00',
            font=('Helvetica', 8),
            bg='#34495e',
            fg='#bdc3c7'
        )
        self.uptime_label.pack(side='left')
    
    def update_dht22_reading(self, sensor_number, temp, humidity):
        """Update DHT22 sensor reading."""
        with self._lock:
            if sensor_number == 1:
                self.dht22_data['sensor_1'] = {'temp': temp, 'humidity': humidity}
            else:
                self.dht22_data['sensor_2'] = {'temp': temp, 'humidity': humidity}
    
    def update_tec_status(self, enabled, active, target_temp, current_temp):
        """Update TEC Peltier status."""
        with self._lock:
            self.tec_status = {
                'enabled': enabled,
                'active': active,
                'target_temp': target_temp,
                'current_temp': current_temp
            }
    
    def update_ir_status(self, sensor_1, sensor_2, detection_mode='any', last_detection=None):
        """
        Update IR sensor status.
        
        Args:
            sensor_1: True=item present, False=item absent, None=unknown
            sensor_2: True=item present, False=item absent, None=unknown
            detection_mode: 'any', 'all', or 'first'
            last_detection: Last detection timestamp
        """
        with self._lock:
            self.ir_status = {
                'sensor_1': sensor_1,
                'sensor_2': sensor_2,
                'detection_mode': detection_mode,
                'last_detection': last_detection
            }
    
    def set_system_health(self, status):
        """
        Set system health status.
        
        Args:
            status: 'operational', 'warning', or 'error'
        """
        with self._lock:
            self.system_health = status
    
    def start_update_loop(self):
        """Start periodic UI update loop on the Tk thread."""
        self._schedule_refresh()

    def _schedule_refresh(self):
        try:
            self.refresh_display()
        except Exception as e:
            print(f"Status panel update error: {e}")
        finally:
            # Keep updates alive even after transient UI errors
            self.update_job = self.after(1000, self._schedule_refresh)
    
    def refresh_display(self):
        """Refresh the display with current status."""
        try:
            with self._lock:
                # Update DHT22 section
                self.update_dht22_display()
                
                # Update TEC section
                self.update_tec_display()
                
                # Update IR section
                self.update_ir_display()
                
                # Update health section
                self.update_health_display()
        except Exception as e:
            print(f"Error refreshing status display: {e}")
    
    def update_dht22_display(self):
        """Update DHT22 display labels."""
        s1 = self.dht22_data['sensor_1']
        s2 = self.dht22_data['sensor_2']
        
        # Sensor 1
        if s1['temp'] is not None:
            temp_text = f"Temp: {s1['temp']:.1f}°C"
            humid_text = f"Humid: {s1['humidity']:.1f}%" if s1['humidity'] is not None else "Humid: --"
        else:
            temp_text = "Temp: --°C"
            humid_text = "Humid: --"
        
        self.dht22_s1_label.config(text=temp_text)
        self.dht22_s1_humid.config(text=humid_text)
        
        # Sensor 2
        if s2['temp'] is not None:
            temp_text = f"Temp: {s2['temp']:.1f}°C"
            humid_text = f"Humid: {s2['humidity']:.1f}%" if s2['humidity'] is not None else "Humid: --"
        else:
            temp_text = "Temp: --°C"
            humid_text = "Humid: --"
        
        self.dht22_s2_label.config(text=temp_text)
        self.dht22_s2_humid.config(text=humid_text)
    
    def update_tec_display(self):
        """Update TEC display labels."""
        status = self.tec_status
        
        if status['enabled']:
            status_text = "ON" if status['active'] else "OFF"
            status_color = "#27ae60" if status['active'] else "#e74c3c"
        else:
            status_text = "DISABLED"
            status_color = "#95a5a6"
        
        self.tec_status_label.config(text=f"Status: {status_text}", fg=status_color)
        
        if status['target_temp'] is not None:
            self.tec_target_label.config(text=f"Target: {status['target_temp']:.1f}°C")
        else:
            self.tec_target_label.config(text="Target: --°C")
        
        if status['current_temp'] is not None:
            self.tec_current_label.config(text=f"{status['current_temp']:.1f}°C")
        else:
            self.tec_current_label.config(text="--°C")
    
    def update_ir_display(self):
        """Update IR sensor display labels."""
        ir = self.ir_status
        
        # Sensor 1
        if ir['sensor_1'] is None:
            self.ir_s1_label.config(text='S1: --')
            self.ir_s1_indicator.config(fg='#95a5a6')  # Gray
        elif ir['sensor_1']:
            self.ir_s1_label.config(text='S1: PRESENT')
            self.ir_s1_indicator.config(fg='#f39c12')  # Orange
        else:
            self.ir_s1_label.config(text='S1: EMPTY')
            self.ir_s1_indicator.config(fg='#e74c3c')  # Red
        
        # Sensor 2
        if ir['sensor_2'] is None:
            self.ir_s2_label.config(text='S2: --')
            self.ir_s2_indicator.config(fg='#95a5a6')  # Gray
        elif ir['sensor_2']:
            self.ir_s2_label.config(text='S2: PRESENT')
            self.ir_s2_indicator.config(fg='#f39c12')  # Orange
        else:
            self.ir_s2_label.config(text='S2: EMPTY')
            self.ir_s2_indicator.config(fg='#e74c3c')  # Red
        
        # Mode
        self.ir_mode_label.config(text=f"Mode: {ir['detection_mode']}")
    
    def update_health_display(self):
        """Update health indicator display."""
        health = self.system_health
        
        if health == 'operational':
            self.health_indicator.config(fg='#27ae60')
            self.health_label.config(text='Operational')
            self.status_indicator.config(fg='#27ae60')
        elif health == 'warning':
            self.health_indicator.config(fg='#f39c12')
            self.health_label.config(text='Warning')
            self.status_indicator.config(fg='#f39c12')
        elif health == 'error':
            self.health_indicator.config(fg='#e74c3c')
            self.health_label.config(text='Error')
            self.status_indicator.config(fg='#e74c3c')

        # Uptime
        try:
            elapsed = int(max(0, time.time() - self.start_time))
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            if hours > 0:
                uptime_text = f"Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                uptime_text = f"Uptime: {minutes:02d}:{seconds:02d}"
            self.uptime_label.config(text=uptime_text)
        except Exception:
            pass
