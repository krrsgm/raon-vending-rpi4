import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
import threading
import re
from payment_handler import PaymentHandler
from system_status_panel import SystemStatusPanel
from daily_sales_logger import get_logger
from arduino_serial_utils import detect_arduino_serial_port
try:
    from stock_tracker import get_tracker
    STOCK_TRACKER_AVAILABLE = True
except ImportError:
    STOCK_TRACKER_AVAILABLE = False
    print("[CartScreen] WARNING: stock_tracker not available")


class CartScreen(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg="#f0f4f8")
        self.controller = controller
        self.buyer_info = None  # program/year/section metadata
        self.program_options = [
            "BSEE", "BSEcE", "BSIT", "BETET", "BETELXT", "BETICT", "BETMECT",
            "BETVTEd-ET", "BETVTEd-ELXT", "BETVTEd-ICT-CH", "BETVTEd-ICT-CP",
            "BSCE", "BETCHT", "BSES", "BETCT", "BSME", "BETAT", "BETDMT",
            "BETEMT", "BETHVAC/RT", "BETMT", "BETNDT", "Faculty Member", "Not Applicable"
        ]
        # Initialize payment handler with coin hoppers from config
        # If TB74 is connected to the ESP32 and the ESP32 forwards bill events,
        # enable esp32 proxy mode and supply the serial port or host from config.
        bill_cfg = controller.config.get('hardware', {}).get('bill_acceptor', {}) if isinstance(controller.config, dict) else {}
        configured_bill_serial = bill_cfg.get('serial_port')
        bill_serial = detect_arduino_serial_port(preferred_port=configured_bill_serial)
        bill_baud = bill_cfg.get('baudrate') or bill_cfg.get('serial_baud')
        # TB74 is directly connected to Arduino Uno (not proxied through ESP32)
        # It connects via USB serial (default /dev/ttyUSB0)
        esp32_mode = False  # Disabled: TB74 is on Arduino USB, not ESP32
        
        # Get coin acceptor config
        coin_cfg = controller.config.get('hardware', {}).get('coin_acceptor', {}) if isinstance(controller.config, dict) else {}
        # Default to serial because coin/bill are on Arduino Uno in this wiring layout.
        use_gpio_coin = coin_cfg.get('use_gpio', False)
        coin_gpio_pin = coin_cfg.get('gpio_pin', 17)  # Default GPIO 17
        hopper_cfg = controller.config.get('hardware', {}).get('coin_hopper', {}) if isinstance(controller.config, dict) else {}
        hopper_serial = detect_arduino_serial_port(preferred_port=hopper_cfg.get('serial_port') or bill_serial)
        hopper_baud = hopper_cfg.get('baudrate', 115200)

        self.payment_handler = PaymentHandler(
            controller.config,
            coin_port=bill_serial,
            coin_baud=115200,
            bill_port=bill_serial,
            bill_baud=bill_baud,
            bill_esp32_mode=esp32_mode,
            bill_esp32_serial_port=None,
            bill_esp32_host=None,
            bill_esp32_port=5000,
            coin_hopper_port=hopper_serial,
            coin_hopper_baud=hopper_baud,
            use_gpio_coin=use_gpio_coin,
            coin_gpio_pin=coin_gpio_pin
        )  # Coin/bill/hopper are expected on Arduino Uno serial by default
        self.payment_in_progress = False
        self.payment_received = 0.0
        self.payment_required = 0.0
        self.change_label = None  # Will be created in the payment window
        self.change_progress_label = None  # Live hopper pulse progress in payment window
        self.change_alert_shown = False  # Prevent duplicate hopper timeout alerts
        self.last_change_status = None  # Deduplicate noisy hopper status messages
        self.payment_completion_scheduled = False
        self._complete_after_id = None
        self._return_to_start_after_id = None
        self._payment_complete_notice = None
        self._payment_notice_countdown_after_id = None
        self.coin_received = 0.0  # Track coins separately
        self.bill_received = 0.0  # Track bills separately
        
        # Initialize stock tracker for inventory management
        self.stock_tracker = None
        if STOCK_TRACKER_AVAILABLE:
            try:
                web_app_host = controller.config.get('web_app_host', 'localhost') if isinstance(controller.config, dict) else 'localhost'
                web_app_port = controller.config.get('web_app_port', 5000) if isinstance(controller.config, dict) else 5000
                machine_id = controller.config.get('machine_id', 'RAON-001') if isinstance(controller.config, dict) else 'RAON-001'
                self.stock_tracker = get_tracker(
                    host=web_app_host,
                    port=web_app_port,
                    machine_id=machine_id
                )
                print(f"[CartScreen] Stock tracker initialized: {machine_id} -> {web_app_host}:{web_app_port}")
            except Exception as e:
                print(f"[CartScreen] Failed to initialize stock tracker: {e}")
        
        # --- Colors and Fonts ---
        self.colors = {
            "background": "#f0f4f8",
            "text_fg": "#2c3e50",
            "gray_fg": "#7f8c8d",
            "border": "#dfe6e9",
            "header_bg": "#ffffff",
            "total_fg": "#2a3eb1",
            "payment_bg": "#eaf0ff",
            "payment_fg": "#1f2f85",
            "primary_btn_bg": "#2222a8",
            "primary_btn_hover": "#2f3fc6",
            "secondary_btn_bg": "#4a63d9",
            "secondary_btn_hover": "#5b73e2",
        }
        self.fonts = {
            "header": tkfont.Font(family="Helvetica", size=24, weight="bold"),
            "item_name": tkfont.Font(family="Helvetica", size=16, weight="bold"),
            "item_details": tkfont.Font(family="Helvetica", size=14),
            "total": tkfont.Font(family="Helvetica", size=20, weight="bold"),
            "qty_btn": tkfont.Font(family="Helvetica", size=14, weight="bold"),
            "action_button": tkfont.Font(family="Helvetica", size=18, weight="bold"),
        }
        screen_height = controller.winfo_screenheight()
        self.touch_dead_zone_top_px = 100
        self.touch_dead_zone_bottom_start_px = 1700
        self.touch_dead_zone_bottom_px = max(0, int(screen_height - self.touch_dead_zone_bottom_start_px))

        # --- Header ---
        header = tk.Frame(
            self,
            bg="#2222a8",
            height=max(96, self.touch_dead_zone_top_px + 46),
        )
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Your Cart",
            font=self.fonts["header"],
            bg=header["bg"],
            fg="#ffffff",
        ).pack(pady=(self.touch_dead_zone_top_px, 8))

        # --- Main content area for cart items ---
        self.cart_items_frame = tk.Frame(self, bg=self.colors["background"])
        self.cart_items_frame.pack(fill="both", expand=True, padx=50, pady=(10, 6))

        # --- Footer for totals ---
        footer = tk.Frame(self, bg=self.colors["background"])
        footer.pack(fill="x", padx=50, pady=(0, 10))

        self.total_label = tk.Label(
            footer,
            font=self.fonts["total"],
            bg=footer["bg"],
            fg=self.colors["total_fg"],
        )
        self.total_label.pack(pady=(0, 8))

        # Keep primary actions in lower touchable area (above status zone).
        action_bar = tk.Frame(self, bg=self.colors["background"])
        action_bar.pack(fill="x", padx=50, pady=(0, 10))

        back_button = tk.Button(
            action_bar,
            text="Back to Shopping",
            font=self.fonts["action_button"],
            bg=self.colors["secondary_btn_bg"],
            fg="#ffffff",
            activebackground=self.colors["secondary_btn_hover"],
            activeforeground="#ffffff",
            relief="flat",
            pady=10,
            command=lambda: controller.show_kiosk(),
        )
        back_button.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self._style_button(back_button, hover_bg=self.colors["secondary_btn_hover"])

        self.checkout_button = tk.Button(
            action_bar,
            text="Pay",
            font=self.fonts["action_button"],
            bg=self.colors["primary_btn_bg"],
            fg="#ffffff",
            activebackground=self.colors["primary_btn_hover"],
            activeforeground="#ffffff",
            relief="flat",
            pady=10,
            command=self.handle_checkout,  # Using our new coin payment handler
        )
        self.checkout_button.pack(side="left", expand=True, fill="x", padx=(5, 0))
        self._style_button(self.checkout_button, hover_bg=self.colors["primary_btn_hover"])

        # --- System Status Panel ---
        status_zone_height = self.touch_dead_zone_bottom_px if self.touch_dead_zone_bottom_px > 0 else 120
        self.status_zone = tk.Frame(self, bg="#111111", height=status_zone_height)
        self.status_zone.pack(side="bottom", fill="x")
        self.status_zone.pack_propagate(False)

        self.status_panel = SystemStatusPanel(self.status_zone, controller=self.controller)
        self.status_panel.pack(fill='both', expand=True)

    def _style_button(self, btn, hover_bg=None, hover_fg=None):
        base_bg = btn.cget("bg")
        base_fg = btn.cget("fg")
        btn.configure(
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            cursor="hand2",
            activebackground=hover_bg or base_bg,
            activeforeground=hover_fg or base_fg,
            padx=12,
            pady=10,
        )

        def _on_enter(_event):
            if hover_bg:
                btn.configure(bg=hover_bg)
            if hover_fg:
                btn.configure(fg=hover_fg)

        def _on_leave(_event):
            btn.configure(bg=base_bg, fg=base_fg)

        btn.bind("<Enter>", _on_enter)
        btn.bind("<Leave>", _on_leave)

    def update_cart(self, cart_items):
        # Clear previous items
        for widget in self.cart_items_frame.winfo_children():
            widget.destroy()

        if not cart_items:
            tk.Label(
                self.cart_items_frame,
                text="Your cart is empty.",
                font=self.fonts["item_name"],
                bg=self.colors["background"],
                fg=self.colors["gray_fg"],
            ).pack(pady=50)
            self.total_label.config(text="")
            self.checkout_button.config(state="disabled")
            return

        grand_total = 0
        self.checkout_button.config(state="normal")
        for item_info in cart_items:
            item = item_info["item"]
            quantity = item_info["quantity"]
            total_price = item["price"] * quantity
            grand_total += total_price

            item_frame = tk.Frame(
                self.cart_items_frame,
                bg="white",
                highlightbackground=self.colors["border"],
                highlightthickness=1,
            )
            item_frame.pack(fill="x", pady=5)
            item_frame.grid_columnconfigure(0, weight=1, minsize=360)
            item_frame.grid_columnconfigure(1, weight=0)

            # --- Left side: Name and Price ---
            info_frame = tk.Frame(item_frame, bg="white")
            info_frame.grid(row=0, column=0, padx=15, pady=10, sticky="nsew")
            raw_name = (
                f"{item['name']} (Slot {item.get('_slot_number')})"
                if item.get('_slot_number') is not None
                else item["name"]
            )
            display_name = str(raw_name)
            if len(display_name) > 68:
                display_name = display_name[:65].rstrip() + "..."

            name_label = tk.Label(
                info_frame,
                text=display_name,
                font=self.fonts["item_name"],
                bg="white",
                fg=self.colors["text_fg"],
                anchor="w",
                justify="left",
                wraplength=680,
            )
            name_label.pack(fill="x")

            details_label = tk.Label(
                info_frame,
                text=f"{self.controller.currency_symbol}{item['price']:.2f} each",
                font=self.fonts["item_details"],
                bg="white",
                fg=self.colors["gray_fg"],
                anchor="w",
            )
            details_label.pack(fill="x")

            # --- Right side: Controls and Total ---
            controls_frame = tk.Frame(item_frame, bg="white")
            # Keep action controls lower for easier touch access in cart view.
            controls_frame.grid(row=0, column=1, padx=15, pady=(24, 10), sticky="se")

            # Quantity adjustment
            qty_frame = tk.Frame(controls_frame, bg="white")
            qty_frame.pack(side="left", padx=20, pady=(10, 0))

            decrease_btn = tk.Button(
                qty_frame,
                text="-",
                font=self.fonts["qty_btn"],
                bg=self.colors["background"],
                fg=self.colors["text_fg"],
                relief="flat",
                width=2,
                command=lambda i=item: self.controller.decrease_cart_item_quantity(i),
            )
            decrease_btn.pack(side="left")
            self._style_button(decrease_btn, hover_bg="#dbe4ff")

            qty_label = tk.Label(
                qty_frame,
                text=str(quantity),
                font=self.fonts["item_details"],
                bg="white",
                fg=self.colors["text_fg"],
                width=3,
            )
            qty_label.pack(side="left", padx=5)

            increase_btn = tk.Button(
                qty_frame,
                text="+",
                font=self.fonts["qty_btn"],
                bg=self.colors["background"],
                fg=self.colors["text_fg"],
                relief="flat",
                width=2,
                command=lambda i=item: self.controller.increase_cart_item_quantity(i),
            )
            increase_btn.pack(side="left")
            self._style_button(increase_btn, hover_bg="#dbe4ff")

            # Total price for the item line
            price_label = tk.Label(
                controls_frame,
                text=f"{self.controller.currency_symbol}{total_price:.2f}",
                font=self.fonts["item_name"],
                bg="white",
                fg=self.colors["total_fg"],
                width=12,
                anchor="e",
            )
            price_label.pack(side="left", padx=(12, 20), pady=(10, 0))

            # Delete button
            delete_btn = tk.Button(
                controls_frame,
                text="Remove",
                font=self.fonts["qty_btn"],
                bg="white",
                fg="#e74c3c",
                relief="flat",
                command=lambda i=item: self.controller.remove_from_cart(i),
            )
            delete_btn.pack(side="left", pady=(10, 0))
            self._style_button(delete_btn, hover_bg="#ffe7ea")

        self.total_label.config(
            text=f"Total: {self.controller.currency_symbol}{grand_total:.2f}"
        )

    def _prompt_buyer_info(self):
        """Prompt buyer to select program, year, and section before payment."""
        dialog = tk.Toplevel(self)
        dialog.title("Buyer Info")
        dialog.configure(bg="white")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)
        try:
            dialog.update_idletasks()
            screen_w = dialog.winfo_screenwidth()
            screen_h = dialog.winfo_screenheight()
            dialog.geometry(f"{screen_w}x{screen_h}+0+0")
            dialog.attributes("-fullscreen", True)
            dialog.lift()
            dialog.attributes("-topmost", True)
        except Exception:
            pass

        label_font = ("Helvetica", 15, "bold")
        menu_font = ("Helvetica", 15)
        btn_font = ("Helvetica", 15, "bold")

        # Header with logo and machine name
        header = tk.Frame(dialog, bg="#1d4ed8")
        header.pack(fill="x")
        tk.Label(header, text="RAON VENDING", fg="white", bg="#1d4ed8",
                 font=("Helvetica", 20, "bold")).pack(pady=8)
        tk.Label(dialog, text="Fill the form to generate order number", bg="white", fg="#1d4ed8",
                 font=("Helvetica", 18, "bold")).pack(pady=(8, 6))
        # System status panel if available
        try:
            status_panel = SystemStatusPanel(header, controller=self.controller, compact=True)
            status_panel.pack(fill="x", padx=12, pady=(0, 8))
        except Exception:
            pass

        tk.Label(dialog, text="Select Program / Affiliation", bg="white", fg="#222", font=label_font).pack(pady=(18, 10))
        program_var = tk.StringVar(value=self.program_options[0])
        program_menu = tk.OptionMenu(dialog, program_var, *self.program_options)
        program_menu.config(width=40, font=menu_font)
        program_menu["menu"].configure(font=menu_font)
        program_menu.pack(pady=(0, 14))

        tk.Label(dialog, text="Select Year Level", bg="white", fg="#222", font=label_font).pack(pady=(10, 8))
        year_var = tk.StringVar(value="N/A")
        year_menu = tk.OptionMenu(dialog, year_var, "1", "2", "3", "4", "N/A")
        year_menu.config(width=16, font=menu_font)
        year_menu["menu"].configure(font=menu_font)
        year_menu.pack(pady=(0, 12))

        tk.Label(dialog, text="Select Section", bg="white", fg="#222", font=label_font).pack(pady=(10, 8))
        section_var = tk.StringVar(value="N/A")
        section_menu = tk.OptionMenu(dialog, section_var, "A", "B", "Test", "N/A")
        section_menu.config(width=14, font=menu_font)
        section_menu["menu"].configure(font=menu_font)
        section_menu.pack(pady=(0, 16))

        result = {"confirmed": False}

        def on_ok():
            result["confirmed"] = True
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg="white")
        btn_frame.pack(pady=24)
        ok_btn = tk.Button(btn_frame, text="OK", width=16, height=2, command=on_ok, bg="#1d976c", fg="white", relief="flat", font=btn_font)
        cancel_btn = tk.Button(btn_frame, text="Cancel", width=16, height=2, command=on_cancel, bg="#e0e0e0", fg="#333", relief="flat", font=btn_font)
        ok_btn.grid(row=0, column=0, padx=14)
        cancel_btn.grid(row=0, column=1, padx=14)

        self._style_button(ok_btn, hover_bg="#15805a")
        self._style_button(cancel_btn, hover_bg="#d0d0d0")

        dialog.wait_window(dialog)

        if not result["confirmed"]:
            return None
        return {
            "program": program_var.get().strip(),
            "year": year_var.get().strip(),
            "section": section_var.get().strip()
        }

    def _prompt_issue_report(self, or_number=None):
        """Prompt user to report an issue after transaction."""
        dialog = tk.Toplevel(self)
        dialog.title("Transaction Feedback")
        dialog.configure(bg="white")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)
        try:
            dialog.update_idletasks()
            screen_w = dialog.winfo_screenwidth()
            screen_h = dialog.winfo_screenheight()
            dialog.geometry(f"{screen_w}x{screen_h}+0+0")
            dialog.attributes("-fullscreen", True)
            dialog.lift()
            dialog.attributes("-topmost", True)
        except Exception:
            pass

        label_font = ("Helvetica", 17, "bold")
        menu_font = ("Helvetica", 17)
        btn_font = ("Helvetica", 17, "bold")

        header = tk.Frame(dialog, bg="#1d4ed8")
        header.pack(fill="x")
        tk.Label(header, text="RAON VENDING", fg="white", bg="#1d4ed8",
                 font=("Helvetica", 22, "bold")).pack(pady=8)
        try:
            status_panel = SystemStatusPanel(header, controller=self.controller, compact=True)
            status_panel.pack(fill="x", padx=12, pady=(0, 8))
        except Exception:
            pass

        tk.Label(dialog, text="Did you encounter any issue with this transaction?",
                 bg="white", fg="#222", font=label_font,
                 wraplength=520, justify="center").pack(pady=(14, 16))

        options = [
            "Item not dispensed",
            "Wrong item dispensed",
            "Wrong quantity dispensed",
            "Wrong payment recorded",
            "Payment not recognized",
            "No change",
            "Wrong change",
            "Others"
        ]

        tk.Label(dialog, text="Select the issue (or choose Others):", bg="white", fg="#222", font=label_font).pack(pady=(10, 10))
        issue_var = tk.StringVar(value=options[0])
        opt = tk.OptionMenu(dialog, issue_var, *options)
        opt.config(width=36, font=menu_font)
        opt["menu"].configure(font=menu_font)
        opt.pack(pady=(0, 16))

        result = {"issue": None, "answered": False}

        def on_yes():
            sel = issue_var.get().strip()
            result["issue"] = sel
            result["answered"] = True
            dialog.destroy()

        def on_no():
            result["issue"] = None
            result["answered"] = True
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg="white")
        btn_frame.pack(pady=22)
        yes_btn = tk.Button(btn_frame, text="Yes", width=16, height=2, command=on_yes, bg="#1d976c", fg="white", relief="flat", font=btn_font)
        no_btn = tk.Button(btn_frame, text="No", width=16, height=2, command=on_no, bg="#e0e0e0", fg="#333", relief="flat", font=btn_font)
        yes_btn.grid(row=0, column=0, padx=16)
        no_btn.grid(row=0, column=1, padx=16)
        self._style_button(yes_btn, hover_bg="#15805a")
        self._style_button(no_btn, hover_bg="#d0d0d0")

        dialog.wait_window(dialog)
        if not result["answered"]:
            return None
        return result["issue"]

    def handle_checkout(self):
        """Process the checkout with coin payment using Allan 123A-Pro."""
        if not self.controller.cart:
            return

        # Collect buyer metadata (program/year/section) before payment.
        info = self._prompt_buyer_info()
        if not info:
            return
        self.buyer_info = info

        # Calculate total amount needed
        total_amount = sum(item["item"]["price"] * item["quantity"] for item in self.controller.cart)
        
        if not self.payment_in_progress:
            # Start payment session
            self.payment_in_progress = True
            self.payment_required = total_amount
            self.payment_received = 0.0
            self.change_alert_shown = False
            self.last_change_status = None
            self.payment_completion_scheduled = False
            self._complete_after_id = None
            # Start payment session and register callbacks for immediate updates
            # Pass UI change-status callback so dispensing progress can be shown
            try:
                self.payment_handler.start_payment_session(total_amount, on_payment_update=self._on_payment_update, on_change_update=self.update_change_status)
            except TypeError:
                # Backwards compatibility: older PaymentHandler might not accept on_change_update
                self.payment_handler.start_payment_session(total_amount, on_payment_update=self._on_payment_update)
            
            # Create fullscreen payment status window for kiosk readability.
            self.payment_window = tk.Toplevel(self)
            self.payment_window.title("Insert Payment")
            payment_wraplength = 900
            try:
                self.payment_window.update_idletasks()
                screen_w = self.payment_window.winfo_screenwidth()
                screen_h = self.payment_window.winfo_screenheight()
                self.payment_window.geometry(f"{screen_w}x{screen_h}+0+0")
                self.payment_window.attributes("-fullscreen", True)
                payment_wraplength = max(800, int(screen_w * 0.84))
            except Exception:
                pass
            # Attach to the main toplevel window so focus and touch events work
            parent_toplevel = self.winfo_toplevel()
            try:
                self.payment_window.transient(parent_toplevel)
            except Exception:
                pass
            # Keep it above the fullscreen app and force focus
            try:
                self.payment_window.attributes('-topmost', True)
            except Exception:
                pass
            # Note: modal grabs can interfere with touchscreen events on some systems.
            # Disable grab_set to avoid blocking touch/click events; rely on focused transient window.
            try:
                # self.payment_window.grab_set()  # Disabled for touch compatibility
                print("DEBUG: Payment window opened (grab_set disabled for touch compatibility)")
            except Exception:
                pass
            try:
                self.payment_window.focus_force()
                self.payment_window.focus_set()
            except Exception:
                pass

            # Ensure the window close button triggers cancellation
            try:
                self.payment_window.protocol("WM_DELETE_WINDOW", self.cancel_payment)
            except Exception:
                pass

            # Bind ESC key to cancel payment
            self.payment_window.bind('<Escape>', lambda e: self.cancel_payment())
            
            # Styling
            self.payment_window.configure(bg=self.colors["payment_bg"])
            big_title_font = tkfont.Font(family="Helvetica", size=32, weight="bold")
            big_amount_font = tkfont.Font(family="Helvetica", size=54, weight="bold")
            big_status_font = tkfont.Font(family="Helvetica", size=24)
            section_title_font = tkfont.Font(family="Helvetica", size=20, weight="bold")
            item_list_font = tkfont.Font(family="Helvetica", size=18)

            header_bar = tk.Frame(self.payment_window, bg="#2222a8", height=96)
            header_bar.pack(fill="x")
            header_bar.pack_propagate(False)
            tk.Label(
                header_bar,
                text="Insert Payment",
                font=big_title_font,
                bg="#2222a8",
                fg="white"
            ).pack(pady=18)

            # Amount required
            amount_frame = tk.Frame(self.payment_window, bg=self.colors["payment_bg"])
            amount_frame.pack(fill="x", pady=(30, 0))
            
            tk.Label(
                amount_frame,
                text="Amount Required:",
                font=big_title_font,
                bg=self.colors["payment_bg"],
                fg=self.colors["text_fg"]
            ).pack()
            
            tk.Label(
                amount_frame,
                text=f"{self.controller.currency_symbol}{total_amount:.2f}",
                font=big_amount_font,
                bg=self.colors["payment_bg"],
                fg=self.colors["payment_fg"]
            ).pack()
            
            # Payment status
            status_frame = tk.Frame(self.payment_window, bg=self.colors["payment_bg"])
            status_frame.pack(fill="x", pady=20)
            
            self.payment_status = tk.Label(
                status_frame,
                text="Coins: {0}0.00 | Bills: {0}0.00\nTotal Received: {0}0.00\nRemaining: {0}{1:.2f}".format(self.controller.currency_symbol, total_amount),
                font=big_status_font,
                bg=self.colors["payment_bg"],
                fg=self.colors["payment_fg"],
                justify=tk.LEFT,
                anchor='w',
                wraplength=payment_wraplength
            )
            self.payment_status.pack()

            self.cancel_warning_label = tk.Label(
                status_frame,
                text="Warning: Canceling will NOT return inserted coins or bills.",
                font=tkfont.Font(family="Helvetica", size=18, weight="bold"),
                bg=self.colors["payment_bg"],
                fg="#c0392b",
                justify=tk.LEFT,
                anchor='w',
                wraplength=payment_wraplength
            )
            self.cancel_warning_label.pack(pady=(10, 0))

            # Options (placed higher for easier touch access)
            options_frame = tk.Frame(self.payment_window, bg=self.colors["payment_bg"])
            options_frame.pack(fill="x", padx=36, pady=(8, 12))

            back_btn = tk.Button(
                options_frame,
                text="Back to Shopping",
                font=section_title_font,
                command=self.back_to_shopping_from_payment,
                bg=self.colors["primary_btn_bg"],
                fg="#ffffff",
                activebackground=self.colors["primary_btn_hover"],
                activeforeground="#ffffff",
                relief="flat"
            )
            back_btn.pack(side="left", expand=True, fill="x", padx=(0, 8))
            self._style_button(back_btn, hover_bg=self.colors["primary_btn_hover"])

            cancel_btn = tk.Button(
                options_frame,
                text="Cancel Payment",
                font=section_title_font,
                command=self.confirm_cancel_payment,
                bg=self.colors["secondary_btn_bg"],
                fg="#ffffff",
                activebackground=self.colors["secondary_btn_hover"],
                activeforeground="#ffffff",
                relief="flat"
            )
            cancel_btn.pack(side="left", expand=True, fill="x", padx=(8, 0))
            self._style_button(cancel_btn, hover_bg=self.colors["secondary_btn_hover"])
            
            # Change status (initially hidden)
            self.change_label = tk.Label(
                status_frame,
                text="",
                font=section_title_font,
                bg=self.colors["payment_bg"],
                fg=self.colors["payment_fg"]
            )
            self.change_label.pack_forget()  # Hidden until change is dispensed

            self.change_progress_label = tk.Label(
                status_frame,
                text="",
                font=tkfont.Font(family="Helvetica", size=18),
                bg=self.colors["payment_bg"],
                fg=self.colors["text_fg"],
                justify=tk.LEFT,
                anchor='w'
            )
            self.change_progress_label.pack_forget()  # Hidden until first pulse update
            
            # Accepted coins info
            tk.Label(
                self.payment_window,
                text="Accepted Payment Methods:",
                font=section_title_font,
                bg=self.colors["payment_bg"],
                fg=self.colors["text_fg"]
            ).pack(pady=(12, 5))
            
            coins_text = (
                f"Coins: {self.controller.currency_symbol}1, {self.controller.currency_symbol}5, {self.controller.currency_symbol}10 (Old and New)\n"
                f"Bills: {self.controller.currency_symbol}20, {self.controller.currency_symbol}50, {self.controller.currency_symbol}100"
            )
            
            tk.Label(
                self.payment_window,
                text=coins_text,
                font=tkfont.Font(family="Helvetica", size=16),
                bg=self.colors["payment_bg"],
                fg=self.colors["text_fg"],
                justify=tk.LEFT,
                wraplength=payment_wraplength,
                anchor='w'
            ).pack()

            # Items to be paid (uses lower available space in fullscreen mode).
            items_section = tk.Frame(self.payment_window, bg=self.colors["payment_bg"])
            items_section.pack(fill="both", expand=True, padx=36, pady=(18, 8))

            tk.Label(
                items_section,
                text="Items to be Paid:",
                font=section_title_font,
                bg=self.colors["payment_bg"],
                fg=self.colors["text_fg"],
                anchor="w"
            ).pack(fill="x", pady=(0, 6))

            items_list_lines = []
            for entry in self.controller.cart:
                item_data = entry.get("item", {})
                item_name = item_data.get("name", "Unknown Item")
                qty = int(entry.get("quantity", 0) or 0)
                unit_price = float(item_data.get("price", 0.0) or 0.0)
                line_total = qty * unit_price
                slot_no = item_data.get("_slot_number")
                slot_text = f" (Slot {slot_no})" if slot_no is not None else ""
                items_list_lines.append(
                    f"- {item_name}{slot_text}  x{qty}  =  {self.controller.currency_symbol}{line_total:.2f}"
                )

            items_text = "\n".join(items_list_lines) if items_list_lines else "- No items in cart"
            self.payment_items_label = tk.Label(
                items_section,
                text=items_text,
                font=item_list_font,
                bg="#ffffff",
                fg=self.colors["text_fg"],
                justify="left",
                anchor="nw",
                wraplength=max(760, payment_wraplength),
                padx=16,
                pady=12,
                relief="solid",
                bd=1
            )
            self.payment_items_label.pack(fill="both", expand=True)
            
            # Start updating payment status
            self.update_payment_status(total_amount)
            
            # Handle window close button
            self.payment_window.protocol("WM_DELETE_WINDOW", self.cancel_payment)
            
        else:
            self.complete_payment()
    
    def update_payment_status(self, total_amount):
        """Update the payment status window with current coin and bill totals"""
        if self.payment_in_progress:
            received = self.payment_handler.get_current_amount()
            
            # Get individual amounts with proper None checks
            coin_amount = 0.0
            if self.payment_handler.coin_acceptor:
                try:
                    coin_amount = self.payment_handler.coin_acceptor.get_received_amount()
                except Exception as e:
                    print(f"[CartScreen] Error getting coin amount: {e}")
            
            bill_amount = 0.0
            if self.payment_handler.bill_acceptor:
                try:
                    bill_amount = self.payment_handler.bill_acceptor.get_received_amount()
                except Exception as e:
                    print(f"[CartScreen] Error getting bill amount: {e}")
            
            if received != self.payment_received:  # Only update if amount changed
                self.payment_received = received
                self.coin_received = coin_amount
                self.bill_received = bill_amount
                remaining = total_amount - received
                
                if remaining >= 0:
                    remaining_text = f"Remaining: {self.controller.currency_symbol}{remaining:.2f}"
                else:
                    remaining_text = f"Change Due: {self.controller.currency_symbol}{abs(remaining):.2f}"
                
                status_text = (
                    f"Coins: {self.controller.currency_symbol}{coin_amount:.2f} | Bills: {self.controller.currency_symbol}{bill_amount:.2f}\n"
                    f"Total Received: {self.controller.currency_symbol}{received:.2f}\n"
                    f"{remaining_text}"
                )
                
                self.payment_status.config(text=status_text)
                if received > 0:
                    self.cancel_warning_label.config(
                        text=(
                            "Warning: Canceling will NOT return inserted "
                            "coins or bills."
                        )
                    )
                
                if received >= total_amount:
                    self._schedule_complete_payment()
                    return
                    
            # Update every 100ms while payment is in progress
            self.after(100, lambda: self.update_payment_status(total_amount))

    def _schedule_complete_payment(self, delay_ms=120):
        """Schedule payment completion once, allowing UI to show the final inserted amount."""
        if self.payment_completion_scheduled or not self.payment_in_progress:
            return
        self.payment_completion_scheduled = True

        def _run_complete():
            self._complete_after_id = None
            if self.payment_in_progress:
                self.complete_payment()

        try:
            self._complete_after_id = self.after(delay_ms, _run_complete)
        except Exception:
            _run_complete()

    def _on_payment_update(self, amount):
        """Callback invoked by PaymentHandler when coins/bills change (push notification).

        The handler passes the combined received amount. Schedule UI update on the
        main thread using `after(0, ...)` so Tkinter updates are safe.
        """
        if not self.payment_in_progress:
            return

        coin_amount = 0.0
        try:
            if self.payment_handler.coin_acceptor:
                coin_amount = self.payment_handler.coin_acceptor.get_received_amount()
        except Exception as e:
            print(f"[PAYMENT] Error getting coin amount: {e}")
            coin_amount = 0.0
        
        bill_amount = 0.0
        try:
            if self.payment_handler.bill_acceptor:
                bill_amount = self.payment_handler.bill_acceptor.get_received_amount()
        except Exception as e:
            print(f"[PAYMENT] Error getting bill amount: {e}")
            bill_amount = 0.0

        # Prepare UI values
        self.payment_received = amount
        self.coin_received = coin_amount
        self.bill_received = bill_amount
        remaining = self.payment_required - amount

        if remaining >= 0:
            remaining_text = f"Remaining: {self.controller.currency_symbol}{remaining:.2f}"
        else:
            remaining_text = f"Change Due: {self.controller.currency_symbol}{abs(remaining):.2f}"

        status_text = (
            f"Coins: {self.controller.currency_symbol}{coin_amount:.2f} | Bills: {self.controller.currency_symbol}{bill_amount:.2f}\n"
            f"Total Received: {self.controller.currency_symbol}{amount:.2f}\n"
            f"{remaining_text}"
        )

        print(f"[PAYMENT UPDATE] Coins: {coin_amount}, Bills: {bill_amount}, Total: {amount}, Required: {self.payment_required}")

        # Schedule UI work on the main thread
        def _apply_update():
            try:
                self.payment_status.config(text=status_text)
                if amount > 0 and getattr(self, "cancel_warning_label", None):
                    self.cancel_warning_label.config(
                        text=(
                            "Warning: Canceling will NOT return inserted "
                            "coins or bills."
                        )
                    )
            except Exception as e:
                print(f"[PAYMENT] Error updating UI: {e}")

            if amount >= self.payment_required:
                print(f"[PAYMENT] Payment complete threshold reached: {amount} >= {self.payment_required}")
                self._schedule_complete_payment()

        try:
            self.after(0, _apply_update)
        except Exception as e:
            print(f"[PAYMENT] Error scheduling UI update: {e}")

    def update_change_status(self, message):
        """Update the change dispensing status display."""
        def _apply_change_status():
            # Ignore repeated identical messages to avoid UI flicker.
            if message == self.last_change_status:
                return
            self.last_change_status = message

            if self.change_label:
                self.change_label.config(text=message)
                self.change_label.pack()  # Make visible
            # Show parsed live pulse progress (x/y) from hopper callback lines.
            if self.change_progress_label:
                pulse_match = re.search(r'PULSE\s+(ONE|FIVE)\s+(\d+)\s*/\s*(\d+)', str(message), re.IGNORECASE)
                if pulse_match:
                    denom = pulse_match.group(1).upper()
                    current = pulse_match.group(2)
                    target = pulse_match.group(3)
                    value = f"{self.controller.currency_symbol}1" if denom == "ONE" else f"{self.controller.currency_symbol}5"
                    self.change_progress_label.config(
                        text=f"Dispense progress ({value}): {current}/{target}"
                    )
                    self.change_progress_label.pack()
                else:
                    upper = str(message).upper()
                    if "CHANGE DISPENSED" in upper:
                        self.change_progress_label.config(text="Dispense progress: Completed")
                        self.change_progress_label.pack()
                    elif "ERROR" in upper or "NO COIN" in upper or "TIMEOUT" in upper:
                        self.change_progress_label.config(text="Dispense progress: Stopped")
                        self.change_progress_label.pack()

            # Show explicit alert when hopper reports no-coin timeout.
            if message and not self.change_alert_shown:
                upper = message.upper()
                if "NO COIN" in upper and "TIMEOUT" in upper:
                    self.change_alert_shown = True
                    try:
                        messagebox.showwarning("Change Hopper Alert", message)
                    except Exception:
                        pass
            # Force redraw so change status is visible during synchronous dispense loop.
            try:
                if self.payment_window and self.payment_window.winfo_exists():
                    self.payment_window.update_idletasks()
            except Exception:
                pass

        try:
            # If callback runs on UI thread (common during stop_payment_session),
            # apply immediately so status is not delayed until after window closes.
            if threading.current_thread() is threading.main_thread():
                _apply_change_status()
            else:
                self.after(0, _apply_change_status)
        except Exception:
            _apply_change_status()

    def complete_payment(self):
        """Complete the payment process and dispense items & change"""
        if not self.payment_in_progress:
            return
             
        self.payment_in_progress = False
        self.payment_completion_scheduled = False
        if self._complete_after_id:
            try:
                self.after_cancel(self._complete_after_id)
            except Exception:
                pass
            self._complete_after_id = None

        thread_args = (
            self.payment_required,
            list(self.controller.cart),
            self.coin_received,
            self.bill_received,
            self.buyer_info
        )
        threading.Thread(target=self._complete_payment_thread, args=thread_args, daemon=True).start()

    def _complete_payment_thread(self, required_amount, cart_snapshot, coin_amount, bill_amount, buyer_info):
        try:
            received, change_dispensed, change_status = self.payment_handler.stop_payment_session(
                required_amount=required_amount
            )
        except Exception as e:
            # Never leave payment UI hanging if hardware/session finalization fails.
            try:
                print(f"[CartScreen] ERROR during stop_payment_session: {e}")
            except Exception:
                pass
            received = self.payment_received
            change_dispensed = 0
            change_status = f"Error finalizing payment: {e}"
        self.after(0, lambda: self._present_payment_complete(
            required_amount,
            received,
            change_dispensed,
            change_status,
            cart_snapshot,
            coin_amount,
            bill_amount,
            None,
            buyer_info
        ))

    def _present_payment_complete(self, required_amount, received, change_dispensed,
                                  change_status, cart_snapshot, coin_amount, bill_amount, or_number=None, buyer_info=None):
        try:
            vend_list = [ {"item": it["item"], "quantity": it["quantity"]} for it in cart_snapshot ]
        except Exception:
            vend_list = []

        def _vend_items():
            try:
                # Use organized vending so slots are processed in ascending order,
                # finishing all pulses for the current slot before the next one.
                self.controller.vend_cart_items_organized(vend_list)
            except Exception as e:
                print(f"Error in vending thread: {e}")

        try:
            threading.Thread(target=_vend_items, daemon=True).start()
        except Exception:
            pass

        change_due = max(0.0, float(received) - float(required_amount))
        # Track actual dispensed change in coin inventory for admin monitoring.
        try:
            if float(change_dispensed) > 0 and hasattr(self.controller, "record_change_dispensed"):
                self.controller.record_change_dispensed(change_dispensed)
        except Exception as e:
            print(f"[CartScreen] Failed to record change dispense in coin stock: {e}")

        status_text = (
            "Thank you!\n\n"
            f"Coins received: {self.controller.currency_symbol}{coin_amount:.2f}\n"
            f"Bills received: {self.controller.currency_symbol}{bill_amount:.2f}\n"
            f"Total paid: {self.controller.currency_symbol}{received:.2f}\n"
            "\nYour items will now be dispensed."
        )
        if change_due > 0:
            status_text += (
                f"\n\nChange due: {self.controller.currency_symbol}{change_due:.2f}\n"
                f"Change dispensed: {self.controller.currency_symbol}{float(change_dispensed):.2f}"
            )
            if change_status:
                status_text += f"\n{change_status}"
                upper = str(change_status).upper()
                if (not self.change_alert_shown) and ("NO COIN" in upper and "TIMEOUT" in upper):
                    self.change_alert_shown = True
                    try:
                        messagebox.showwarning("Change Hopper Alert", change_status)
                    except Exception:
                        pass

        self._destroy_payment_window()

        def _extract_cart_entry_name_and_qty(entry):
            """Normalize cart entry shapes to (item_name, quantity)."""
            if not isinstance(entry, dict):
                return "Unknown", 1
            qty = entry.get('quantity', 1)
            try:
                qty = int(qty)
            except Exception:
                qty = 1
            if qty <= 0:
                qty = 1
            item_obj = entry.get('item') if isinstance(entry.get('item'), dict) else None
            item_name = (item_obj or entry).get('name') if isinstance((item_obj or entry), dict) else None
            if not item_name:
                item_name = "Unknown"
            return item_name, qty
        
        or_number_value = or_number
        # Log the transaction to daily sales log
        try:
            logger = get_logger()
            items_to_log = []
            for item in cart_snapshot:
                item_name, qty = _extract_cart_entry_name_and_qty(item)
                items_to_log.append({
                    'name': item_name,
                    'quantity': qty
                })
            or_number_logged = logger.log_transaction(
                items_list=items_to_log,
                coin_amount=coin_amount,
                bill_amount=bill_amount,
                change_dispensed=change_dispensed,
                buyer_program=buyer_info.get("program") if isinstance(buyer_info, dict) else None,
                buyer_year=buyer_info.get("year") if isinstance(buyer_info, dict) else None,
                buyer_section=buyer_info.get("section") if isinstance(buyer_info, dict) else None,
                or_number=or_number_value
            )
            if not or_number_value and or_number_logged:
                or_number_value = or_number_logged
        except Exception as e:
            print(f"[CartScreen] Error logging transaction: {e}")
        
        # Record sales in stock tracker for inventory management and alerts
        if self.stock_tracker:
            try:
                for item in cart_snapshot:
                    item_name, qty = _extract_cart_entry_name_and_qty(item)
                    
                    result = self.stock_tracker.record_sale(
                        item_name=item_name,
                        quantity=qty,
                        coin_amount=coin_amount,
                        bill_amount=bill_amount,
                        change_dispensed=change_dispensed
                    )
                    
                    if not result['success']:
                        print(f"[CartScreen] Failed to record sale for {item_name}: {result['message']}")
                    elif result['alert']:
                        alert_msg = result['alert'].get('message', 'Stock low')
                        print(f"[CartScreen] STOCK ALERT: {alert_msg}")
                        messagebox.showwarning('Stock Alert', alert_msg)
                    else:
                        print(f"[CartScreen] Sale recorded for {item_name} (qty: {qty})")
            except Exception as e:
                print(f"[CartScreen] Error recording sales in stock tracker: {e}")

        if or_number_value:
            status_text += f"\n\nOR: {or_number_value}"

        def _after_vend():
            try:
                self.controller.apply_cart_stock_deductions(cart_snapshot)
            except Exception as e:
                print(f"[CartScreen] Error applying stock deductions: {e}")

            # Prompt for post-transaction issue report (optional)
            try:
                issue = self._prompt_issue_report(or_number_value)
                if issue:
                    logger = get_logger()
                    logger.log_event(
                        "ISSUE",
                        f"OR: {or_number_value or 'N/A'} | Issue: {issue}"
                    )
            except Exception as e:
                print(f"[CartScreen] Error capturing issue report: {e}")

            # Reset buyer info after successful transaction
            self.buyer_info = None
            
            # Clear cart and return to kiosk screen
            self.controller.clear_cart()
            # Do not auto-timeout; leave notice until issue prompt/OK is handled.
            self._show_payment_complete_notice(status_text, auto_return_ms=None)

        def _vend_items_and_finish():
            try:
                # Use organized vending so slots are processed in ascending order.
                self.controller.vend_cart_items_organized(vend_list)
            except Exception as e:
                print(f"Error in vending thread: {e}")
            finally:
                try:
                    self.after(0, _after_vend)
                except Exception:
                    _after_vend()

        try:
            threading.Thread(target=_vend_items_and_finish, daemon=True).start()
        except Exception:
            _after_vend()
        
        # Prompt for post-transaction issue report (optional)
        try:
            issue = self._prompt_issue_report(or_number_value)
            if issue:
                logger = get_logger()
                logger.log_event(
                    "ISSUE",
                    f"OR: {or_number_value or 'N/A'} | Issue: {issue}"
                )
        except Exception as e:
            print(f"[CartScreen] Error capturing issue report: {e}")
        
        # Reset buyer info after successful transaction
        self.buyer_info = None
        
        # Clear cart and return to kiosk screen
        self.controller.clear_cart()
        try:
            self.controller.finish_order_timer(status="SUCCESS")
        except Exception:
            pass
        self._show_payment_complete_notice(status_text, auto_return_ms=10000)
        self._schedule_return_to_start_order(delay_ms=10000)

    def _cancel_scheduled_return_to_start_order(self):
        """Cancel pending delayed navigation to Start Order, if any."""
        if self._return_to_start_after_id:
            try:
                self.after_cancel(self._return_to_start_after_id)
            except Exception:
                pass
            self._return_to_start_after_id = None

    def _destroy_payment_complete_notice(self):
        """Close payment-complete popup and cancel its countdown updates."""
        if self._payment_notice_countdown_after_id:
            try:
                self.after_cancel(self._payment_notice_countdown_after_id)
            except Exception:
                pass
            self._payment_notice_countdown_after_id = None
        if self._payment_complete_notice:
            try:
                self._payment_complete_notice.destroy()
            except Exception:
                pass
            self._payment_complete_notice = None

    def _show_payment_complete_notice(self, status_text, auto_return_ms=10000):
        """Show a non-blocking completion popup while waiting for auto-return."""
        self._destroy_payment_complete_notice()

        popup = tk.Toplevel(self)
        self._payment_complete_notice = popup
        popup.title("Payment Complete")
        popup.configure(bg=self.colors["payment_bg"])
        try:
            popup.attributes("-topmost", True)
        except Exception:
            pass
        try:
            popup.protocol("WM_DELETE_WINDOW", lambda: None)
        except Exception:
            pass

        try:
            popup.update_idletasks()
            screen_w = popup.winfo_screenwidth()
            screen_h = popup.winfo_screenheight()
            popup.geometry(f"{screen_w}x{screen_h}+0+0")
            popup.attributes("-fullscreen", True)
        except Exception:
            pass

        header = tk.Frame(popup, bg="#1d4ed8")
        header.pack(fill="x")
        tk.Label(header, text="RAON VENDING", fg="white", bg="#1d4ed8",
                 font=("Helvetica", 24, "bold")).pack(pady=8)
        try:
            status_panel = SystemStatusPanel(header, controller=self.controller, compact=True)
            status_panel.pack(fill="x", padx=12, pady=(0, 8))
        except Exception:
            pass

        tk.Label(
            popup,
            text="Payment Complete",
            font=("Helvetica", 28, "bold"),
            bg=self.colors["payment_bg"],
            fg=self.colors["payment_fg"],
        ).pack(pady=(24, 12))

        tk.Label(
            popup,
            text=status_text,
            font=tkfont.Font(family="Helvetica", size=18, weight="bold"),
            bg=self.colors["payment_bg"],
            fg=self.colors["text_fg"],
            justify=tk.LEFT,
            wraplength=max(900, int(screen_w * 0.85)) if 'screen_w' in locals() else 900,
            anchor="w",
        ).pack(fill="both", expand=True, padx=32, pady=(0, 16))

        countdown_label = tk.Label(
            popup,
            text="",
            font=tkfont.Font(family="Helvetica", size=16, weight="bold"),
            bg=self.colors["payment_bg"],
            fg=self.colors["payment_fg"],
        )
        countdown_label.pack(pady=(0, 8))

        if auto_return_ms is not None and auto_return_ms > 0:
            remaining_sec = max(1, int(auto_return_ms / 1000))
        else:
            remaining_sec = None

        def _tick():
            nonlocal remaining_sec
            if not self._payment_complete_notice or not self._payment_complete_notice.winfo_exists():
                self._payment_notice_countdown_after_id = None
                return
            if remaining_sec is None:
                countdown_label.config(text="Press the home button to start a new order.")
                self._payment_notice_countdown_after_id = None
                return
            countdown_label.config(text=f"Returning to Start Order in {remaining_sec} second(s)...")
            if remaining_sec <= 1:
                self._payment_notice_countdown_after_id = None
                return
            remaining_sec -= 1
            self._payment_notice_countdown_after_id = self.after(1000, _tick)

        if remaining_sec is not None:
            _tick()

    def _go_start_order_now(self):
        """Navigate immediately to Start Order and clear pending auto-return state."""
        self._cancel_scheduled_return_to_start_order()
        self._destroy_payment_complete_notice()
        try:
            self.controller.show_start_order()
        except Exception:
            pass

    def _schedule_return_to_start_order(self, delay_ms=10000):
        """Auto-return to Start Order after payment completion."""
        self._cancel_scheduled_return_to_start_order()

        def _go_start_order():
            self._return_to_start_after_id = None
            self._go_start_order_now()

        try:
            self._return_to_start_after_id = self.after(int(delay_ms), _go_start_order)
        except Exception:
            _go_start_order()

    def _destroy_payment_window(self):
        """Safely destroy the payment status window."""
        if hasattr(self, 'payment_window') and self.payment_window:
            try:
                self.payment_window.destroy()
            except Exception:
                pass
            finally:
                self.payment_window = None

    def back_to_shopping_from_payment(self):
        """Stop payment flow and return to kiosk shopping screen."""
        self._cancel_payment_and_route(route="kiosk")

    def confirm_cancel_payment(self):
        """Ask for confirmation before canceling payment."""
        try:
            proceed = messagebox.askyesno(
                "Confirm Cancel",
                "Are you sure you want to cancel payment?",
                parent=getattr(self, "payment_window", None),
            )
        except Exception:
            proceed = True
        if proceed:
            self._cancel_payment_and_route(route="start_order")

    def cancel_payment(self, event=None):
        """Stop payment flow and return to start order screen."""
        self._cancel_payment_and_route(route="start_order")

    def _cancel_payment_and_route(self, route="start_order"):
        """Cancel the current payment session.

        This correctly handles the tuple returned by
        PaymentHandler.stop_payment_session() which is
        (total_received, change_amount, change_status).
        The method will always close the payment window (if present)
        and return the UI to the kiosk screen.
        """
        # Debug: log cancellation attempt
        try:
            print(f"DEBUG: cancel_payment called, route={route}, payment_in_progress={self.payment_in_progress}")
        except Exception:
            pass

        # Ensure payment flag is reset even if exception occurs
        try:
            self._cancel_scheduled_return_to_start_order()
            self._destroy_payment_complete_notice()
            self.payment_completion_scheduled = False
            if self._complete_after_id:
                try:
                    self.after_cancel(self._complete_after_id)
                except Exception:
                    pass
                self._complete_after_id = None
            # If a payment was in progress, stop it and handle returned tuple
            if self.payment_in_progress:
                try:
                    total_received, change_amount, change_status = self.payment_handler.stop_payment_session()
                except Exception:
                    # Defensive: if the payment handler API changes or errors,
                    # fall back to a safe default
                    total_received = 0
                    change_amount = 0
                    change_status = ""
        finally:
            # Always reset the flag
            self.payment_in_progress = False

        # Ensure the payment window is closed and return to kiosk
        self._destroy_payment_window()

        try:
            self.controller.finish_order_timer(status="CANCELLED")
        except Exception:
            pass

        # Navigate based on selected option without extra prompt.
        try:
            if route == "kiosk":
                self.controller.show_kiosk()
            else:
                self.controller.show_start_order()
            try:
                self.controller.focus_force()
            except Exception:
                pass
        except Exception:
            pass
                
    def on_closing(self):
        """Handle cleanup when closing"""
        if hasattr(self, 'payment_handler'):
            self.payment_handler.cleanup()



