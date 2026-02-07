"""
Logs Viewer Screen

Displays daily sales summaries and temperature logs in a user-friendly interface.
Allows viewing/exporting log files for analysis.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from daily_sales_logger import get_logger
from datetime import datetime, timedelta
import os


class LogsScreen(tk.Frame):
    """Screen for viewing sales and temperature logs."""
    
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg="#f0f4f8")
        self.controller = controller
        self.logger = get_logger()
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Title bar
        title_frame = tk.Frame(self, bg="#2c3e50", height=60)
        title_frame.grid(row=0, column=0, sticky="ew")
        title_frame.grid_propagate(False)
        
        title_label = tk.Label(
            title_frame, 
            text="📊 Sales & Temperature Logs",
            font=("Arial", 24, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title_label.pack(pady=10)
        
        # Main content frame with tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
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
        button_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        export_btn = tk.Button(
            button_frame,
            text="📥 Export Today's Log",
            font=("Arial", 11, "bold"),
            bg="#27ae60",
            fg="white",
            padx=15,
            pady=8,
            command=self.export_todays_log
        )
        export_btn.pack(side="left", padx=5)
        
        back_btn = tk.Button(
            button_frame,
            text="← Back",
            font=("Arial", 11, "bold"),
            bg="#95a5a6",
            fg="white",
            padx=15,
            pady=8,
            command=lambda: controller.show_frame("AdminScreen")
        )
        back_btn.pack(side="right", padx=5)
    
    def _setup_summary_tab(self):
        """Setup today's sales summary display."""
        # Summary box
        summary_box = tk.Frame(self.summary_frame, bg="white", relief="sunken", bd=2)
        summary_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.summary_text = tk.Text(
            summary_box,
            height=20,
            font=("Courier", 11),
            bg="white",
            fg="#2c3e50",
            wrap="word"
        )
        self.summary_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Refresh button
        refresh_btn = tk.Button(
            self.summary_frame,
            text="🔄 Refresh",
            font=("Arial", 10, "bold"),
            bg="#3498db",
            fg="white",
            command=self.refresh_summary
        )
        refresh_btn.pack(pady=10)
        
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
        date_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(date_frame, text="Select Date:", font=("Arial", 11, "bold"), bg="#f0f4f8").pack(side="left", padx=5)
        
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        date_entry = tk.Entry(date_frame, textvariable=self.date_var, font=("Arial", 10), width=15)
        date_entry.pack(side="left", padx=5)
        
        load_btn = tk.Button(
            date_frame,
            text="Load",
            font=("Arial", 10, "bold"),
            bg="#3498db",
            fg="white",
            command=self.load_log_file
        )
        load_btn.pack(side="left", padx=5)
        
        # Log text display
        log_box = tk.Frame(self.logs_frame, bg="white", relief="sunken", bd=2)
        log_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(log_box)
        scrollbar.pack(side="right", fill="y")
        
        self.log_text = tk.Text(
            log_box,
            height=20,
            font=("Courier", 10),
            bg="white",
            fg="#2c3e50",
            yscrollcommand=scrollbar.set
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
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
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tk.Label(list_frame, text="Available Log Files:", font=("Arial", 12, "bold"), bg="#f0f4f8").pack(anchor="w", pady=5)
        
        # Scrollable list
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.log_list = tk.Listbox(
            list_frame,
            font=("Courier", 10),
            bg="white",
            yscrollcommand=scrollbar.set,
            height=15
        )
        self.log_list.pack(fill="both", expand=True, pady=5)
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
