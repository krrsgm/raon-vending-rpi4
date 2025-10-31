import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
from payment_handler import PaymentHandler


class CartScreen(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg="#f0f4f8")
        self.controller = controller
        # Initialize payment handler with coin hoppers from config
        self.payment_handler = PaymentHandler(controller.config, coin_pin=17)  # Using GPIO17 for coin signal
        self.payment_in_progress = False
        self.payment_received = 0.0
        self.payment_required = 0.0
        self.change_label = None  # Will be created in the payment window
        
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
            text="Pay with Coins",
            font=self.fonts["action_button"],
            bg=self.colors["total_fg"],
            fg=self.colors["background"],
            relief="flat",
            pady=10,
            command=self.handle_checkout,  # Using our new coin payment handler
        )
        self.checkout_button.pack(side="left", expand=True, fill="x", padx=(5, 0))

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
            text=f"Grand Total: {self.controller.currency_symbol}{grand_total:.2f}"
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
            self.payment_handler.start_payment_session(total_amount)
            
            # Create payment status window with fixed size and position
            self.payment_window = tk.Toplevel(self)
            self.payment_window.title("Insert Coins")
            self.payment_window.geometry("400x400")
            self.payment_window.transient(self)  # Make it float on top
            self.payment_window.grab_set()  # Make it modal
            
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
                text="Received: ₱0.00\nRemaining: ₱{:.2f}".format(total_amount),
                font=self.fonts["item_details"],
                bg=self.colors["payment_bg"],
                fg=self.colors["payment_fg"]
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
                text="Accepted Coins:",
                font=self.fonts["item_details"],
                bg=self.colors["payment_bg"],
                fg=self.colors["text_fg"]
            ).pack(pady=(20,5))
            
            coins_text = (
                "• ₱1 (Old and New Coins)\n"
                "• ₱5 (Old and New Coins)\n"
                "• ₱10 (Old and New Coins)"
            )
            
            tk.Label(
                self.payment_window,
                text=coins_text,
                font=self.fonts["item_details"],
                bg=self.colors["payment_bg"],
                fg=self.colors["text_fg"],
                justify=tk.LEFT
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
        """Update the payment status window with current coin total"""
        if self.payment_in_progress:
            received = self.payment_handler.get_current_amount()
            if received != self.payment_received:  # Only update if amount changed
                self.payment_received = received
                remaining = total_amount - received
                
                status_text = (
                    f"Received: ₱{received:.2f}\n"
                    f"Remaining: ₱{remaining:.2f}"
                )
                
                self.payment_status.config(text=status_text)
                
                if received >= total_amount:
                    self.complete_payment()
                    return
                    
            # Update every 100ms while payment is in progress
            self.after(100, lambda: self.update_payment_status(total_amount))

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
            
        # Show final status
        status_text = (
            f"Thank you!\n\n"
            f"Amount paid: ₱{received:.2f}\n"
        )
        
        if change_dispensed > 0:
            status_text += f"Change dispensed: ₱{change_dispensed:.2f}\n"
            if change_status:
                status_text += f"{change_status}\n"
                
        status_text += "\nYour items will now be dispensed."
        
        messagebox.showinfo("Payment Complete", status_text)
        
        # Clean up and return to main screen
        self.payment_window.destroy()
        self.controller.clear_cart()
        self.controller.show_frame("KioskFrame")
        
    def cancel_payment(self):
        """Cancel the current payment session"""
        if self.payment_in_progress:
            self.payment_in_progress = False
            received = self.payment_handler.stop_payment_session()
            
            if received > 0:
                messagebox.showwarning(
                    "Payment Cancelled",
                    f"Payment cancelled.\n"
                    f"Please collect your money: ₱{received:.2f}"
                )
            
            self.payment_window.destroy()
                
    def on_closing(self):
        """Handle cleanup when closing"""
        if hasattr(self, 'payment_handler'):
            self.payment_handler.cleanup()
