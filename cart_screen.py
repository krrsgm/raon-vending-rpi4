import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
from payment_handler import PaymentHandler
from system_status_panel import SystemStatusPanel
from daily_sales_logger import get_logger
import threading


class CartScreen(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg="#f0f4f8")
        self.controller = controller
        # Initialize payment handler with coin hoppers from config
        # If TB74 is connected to the ESP32 and the ESP32 forwards bill events,
        # enable esp32 proxy mode and supply the serial port or host from config.
        bill_cfg = controller.config.get('hardware', {}).get('bill_acceptor', {}) if isinstance(controller.config, dict) else {}
        # Default to /dev/ttyACM0 for USB-connected Arduino Uno; can be overridden in config
        bill_serial = bill_cfg.get('serial_port', '/dev/ttyACM0')
        bill_baud = bill_cfg.get('baudrate') or bill_cfg.get('serial_baud')
        # TB74 is directly connected to Arduino Uno (not proxied through ESP32)
        # It connects via USB at /dev/ttyACM0
        esp32_mode = False  # Disabled: TB74 is on Arduino USB, not ESP32
        
        # Get coin acceptor config (prefer GPIO on Raspberry Pi)
        coin_cfg = controller.config.get('hardware', {}).get('coin_acceptor', {}) if isinstance(controller.config, dict) else {}
        use_gpio_coin = coin_cfg.get('use_gpio', True)  # Default to GPIO on RPi
        coin_gpio_pin = coin_cfg.get('gpio_pin', 17)  # Default GPIO 17
        
        self.payment_handler = PaymentHandler(
            controller.config,
            coin_port=None,  # Auto-detect ESP32 USB serial port (fallback)
            coin_baud=115200,
            bill_port=bill_serial,
            bill_baud=bill_baud,
            bill_esp32_mode=esp32_mode,
            bill_esp32_serial_port=None,
            bill_esp32_host=None,
            bill_esp32_port=5000,
            use_gpio_coin=use_gpio_coin,
            coin_gpio_pin=coin_gpio_pin
        )  # Using GPIO coin acceptor on RPi
        self.payment_in_progress = False
        self.payment_received = 0.0
        self.payment_required = 0.0
        self.change_label = None  # Will be created in the payment window
        self.coin_received = 0.0  # Track coins separately
        self.bill_received = 0.0  # Track bills separately
        
        # --- Colors and Fonts ---
        self.colors = {
            "background": "#f0f4f8",
            "text_fg": "#2c3e50",
            "gray_fg": "#7f8c8d",
            "border": "#dfe6e9",
            "header_bg": "#ffffff",
            "total_fg": "#27ae60",
            "payment_bg": "#e8f5e9",
            "payment_fg": "#2e7d32",
        }
        self.fonts = {
            "header": tkfont.Font(family="Helvetica", size=24, weight="bold"),
            "item_name": tkfont.Font(family="Helvetica", size=16, weight="bold"),
            "item_details": tkfont.Font(family="Helvetica", size=14),
            "total": tkfont.Font(family="Helvetica", size=20, weight="bold"),
            "qty_btn": tkfont.Font(family="Helvetica", size=14, weight="bold"),
            "action_button": tkfont.Font(family="Helvetica", size=18, weight="bold"),
        }

        # --- Header ---
        header = tk.Frame(
            self,
            bg=self.colors["header_bg"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
        )
        header.pack(fill="x", pady=(0, 10))
        tk.Label(
            header,
            text="Your Cart",
            font=self.fonts["header"],
            bg=header["bg"],
            fg=self.colors["text_fg"],
        ).pack(pady=20)

        # --- Main content area for cart items ---
        self.cart_items_frame = tk.Frame(self, bg=self.colors["background"])
        self.cart_items_frame.pack(fill="both", expand=True, padx=50)

        # --- Footer for totals and buttons ---
        footer = tk.Frame(self, bg=self.colors["background"])
        footer.pack(fill="x", padx=50, pady=20)

        self.total_label = tk.Label(
            footer,
            font=self.fonts["total"],
            bg=footer["bg"],
            fg=self.colors["total_fg"],
        )
        self.total_label.pack(pady=(0, 20))

        action_frame = tk.Frame(footer, bg=self.colors["background"])
        action_frame.pack(fill="x")

        back_button = tk.Button(
            action_frame,
            text="Back to Shopping",
            font=self.fonts["action_button"],
            bg=self.colors["gray_fg"],
            fg=self.colors["background"],
            relief="flat",
            pady=10,
            command=lambda: controller.show_kiosk(),
        )
        back_button.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.checkout_button = tk.Button(
            action_frame,
            text="Pay",
            font=self.fonts["action_button"],
            bg=self.colors["total_fg"],
            fg=self.colors["background"],
            relief="flat",
            pady=10,
            command=self.handle_checkout,  # Using our new coin payment handler
        )
        self.checkout_button.pack(side="left", expand=True, fill="x", padx=(5, 0))

        # --- System Status Panel ---
        self.status_panel = SystemStatusPanel(self, controller=self.controller)
        self.status_panel.pack(side='bottom', fill='x')

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
            item_frame.grid_columnconfigure(1, weight=1)

            # --- Left side: Name and Price ---
            info_frame = tk.Frame(item_frame, bg="white")
            info_frame.grid(row=0, column=0, padx=15, pady=10, sticky="nw")

            name_label = tk.Label(
                info_frame,
                text=item["name"],
                font=self.fonts["item_name"],
                bg="white",
                fg=self.colors["text_fg"],
                anchor="w",
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
            controls_frame.grid(row=0, column=1, padx=15, pady=10, sticky="nse")

            # Quantity adjustment
            qty_frame = tk.Frame(controls_frame, bg="white")
            qty_frame.pack(side="left", padx=20)

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

            # Total price for the item line
            price_label = tk.Label(
                controls_frame,
                text=f"{self.controller.currency_symbol}{total_price:.2f}",
                font=self.fonts["item_name"],
                bg="white",
                fg=self.colors["text_fg"],
                width=10,
                anchor="e",
            )
            price_label.pack(side="left", padx=20)

            # Delete button
            delete_btn = tk.Button(
                controls_frame,
                text="✕",
                font=self.fonts["qty_btn"],
                bg="white",
                fg="#e74c3c",
                relief="flat",
                command=lambda i=item: self.controller.remove_from_cart(i),
            )
            delete_btn.pack(side="left")

        self.total_label.config(
            text=f"Total: {self.controller.currency_symbol}{grand_total:.2f}"
        )

    def handle_checkout(self):
        """Process the checkout with coin payment using Allan 123A-Pro."""
        if not self.controller.cart:
            return

        # Calculate total amount needed
        total_amount = sum(item["item"]["price"] * item["quantity"] for item in self.controller.cart)
        
        if not self.payment_in_progress:
            # Start payment session
            self.payment_in_progress = True
            self.payment_required = total_amount
            self.payment_received = 0.0
            # Start payment session and register callbacks for immediate updates
            # Pass UI change-status callback so dispensing progress can be shown
            try:
                self.payment_handler.start_payment_session(total_amount, on_payment_update=self._on_payment_update, on_change_update=self.update_change_status)
            except TypeError:
                # Backwards compatibility: older PaymentHandler might not accept on_change_update
                self.payment_handler.start_payment_session(total_amount, on_payment_update=self._on_payment_update)
            
            # Create payment status window with fixed size and position
            self.payment_window = tk.Toplevel(self)
            self.payment_window.title("Insert Payment")
            self.payment_window.geometry("400x400")            # Center the payment window on screen
            try:
                self.payment_window.update_idletasks()
                x = (self.payment_window.winfo_screenwidth() // 2) - (550 // 2)
                y = (self.payment_window.winfo_screenheight() // 2) - (500 // 2)
                self.payment_window.geometry(f"550x500+{x}+{y}")
            except Exception:
                pass            # Attach to the main toplevel window so focus and touch events work
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
            
            # Amount required
            amount_frame = tk.Frame(self.payment_window, bg=self.colors["payment_bg"])
            amount_frame.pack(fill="x", pady=(20,0))
            
            tk.Label(
                amount_frame,
                text="Amount Required:",
                font=self.fonts["item_details"],
                bg=self.colors["payment_bg"],
                fg=self.colors["text_fg"]
            ).pack()
            
            tk.Label(
                amount_frame,
                text=f"₱{total_amount:.2f}",
                font=self.fonts["header"],
                bg=self.colors["payment_bg"],
                fg=self.colors["payment_fg"]
            ).pack()
            
            # Payment status
            status_frame = tk.Frame(self.payment_window, bg=self.colors["payment_bg"])
            status_frame.pack(fill="x", pady=20)
            
            self.payment_status = tk.Label(
                status_frame,
                text="Coins: ₱0.00 | Bills: ₱0.00\nTotal Received: ₱0.00\nRemaining: ₱{:.2f}".format(total_amount),
                font=tkfont.Font(family="Helvetica", size=11),
                bg=self.colors["payment_bg"],
                fg=self.colors["payment_fg"],
                justify=tk.LEFT,
                anchor='w',
                wraplength=480
            )
            self.payment_status.pack()
            
            # Change status (initially hidden)
            self.change_label = tk.Label(
                status_frame,
                text="",
                font=self.fonts["item_details"],
                bg=self.colors["payment_bg"],
                fg=self.colors["payment_fg"]
            )
            self.change_label.pack_forget()  # Hidden until change is dispensed
            
            # Accepted coins info
            tk.Label(
                self.payment_window,
                text="Accepted Payment Methods:",
                font=self.fonts["item_details"],
                bg=self.colors["payment_bg"],
                fg=self.colors["text_fg"]
            ).pack(pady=(20,5))
            
            coins_text = (
                "Coins: • ₱1 • ₱5 • ₱10 (Old and New)\n"
                "Bills: • ₱20 • ₱50 • ₱100\n"
                "Please pay in exact amount only.\n"
                "This machine does not dispense change at the moment."
            )
            
            tk.Label(
                self.payment_window,
                text=coins_text,
                font=tkfont.Font(family="Helvetica", size=11),
                bg=self.colors["payment_bg"],
                fg=self.colors["text_fg"],
                justify=tk.LEFT,
                wraplength=480,
                anchor='w'
            ).pack()
            
            # Cancel button
            tk.Button(
                self.payment_window,
                text="Cancel Payment",
                font=self.fonts["item_details"],
                command=self.cancel_payment,
                bg="white",
                fg="#e74c3c",
                relief="flat"
            ).pack(pady=20)
            
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
            
            # Get individual amounts
            coin_amount = self.payment_handler.coin_acceptor.get_received_amount()
            bill_amount = 0.0
            if self.payment_handler.bill_acceptor:
                bill_amount = self.payment_handler.bill_acceptor.get_received_amount()
            
            if received != self.payment_received:  # Only update if amount changed
                self.payment_received = received
                self.coin_received = coin_amount
                self.bill_received = bill_amount
                remaining = total_amount - received
                
                status_text = (
                    f"Coins: ₱{coin_amount:.2f} | Bills: ₱{bill_amount:.2f}\n"
                    f"Total Received: ₱{received:.2f}\n"
                    f"Remaining: ₱{remaining:.2f}"
                )
                
                self.payment_status.config(text=status_text)
                
                if received >= total_amount:
                    self.complete_payment()
                    return
                    
            # Update every 100ms while payment is in progress
            self.after(100, lambda: self.update_payment_status(total_amount))

    def _on_payment_update(self, amount):
        """Callback invoked by PaymentHandler when coins/bills change (push notification).

        The handler passes the combined received amount. Schedule UI update on the
        main thread using `after(0, ...)` so Tkinter updates are safe.
        """
        if not self.payment_in_progress:
            return

        try:
            coin_amount = self.payment_handler.coin_acceptor.get_received_amount()
        except Exception as e:
            print(f"[PAYMENT] Error getting coin amount: {e}")
            coin_amount = 0.0
        try:
            bill_amount = self.payment_handler.bill_acceptor.get_received_amount() if self.payment_handler.bill_acceptor else 0.0
        except Exception as e:
            print(f"[PAYMENT] Error getting bill amount: {e}")
            bill_amount = 0.0

        # Prepare UI values
        self.payment_received = amount
        self.coin_received = coin_amount
        self.bill_received = bill_amount
        remaining = self.payment_required - amount

        status_text = (
            f"Coins: ₱{coin_amount:.2f} | Bills: ₱{bill_amount:.2f}\n"
            f"Total Received: ₱{amount:.2f}\n"
            f"Remaining: ₱{remaining:.2f}"
        )

        print(f"[PAYMENT UPDATE] Coins: {coin_amount}, Bills: {bill_amount}, Total: {amount}, Required: {self.payment_required}")

        # Schedule UI work on the main thread
        def _apply_update():
            try:
                self.payment_status.config(text=status_text)
            except Exception as e:
                print(f"[PAYMENT] Error updating UI: {e}")

            if amount >= self.payment_required:
                print(f"[PAYMENT] Payment complete: {amount} >= {self.payment_required}")
                try:
                    self.complete_payment()
                except Exception as e:
                    print(f"[PAYMENT] Error completing payment: {e}")

        try:
            self.after(0, _apply_update)
        except Exception as e:
            print(f"[PAYMENT] Error scheduling UI update: {e}")

    def update_change_status(self, message):
        """Update the change dispensing status display."""
        if self.change_label:
            self.change_label.config(text=message)
            self.change_label.pack()  # Make visible
            self.payment_window.update()

    def complete_payment(self):
        """Complete the payment process and dispense items & change"""
        if not self.payment_in_progress:
            return
            
        self.payment_in_progress = False
        
        # Stop payment session and handle change
        received, change_dispensed, change_status = self.payment_handler.stop_payment_session(
            required_amount=self.payment_required
        )
        
        # Show change being dispensed if needed
        if change_dispensed > 0:
            self.update_change_status(f"Dispensing change: ₱{change_dispensed:.2f}...")
            
        # Get individual amounts for final display
        coin_amount = self.coin_received
        bill_amount = self.bill_received
        
        # Start vending physical items in background so UI stays responsive
        try:
            vend_list = [ {"item": it["item"], "quantity": it["quantity"]} for it in self.controller.cart ]
        except Exception:
            vend_list = []

        def _vend_items():
            try:
                for entry in vend_list:
                    try:
                        item_obj = entry.get('item') if isinstance(entry, dict) else None
                        qty = int(entry.get('quantity', 1)) if isinstance(entry, dict) else 1
                        if item_obj and item_obj.get('name'):
                            name = item_obj.get('name')
                            print(f"Vending {qty} x {name}...")
                            # pulse configured ms (fallback to 800ms)
                            pulse_ms = self.controller.config.get('esp32_pulse_ms', 800) if isinstance(self.controller.config, dict) else 800
                            # vend_slots_for will handle round-robin if multiple slots assigned
                            try:
                                self.controller.vend_slots_for(name, qty)
                            except Exception as e:
                                print(f"Error vending {name}: {e}")
                    except Exception:
                        continue
            except Exception as e:
                print(f"Error in vending thread: {e}")

        try:
            threading.Thread(target=_vend_items, daemon=True).start()
        except Exception:
            pass

        # Show final status
        status_text = (
            f"Thank you!\n\n"
            f"Coins received: ₱{coin_amount:.2f}\n"
            f"Bills received: ₱{bill_amount:.2f}\n"
            f"Total paid: ₱{received:.2f}\n"
        )
        
        if change_dispensed > 0:
            status_text += f"Change dispensed: ₱{change_dispensed:.2f}\n"
            if change_status:
                status_text += f"{change_status}\n"
                
        status_text += "\nYour items will now be dispensed."
        
        messagebox.showinfo("Payment Complete", status_text)
        
        # Log the transaction to daily sales log
        try:
            logger = get_logger()
            items_to_log = []
            for item in self.controller.cart:
                items_to_log.append({
                    'name': item.get('name', 'Unknown'),
                    'quantity': item.get('quantity', 1)
                })
            logger.log_transaction(
                items_list=items_to_log,
                coin_amount=coin_amount,
                bill_amount=bill_amount,
                change_dispensed=change_dispensed
            )
        except Exception as e:
            print(f"[CartScreen] Error logging transaction: {e}")
        
        # Clean up and return to main screen
        self.payment_window.destroy()
        self.controller.clear_cart()
        self.controller.show_frame("KioskFrame")
        
    def cancel_payment(self, event=None):
        """Cancel the current payment session.

        This correctly handles the tuple returned by
        PaymentHandler.stop_payment_session() which is
        (total_received, change_amount, change_status).
        The method will always close the payment window (if present)
        and return the UI to the kiosk screen.
        """
        # Debug: log cancellation attempt
        try:
            print(f"DEBUG: cancel_payment called, event={bool(event)}, payment_in_progress={self.payment_in_progress}")
        except Exception:
            pass

        # Ensure payment flag is reset even if exception occurs
        try:
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

                if total_received and total_received > 0:
                    messagebox.showwarning(
                        "Payment Cancelled",
                        f"Payment cancelled.\n"
                        f"Please collect your money: ₱{total_received:.2f}"
                    )
        finally:
            # Always reset the flag
            self.payment_in_progress = False

        # Ensure the payment window is closed and return to kiosk
        try:
            if hasattr(self, 'payment_window') and self.payment_window:
                try:
                    print("DEBUG: Destroying payment window from cancel_payment")
                except Exception:
                    pass
                self.payment_window.destroy()
        except Exception:
            pass

        # Return to kiosk screen regardless of payment state
        try:
            self.controller.show_kiosk()
        except Exception:
            pass
                
    def on_closing(self):
        """Handle cleanup when closing"""
        if hasattr(self, 'payment_handler'):
            self.payment_handler.cleanup()
