"""
Logs Viewer Screen

Displays daily sales summaries and temperature logs in a user-friendly interface.
Allows viewing/exporting log files for analysis.
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk, messagebox, filedialog
from daily_sales_logger import get_logger
from datetime import datetime, timedelta
import os
import io
from fix_paths import get_absolute_path
from system_status_panel import SystemStatusPanel

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


def pil_to_photoimage(pil_image):
    """Convert PIL Image to Tkinter PhotoImage using PPM format (no ImageTk needed)."""
    with io.BytesIO() as output:
        pil_image.save(output, format="PPM")
        data = output.getvalue()
    return tk.PhotoImage(data=data)


def _get_touch_metrics(anchor):
    controller = getattr(anchor, "controller", None)
    cfg = getattr(controller, "config", {}) if controller is not None else {}

    diagonal_inches = 13.3
    try:
        diagonal_inches = float((cfg or {}).get("display_diagonal_inches", diagonal_inches))
    except Exception:
        diagonal_inches = 13.3

    try:
        screen_w = max(1, int(anchor.winfo_screenwidth()))
        screen_h = max(1, int(anchor.winfo_screenheight()))
        diagonal_pixels = (screen_w ** 2 + screen_h ** 2) ** 0.5
        ppi = diagonal_pixels / diagonal_inches if diagonal_inches > 0 else 165.0
    except Exception:
        ppi = 165.0

    touch_px = max(44, int(ppi * 0.30))
    base_font = max(10, int(touch_px * 0.28))
    button_font = max(11, int(touch_px * 0.30))

    return {
        "touch_px": touch_px,
        "base_font": base_font,
        "button_font": button_font,
        "title_font": max(18, button_font + 10),
        "section_pad": max(10, int(touch_px * 0.22)),
        "row_pad": max(8, int(touch_px * 0.18)),
        "button_padx": max(12, int(touch_px * 0.38)),
        "button_pady": max(8, int(touch_px * 0.18)),
        "entry_width_chars": max(14, int(touch_px * 0.35)),
        "list_height": max(12, int(touch_px * 0.28)),
    }


class LogsScreen(tk.Frame):
    """Screen for viewing sales and temperature logs."""
    
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg="#f0f4f8")
        self.controller = controller
        self.logger = get_logger()
        self.touch = _get_touch_metrics(controller)
        self._configure_styles()
        screen_height = controller.winfo_screenheight()
        self.header_px = max(96, int(screen_height * 0.14))
        self.touch_dead_zone_bottom_start_px = 1700
        self.touch_dead_zone_bottom_px = max(0, int(screen_height - self.touch_dead_zone_bottom_start_px))
        cfg = getattr(self.controller, "config", {}) if isinstance(getattr(self.controller, "config", {}), dict) else {}
        self.machine_name = cfg.get("machine_name", "RAON")
        self.machine_subtitle = cfg.get("machine_subtitle", "Rapid Access Outlet for Electronic Necessities")
        self.header_logo_path = cfg.get("header_logo_path", "")
        self.logo_image = None
        self.brand_bg = "#2222a8"
        self.header_fonts = {
            "machine_title": tkfont.Font(family="Helvetica", size=max(18, int(self.header_px * 0.30)), weight="bold"),
            "machine_subtitle": tkfont.Font(family="Helvetica", size=max(10, int(self.header_px * 0.16))),
            "logo_placeholder": tkfont.Font(family="Helvetica", size=max(14, int(self.header_px * 0.28)), weight="bold"),
        }

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.brand_header = tk.Frame(self, bg=self.brand_bg, height=self.header_px)
        self.brand_header.grid(row=0, column=0, sticky="ew")
        self.brand_header.grid_propagate(False)

        brand_left = tk.Frame(self.brand_header, bg=self.brand_bg)
        brand_left.pack(side="left", padx=12, pady=8)

        logo_frame = tk.Frame(
            brand_left,
            bg=self.brand_bg,
            width=160,
            height=int(self.header_px * 0.82),
        )
        logo_frame.pack(side="left", padx=(0, 12))
        logo_frame.pack_propagate(False)

        self.logo_image_label = tk.Label(logo_frame, bg=self.brand_bg, fg="white")
        self.logo_image_label.pack(expand=True)

        logo_text_frame = tk.Frame(brand_left, bg=self.brand_bg)
        logo_text_frame.pack(anchor="w")

        self.brand_title_label = tk.Label(
            logo_text_frame,
            text=self.machine_name,
            bg=self.brand_bg,
            fg="white",
            font=self.header_fonts["machine_title"],
            anchor="w",
            justify="left",
        )
        self.brand_title_label.pack(anchor="w")

        self.brand_subtitle_label = tk.Label(
            logo_text_frame,
            text=self.machine_subtitle,
            bg=self.brand_bg,
            fg="white",
            font=self.header_fonts["machine_subtitle"],
            anchor="w",
            justify="left",
        )
        self.brand_subtitle_label.pack(anchor="w")
        self.load_header_logo()
        
        # Title bar
        title_frame = tk.Frame(self, bg="#2c3e50", height=60)
        title_frame.grid(row=1, column=0, sticky="ew")
        title_frame.grid_propagate(False)
        
        title_label = tk.Label(
            title_frame, 
            text="📊 Sales & Temperature Logs",
            font=("Arial", self.touch["title_font"], "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title_label.pack(pady=10)
        
        # Main content frame with tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.configure(style="LogsTouch.TNotebook")
        self.notebook.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=self.touch["section_pad"],
            pady=self.touch["row_pad"],
        )
        
        # Tab 1: Today's Summary
        self.summary_frame = tk.Frame(self.notebook, bg="#f0f4f8")
        self.notebook.add(self.summary_frame, text="Today's Summary")
        self._setup_summary_tab()
        
        # Tab 2: View Logs
        self.logs_frame = tk.Frame(self.notebook, bg="#f0f4f8")
        self.notebook.add(self.logs_frame, text="View Logs")
        self._setup_logs_tab()
        
        # Tab 3: History
        self.history_frame = tk.Frame(self.notebook, bg="#f0f4f8")
        self.notebook.add(self.history_frame, text="History")
        self._setup_history_tab()
        
        # Bottom button bar
        button_frame = tk.Frame(self, bg="#f0f4f8")
        button_top_pady = max(2, self.touch["row_pad"] - 6)
        button_bottom_pady = max(4, self.touch["row_pad"] - 2)
        button_frame.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=self.touch["section_pad"],
            pady=(button_top_pady, button_bottom_pady),
        )
        
        export_btn = tk.Button(
            button_frame,
            text="📥 Export Today's Log",
            font=("Arial", self.touch["button_font"], "bold"),
            bg="#27ae60",
            fg="white",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=self.export_todays_log
        )
        export_btn.pack(side="left", padx=5)
        
        back_btn = tk.Button(
            button_frame,
            text="← Back",
            font=("Arial", self.touch["button_font"], "bold"),
            bg="#95a5a6",
            fg="white",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=lambda: controller.show_frame("AdminScreen")
        )
        back_btn.pack(side="right", padx=5)
        status_height = self.touch_dead_zone_bottom_px if self.touch_dead_zone_bottom_px > 0 else max(70, int(screen_height * 0.08))
        self.status_zone = tk.Frame(self, bg="#111111", height=status_height)
        self.status_zone.grid(row=4, column=0, sticky="ew")
        self.status_zone.grid_propagate(False)
        self.status_panel = SystemStatusPanel(self.status_zone, controller=self.controller)
        self.status_panel.pack(fill="both", expand=True)
        self.bind("<<ShowFrame>>", self._on_show_frame)

    def _on_show_frame(self, event=None):
        self._refresh_brand_header()
        try:
            self.status_panel.refresh_display()
        except Exception:
            pass
        try:
            self.refresh_summary()
        except Exception:
            pass
        try:
            self.refresh_log_list()
        except Exception:
            pass

    def _refresh_brand_header(self):
        cfg = getattr(self.controller, "config", {}) if isinstance(getattr(self.controller, "config", {}), dict) else {}
        self.machine_name = cfg.get("machine_name", self.machine_name)
        self.machine_subtitle = cfg.get("machine_subtitle", self.machine_subtitle)
        self.header_logo_path = cfg.get("header_logo_path", self.header_logo_path)
        try:
            self.brand_title_label.config(text=self.machine_name)
            self.brand_subtitle_label.config(text=self.machine_subtitle)
        except Exception:
            pass
        self.load_header_logo()

    def load_header_logo(self):
        """Load header logo from config path; fallback to machine initials."""
        self.logo_image = None
        logo_path = str(self.header_logo_path or "").strip()
        resolved_logo = None

        if logo_path:
            resolved_logo = get_absolute_path(logo_path)
            if not os.path.exists(resolved_logo):
                resolved_logo = logo_path if os.path.exists(logo_path) else None

        if resolved_logo and PIL_AVAILABLE:
            try:
                img = Image.open(resolved_logo)
                max_h = int(self.header_px * 0.80)
                max_w = 180
                resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                img.thumbnail((max_w, max_h), resample)
                self.logo_image = pil_to_photoimage(img)
                self.logo_image_label.config(image=self.logo_image, text="")
                self.logo_image_label.image = self.logo_image
                return
            except Exception:
                pass

        fallback = (self.machine_name[:1] if self.machine_name else "R").upper()
        self.logo_image_label.config(
            image="",
            text=fallback,
            font=self.header_fonts["logo_placeholder"],
            fg="white",
            bg=self.brand_bg,
        )

    def _configure_styles(self):
        try:
            style = ttk.Style(self)
            style.configure(
                "LogsTouch.TNotebook.Tab",
                font=("Arial", max(10, self.touch["base_font"]), "bold"),
                padding=(max(8, self.touch["button_padx"] - 4), max(6, self.touch["button_pady"] - 2)),
            )
            style.configure("LogsTouch.TNotebook", tabmargins=(2, 4, 2, 0))
        except Exception:
            pass
    
    def _setup_summary_tab(self):
        """Setup today's sales summary display."""
        # Summary box
        summary_box = tk.Frame(self.summary_frame, bg="white", relief="sunken", bd=2)
        summary_box.pack(
            fill="both",
            expand=True,
            padx=self.touch["section_pad"],
            pady=self.touch["row_pad"],
        )
        
        self.summary_text = tk.Text(
            summary_box,
            height=20,
            font=("Courier", max(11, self.touch["base_font"])),
            bg="white",
            fg="#2c3e50",
            wrap="word"
        )
        self.summary_text.pack(
            fill="both",
            expand=True,
            padx=self.touch["section_pad"],
            pady=self.touch["row_pad"],
        )
        
        # Refresh button
        refresh_btn = tk.Button(
            self.summary_frame,
            text="🔄 Refresh",
            font=("Arial", max(10, self.touch["button_font"]), "bold"),
            bg="#3498db",
            fg="white",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=self.refresh_summary
        )
        refresh_btn.pack(pady=self.touch["row_pad"])
        
        # Initial load
        self.refresh_summary()
    
    def refresh_summary(self):
        """Refresh today's sales summary."""
        self.summary_text.config(state="normal")
        self.summary_text.delete("1.0", "end")
        
        try:
            summary = self.logger.get_today_summary()
            items_sold = self.logger.get_items_sold_summary()
            
            if summary:
                today = datetime.now().strftime("%A, %B %d, %Y")
                
                # Build items list
                items_display = ""
                if items_sold:
                    items_display = "\n📦 ITEMS SOLD:\n"
                    for item_name in sorted(items_sold.keys()):
                        qty = items_sold[item_name]
                        items_display += f"   {item_name:<35} x{qty:>3}\n"
                else:
                    items_display = "\n📦 ITEMS SOLD:\n   (No items sold yet)\n"
                
                display = f"""
╔════════════════════════════════════════════════════╗
║          TODAY'S SALES SUMMARY                     ║
║          {today}           ║
╚════════════════════════════════════════════════════╝

📊 TRANSACTIONS:
   Total Transactions: {summary['total_transactions']}
{items_display}
💰 REVENUE:
   Coins Received:     ₱{summary['total_coins']:>10,.2f}
   Bills Received:     ₱{summary['total_bills']:>10,.2f}
   ────────────────────────────
   Total Sales:        ₱{summary['total_sales']:>10,.2f}
   
🔄 CHANGE DISPENSED:
   Total Change:       ₱{summary['total_change']:>10,.2f}

💵 NET REVENUE:
   (Sales - Change):   ₱{summary['total_sales'] - summary['total_change']:>10,.2f}

{'─' * 52}

Last Updated: {datetime.now().strftime('%H:%M:%S')}
                """
                self.summary_text.insert("1.0", display)
        except Exception as e:
            self.summary_text.insert("1.0", f"Error loading summary:\n{e}")
        
        self.summary_text.config(state="disabled")
    
    def _setup_logs_tab(self):
        """Setup log viewer tab."""
        # Date selector
        date_frame = tk.Frame(self.logs_frame, bg="#f0f4f8")
        date_frame.pack(fill="x", padx=self.touch["section_pad"], pady=self.touch["row_pad"])
        
        tk.Label(
            date_frame,
            text="Select Date:",
            font=("Arial", self.touch["button_font"], "bold"),
            bg="#f0f4f8",
        ).pack(side="left", padx=6)
        
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        date_entry = tk.Entry(
            date_frame,
            textvariable=self.date_var,
            font=("Arial", max(10, self.touch["base_font"])),
            width=self.touch["entry_width_chars"],
        )
        date_entry.pack(side="left", padx=6, ipady=max(3, int(self.touch["touch_px"] * 0.08)))
        
        load_btn = tk.Button(
            date_frame,
            text="Load",
            font=("Arial", max(10, self.touch["button_font"]), "bold"),
            bg="#3498db",
            fg="white",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=self.load_log_file
        )
        load_btn.pack(side="left", padx=6)
        
        # Log text display
        log_box = tk.Frame(self.logs_frame, bg="white", relief="sunken", bd=2)
        log_box.pack(fill="both", expand=True, padx=self.touch["section_pad"], pady=self.touch["row_pad"])
        
        scrollbar = tk.Scrollbar(log_box)
        scrollbar.pack(side="right", fill="y")
        
        self.log_text = tk.Text(
            log_box,
            height=20,
            font=("Courier", max(10, self.touch["base_font"])),
            bg="white",
            fg="#2c3e50",
            yscrollcommand=scrollbar.set
        )
        self.log_text.pack(fill="both", expand=True, padx=self.touch["section_pad"], pady=self.touch["row_pad"])
        scrollbar.config(command=self.log_text.yview)
        
        # Initial load
        self.load_log_file()
    
    def load_log_file(self):
        """Load and display selected date's log file."""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        
        try:
            log_date = self.date_var.get()
            log_file = os.path.join(self.logger.logs_dir, f"sales_{log_date}.log")
            
            if os.path.exists(log_file):
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self.log_text.insert("1.0", content)
                self.log_text.insert("end", f"\n\n✓ Loaded {log_date}")
            else:
                self.log_text.insert("1.0", f"No log file found for {log_date}\n\nLog file should be at:\n{log_file}")
        except Exception as e:
            self.log_text.insert("1.0", f"Error loading log:\n{e}")
        
        self.log_text.config(state="disabled")
    
    def _setup_history_tab(self):
        """Setup history/available logs tab."""
        # Available logs list
        list_frame = tk.Frame(self.history_frame, bg="#f0f4f8")
        list_frame.pack(fill="both", expand=True, padx=self.touch["section_pad"], pady=self.touch["row_pad"])
        
        tk.Label(
            list_frame,
            text="Available Log Files:",
            font=("Arial", max(12, self.touch["button_font"]), "bold"),
            bg="#f0f4f8",
        ).pack(anchor="w", pady=6)
        
        # Scrollable list
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.log_list = tk.Listbox(
            list_frame,
            font=("Courier", max(10, self.touch["base_font"])),
            bg="white",
            yscrollcommand=scrollbar.set,
            height=self.touch["list_height"]
        )
        self.log_list.pack(fill="both", expand=True, pady=6)
        self.log_list.bind("<<ListboxSelect>>", self.on_log_selected)
        scrollbar.config(command=self.log_list.yview)
        
        # Populate list
        self.refresh_log_list()
    
    def refresh_log_list(self):
        """Refresh the list of available log files."""
        self.log_list.delete(0, "end")
        
        try:
            if os.path.exists(self.logger.logs_dir):
                log_files = sorted(
                    [f for f in os.listdir(self.logger.logs_dir) if f.startswith("sales_")],
                    reverse=True
                )
                
                for log_file in log_files:
                    file_path = os.path.join(self.logger.logs_dir, log_file)
                    file_size = os.path.getsize(file_path)
                    file_date = log_file.replace("sales_", "").replace(".log", "")
                    
                    display_text = f"{file_date}  ({file_size:,} bytes)"
                    self.log_list.insert("end", display_text)
        except Exception as e:
            self.log_list.insert("end", f"Error: {e}")
    
    def on_log_selected(self, event):
        """When a log is selected, load it in the view logs tab."""
        selection = self.log_list.curselection()
        if selection:
            item_text = self.log_list.get(selection[0])
            # Extract date from display text
            log_date = item_text.split("  ")[0]
            self.date_var.set(log_date)
            self.load_log_file()
            self.notebook.select(1)  # Switch to view logs tab
    
    def export_todays_log(self):
        """Export today's log to a file."""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = os.path.join(self.logger.logs_dir, f"sales_{today}.log")
            
            if not os.path.exists(log_file):
                messagebox.showwarning("Export Failed", f"No log file found for {today}")
                return
            
            # Ask user where to save
            save_path = filedialog.asksaveasfilename(
                defaultextension=".log",
                filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"sales_{today}.log"
            )
            
            if save_path:
                with open(log_file, "r", encoding="utf-8") as src:
                    content = src.read()
                with open(save_path, "w", encoding="utf-8") as dst:
                    dst.write(content)
                messagebox.showinfo("Export Successful", f"Log exported to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export log:\n{e}")
