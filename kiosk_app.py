import tkinter as tk
from tkinter import font as tkfont, ttk
from PIL import Image, ImageTk
import os

class KioskFrame(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.scan_start_x = 0 # To hold the initial x-coordinate for scrolling
        self._last_canvas_width = 0 # To prevent unnecessary redraws

        # --- Drag vs. Click state ---
        self._is_dragging = False
        self._click_job = None
        self._clicked_item_data = None
        self._resize_job = None
        self.image_cache = {} # To prevent images from being garbage-collected

        # --- Color and Font Scheme ---
        self.colors = {
            'background': '#f0f4f8',
            'card_bg': '#ffffff',
            'text_fg': '#2c3e50',
            'gray_fg': '#7f8c8d',
            'price_fg': '#27ae60',
            'border': '#dfe6e9',
            'disabled_bg': '#f5f6fa',
            'out_of_stock_fg': '#e74c3c'
        }
        self.fonts = {
            'header': tkfont.Font(family="Helvetica", size=24, weight="bold"),
            'name': tkfont.Font(family="Helvetica", size=16, weight="bold"),
            'description': tkfont.Font(family="Helvetica", size=12),
            'price': tkfont.Font(family="Helvetica", size=14, weight="bold"),
            'quantity': tkfont.Font(family="Helvetica", size=12),
            'image_placeholder': tkfont.Font(family="Helvetica", size=14),
            'out_of_stock': tkfont.Font(family="Helvetica", size=14, weight="bold"),
        }
        # --- Calculate header/footer pixel sizes based on screen and physical diagonal ---
        # Use display diagonal from config if provided (in inches), default 13.3"
        diagonal_inches = 13.3
        try:
            diagonal_inches = float(getattr(controller, 'config', {}).get('display_diagonal_inches', diagonal_inches))
        except Exception:
            diagonal_inches = 13.3

        # Get current screen pixel dimensions (may already be portrait or landscape depending on system settings)
        try:
            screen_w = controller.winfo_screenwidth()
            screen_h = controller.winfo_screenheight()
            diagonal_pixels = (screen_w ** 2 + screen_h ** 2) ** 0.5
            ppi = diagonal_pixels / diagonal_inches if diagonal_inches > 0 else 165.68
        except Exception:
            # Fallback to a reasonable default PPI
            ppi = 165.68

        # Get screen dimensions for proportional sizing
        screen_height = controller.winfo_screenheight()
        self.header_px = int(screen_height * 0.15)  # 15% of screen height for header
        self.footer_px = int(screen_height * 0.05)  # 5% of screen height for footer

        # Fonts proportional to screen height
        title_size = int(screen_height * 0.035)  # 3.5% of height
        self.fonts['machine_title'] = tkfont.Font(family="Helvetica", size=title_size, weight="bold")
        self.fonts['machine_subtitle'] = tkfont.Font(family="Helvetica", size=max(7, self.header_px // 16))
        self.fonts['footer'] = tkfont.Font(family="Helvetica", size=max(7, self.footer_px // 10))
        # Placeholder logo font
        self.fonts['logo_placeholder'] = tkfont.Font(family="Helvetica", size=max(8, self.header_px // 12), weight="bold")
        # Read configurable values from controller config
        cfg = getattr(controller, 'config', {})
        self.machine_name = cfg.get('machine_name', 'RAON')
        self.machine_subtitle = cfg.get('machine_subtitle', 'Rapid Access Outlet for Electronic Necessities')
        self.header_logo_path = cfg.get('header_logo_path', '')

        self.items = controller.items
        self.configure(bg=self.colors['background'])
        # Create widgets and expose header/footer widgets so they can be updated
        self.create_widgets()


    def on_canvas_press(self, event):
        """Records the starting y-position and fixed x-position of a mouse drag."""
        self.canvas.scan_mark(event.x, event.y)
        self.scan_start_x = event.x

    def on_canvas_drag(self, event):
        """Moves the canvas view vertically based on mouse drag."""
        # Use the stored scan_start_x to prevent horizontal movement
        self.canvas.scan_dragto(self.scan_start_x, event.y, gain=1)

    def on_item_press(self, event, item_data):
        """Handles the initial press on an item card."""
        # Prepare for a potential drag
        self.on_canvas_press(event)
        # Store item data for a potential click
        self._clicked_item_data = item_data
        # Schedule the click action, but don't execute it yet
        self._click_job = self.after(150, self.perform_item_click)

    def on_item_drag(self, event):
        """Handles dragging that starts on an item card."""
        # If a click was scheduled, cancel it because this is a drag
        if self._click_job:
            self.after_cancel(self._click_job)
            self._click_job = None
        # Perform the canvas drag
        self.on_canvas_drag(event)

    def on_item_release(self, event):
        """Resets state on mouse release."""
        # This is intentionally left simple. The click is handled by the after() job.
        pass

    def perform_item_click(self):
        """Navigates to the item screen. Called only if no drag occurs."""
        if self._clicked_item_data:
            self.controller.show_item(self._clicked_item_data)
    def create_item_card(self, parent, item_data):
        """Creates a single item card widget."""
        card = tk.Frame(
            parent, 
            bg=self.colors['card_bg'], 
            highlightbackground=self.colors['border'], 
            highlightthickness=1
        )

        # 3. Image Placeholder
        image_frame = tk.Frame(card, bg=self.colors['card_bg'], height=150)
        image_frame.pack(fill='x', padx=10, pady=10)
        image_frame.pack_propagate(False) # Prevents child widgets from resizing it
        
        image_label = tk.Label(image_frame, bg=self.colors['card_bg'])
        image_label.pack(expand=True)

        image_path = item_data.get("image")
        if image_path and os.path.exists(image_path):
            try:
                # Open, resize, and display the image
                img = Image.open(image_path)
                
                # Resize image to fit the frame height while maintaining aspect ratio
                base_height = 150
                h_percent = (base_height / float(img.size[1]))
                w_size = int((float(img.size[0]) * float(h_percent)))
                img = img.resize((w_size, base_height), Image.Resampling.LANCZOS)

                photo = ImageTk.PhotoImage(img)
                image_label.config(image=photo)
                image_label.image = photo # Keep a reference!
            except Exception as e:
                print(f"Error loading image {image_path}: {e}")
                image_label.config(text="Image Error", font=self.fonts['image_placeholder'], fg=self.colors['gray_fg'])
        else:
            # Show placeholder if no image
            image_label.config(text="No Image", font=self.fonts['image_placeholder'], fg=self.colors['gray_fg'])


        # Frame for text content
        text_frame = tk.Frame(card, bg=self.colors['card_bg'])
        text_frame.pack(fill='x', padx=10)

        # 1. Name of item
        tk.Label(
            text_frame, 
            text=item_data['name'], 
            font=self.fonts['name'], 
            bg=self.colors['card_bg'], 
            fg=self.colors['text_fg'],
            anchor='w'
        ).pack(fill='x', pady=(5, 2))

        # 2. Description
        tk.Label(
            text_frame, 
            text=item_data['description'], 
            font=self.fonts['description'], 
            bg=self.colors['card_bg'], 
            fg=self.colors['gray_fg'],
            wraplength=280,
            justify='left',
            anchor='nw'
        ).pack(fill='x', pady=(0, 10))

        # Frame for price and quantity
        bottom_frame = tk.Frame(card, bg=self.colors['card_bg'])
        bottom_frame.pack(fill='x', padx=10, pady=(0, 10))

        if item_data['quantity'] > 0:
            # 4. Price
            tk.Label(
                bottom_frame, 
                text=f"{self.controller.currency_symbol}{item_data['price']:.2f}", 
                font=self.fonts['price'], 
                bg=self.colors['card_bg'], 
                fg=self.colors['price_fg']
            ).pack(side='left')

            # 5. Quantity available
            tk.Label(
                bottom_frame, 
                text=f"Qty: {item_data['quantity']}", 
                font=self.fonts['quantity'], 
                bg=self.colors['card_bg'], 
                fg=self.colors['gray_fg']
            ).pack(side='right')

            # --- Bind click event to all widgets on the card ---
            # We now need to handle press, drag (motion), and release separately
            press_action = lambda e, data=item_data: self.on_item_press(e, data)
            
            card.bind("<ButtonPress-1>", press_action)
            card.bind("<B1-Motion>", self.on_item_drag)
            card.bind("<ButtonRelease-1>", self.on_item_release)
            for widget in card.winfo_children():
                widget.bind("<ButtonPress-1>", press_action)
                widget.bind("<B1-Motion>", self.on_item_drag)
                widget.bind("<ButtonRelease-1>", self.on_item_release)
                if isinstance(widget, tk.Frame): # Bind children of inner frames too
                    for child in widget.winfo_children():
                        child.bind("<ButtonPress-1>", press_action)
                        child.bind("<B1-Motion>", self.on_item_drag)
                        child.bind("<ButtonRelease-1>", self.on_item_release)
        else: # Item is out of stock
            # Change background of all frames on the card
            disabled_bg = self.colors['disabled_bg']
            card.config(bg=disabled_bg)
            for widget in card.winfo_children():
                if isinstance(widget, tk.Frame):
                    widget.config(bg=disabled_bg)
                    for child in widget.winfo_children():
                        child.config(bg=disabled_bg)

            # Display "Out of Stock" message
            tk.Label(bottom_frame, text="Out of Stock", font=self.fonts['out_of_stock'], bg=disabled_bg, fg=self.colors['out_of_stock_fg']).pack()

        return card

    def create_widgets(self):
        # Top fixed header (machine name). Keep a fixed pixel height so it matches physical size.
        self.header = tk.Frame(self, bg=self.colors['background'], height=self.header_px)
        self.header.pack(side='top', fill='x')
        self.header.pack_propagate(False)

        # Left: logo (optional)
        left_frame = tk.Frame(self.header, bg=self.colors['background'])
        left_frame.pack(side='left', padx=8, pady=4)  # Reduced padding
        self.logo_label = tk.Label(left_frame, bg=self.colors['background'])
        self.logo_label.pack()
        self._load_header_logo()

        # Center: machine title and subtitle
        center_frame = tk.Frame(self.header, bg=self.colors['background'])
        center_frame.pack(side='left', fill='both', expand=True)
        self.title_label = tk.Label(center_frame, text=self.machine_name, font=self.fonts['machine_title'], bg=self.colors['background'], fg=self.colors['text_fg'])
        self.title_label.pack(side='top', anchor='w', padx=10)  # Reduced padding
        self.subtitle_label = tk.Label(center_frame, text=self.machine_subtitle, font=self.fonts['machine_subtitle'], bg=self.colors['background'], fg=self.colors['gray_fg'])
        self.subtitle_label.pack(side='top', anchor='w', padx=10)  # Reduced padding

        # Cart button on the header's right side
        # Create a frame below header for the cart button
        cart_frame = tk.Frame(self, bg=self.colors['background'])
        cart_frame.pack(fill='x', pady=(0, 4))
        
        # Category selection frame
        category_label = tk.Label(
            cart_frame,
            text="Category:",
            font=tkfont.Font(family="Helvetica", size=10, weight="bold"),
            bg=self.colors['background'],
            fg=self.colors['text_fg']
        )
        category_label.pack(side='left', padx=(8, 4), pady=2)

        # Get categories from config
        categories = ["All Categories"] + self.controller.config.get('categories', [])
        self.category_var = tk.StringVar(value="All Categories")
        
        self.category_combo = ttk.Combobox(
            cart_frame,
            textvariable=self.category_var,
            values=categories,
            state="readonly",
            font=tkfont.Font(family="Helvetica", size=10),
            width=20
        )
        self.category_combo.pack(side='left', padx=4, pady=2)
        self.category_combo.bind('<<ComboboxSelected>>', self.filter_by_category)

        # Cart button in its own frame below header
        cart_button = tk.Button(
            cart_frame,
            text="View Cart",
            font=tkfont.Font(family="Helvetica", size=10),
            bg=self.colors['price_fg'],
            fg=self.colors['card_bg'],
            relief='flat',
            padx=8,
            pady=2,
            command=lambda: self.controller.show_cart()
        )
        cart_button.pack(side='right', padx=8, pady=2)

        # Container for the scrollable area - sits between header and footer
        scroll_container = tk.Frame(self, bg=self.colors['background'])
        scroll_container.pack(fill='both', expand=True)
        scroll_container.bind('<Configure>', self.on_resize)

        # Scrollable area for items
        self.canvas = tk.Canvas(scroll_container, bg=self.colors['background'], highlightthickness=0)
        # The scrollbar is no longer created or packed.
        scrollable_frame = tk.Frame(self.canvas, bg=self.colors['background'])

        # Bind drag-to-scroll to the frame itself (for the space between items)
        scrollable_frame.bind("<ButtonPress-1>", self.on_canvas_press)
        scrollable_frame.bind("<B1-Motion>", self.on_canvas_drag)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        # The canvas window that holds the frame
        self.canvas_window = self.canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        # The yscrollcommand is no longer configured as there is no scrollbar.

        # Populate grid with item cards
        self.populate_items()
        # --- Add Drag-to-Scroll functionality ---
        # We only need to bind to the canvas itself.
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)

        self.canvas.pack(side="left", fill="both", expand=True)
        # The scrollbar.pack() call is removed.

        # Bottom fixed footer showing group members
        self.footer = tk.Frame(self, bg=self.colors['background'], height=self.footer_px)
        self.footer.pack(side='bottom', fill='x')
        self.footer.pack_propagate(False)

        members = getattr(self.controller, 'config', {}).get('group_members', [])
        if isinstance(members, list):
            members_text = '  |  '.join(members) if members else ''
        else:
            members_text = str(members)

        self.footer_label = tk.Label(self.footer, text=members_text, font=self.fonts['footer'], bg=self.colors['background'], fg=self.colors['gray_fg'])
        self.footer_label.pack(side='top', pady= max(2, self.footer_px//8))

    def _load_header_logo(self):
        """Attempt to load the header logo image (if configured) and resize it to fit header height."""
        self.logo_image = None
        logo_path = getattr(self, 'header_logo_path', '')
        if logo_path and os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                # Target height slightly smaller than header to allow padding
                target_h = max(1, self.header_px - 12)
                h_percent = (target_h / float(img.size[1]))
                w_size = int((float(img.size[0]) * float(h_percent)))
                img = img.resize((w_size, target_h), Image.Resampling.LANCZOS)
                self.logo_image = ImageTk.PhotoImage(img)
                self.logo_label.config(image=self.logo_image, text='')
            except Exception as e:
                print(f"Error loading header logo {logo_path}: {e}")
                # Fall back to textual placeholder
                self.logo_label.config(image='', text=self.machine_name if self.machine_name else 'RAON', font=self.fonts['logo_placeholder'], fg=self.colors['text_fg'], bg=self.colors['background'], relief='groove', bd=1, padx=6, pady=4)
        else:
            # No logo; show a concise textual placeholder (initials) to avoid
            # repeating the full machine name in the header.
            name = self.machine_name or 'RAON'
            # Build initials from words in the name (max 4 chars)
            initials = ''.join([p[0].upper() for p in name.split() if p])[:4]
            # If initials would be too short (single char) and the name is short,
            # use up to the first 4 characters of the name instead for clarity.
            if len(initials) == 1 and len(name) <= 4:
                placeholder_text = name.upper()[:4]
            else:
                placeholder_text = initials

            self.logo_label.config(
                image='',
                text=placeholder_text,
                font=self.fonts['logo_placeholder'],
                fg=self.colors['text_fg'],
                bg=self.colors['background'],
                relief='groove',
                bd=1,
                padx=6,
                pady=4,
            )

    def update_kiosk_config(self):
        """Reload configuration from controller and update header/footer (can be called after saving config)."""
        cfg = getattr(self.controller, 'config', {})
        # Update category selector with current categories
        categories = ["All Categories"] + cfg.get('categories', [])
        self.category_combo['values'] = categories
        if self.category_var.get() not in categories:
            self.category_var.set("All Categories")

        # Recompute PPI and pixel heights if diagonal changed
        diagonal_inches = cfg.get('display_diagonal_inches', 13.3)
        try:
            screen_w = self.controller.winfo_screenwidth()
            screen_h = self.controller.winfo_screenheight()
            diagonal_pixels = (screen_w ** 2 + screen_h ** 2) ** 0.5
            ppi = diagonal_pixels / float(diagonal_inches) if float(diagonal_inches) > 0 else 165.68
        except Exception:
            ppi = 165.68

        self.header_px = int(round(2.5 * ppi))
        self.footer_px = int(round(1.0 * ppi))

        # Update fonts sized for header/footer
        self.fonts['machine_title'].configure(size=max(18, self.header_px // 6))
        self.fonts['machine_subtitle'].configure(size=max(10, self.header_px // 12))
        self.fonts['footer'].configure(size=max(10, self.footer_px // 6))

        # Update machine text and logo
        self.machine_name = cfg.get('machine_name', self.machine_name)
        self.machine_subtitle = cfg.get('machine_subtitle', self.machine_subtitle)
        self.header_logo_path = cfg.get('header_logo_path', self.header_logo_path)

        self.title_label.config(text=self.machine_name)
        self.subtitle_label.config(text=self.machine_subtitle)
        # Resize header/footer frames
        self.header.config(height=self.header_px)
        self.footer.config(height=self.footer_px)
        self._load_header_logo()
        # Update footer members text
        members = cfg.get('group_members', [])
        if isinstance(members, list):
            members_text = '  |  '.join(members) if members else ''
        else:
            members_text = str(members)
        self.footer_label.config(text=members_text)

    def on_resize(self, event):
        """
        On window resize, checks if the width has changed enough to warrant
        rebuilding the item grid.
        """
        # Cancel any pending resize job to avoid multiple executions
        if self._resize_job:
            self.after_cancel(self._resize_job)

        # Schedule the grid population to run after a short delay
        if abs(event.width - self._last_canvas_width) > 10:
            self._resize_job = self.after(50, self.populate_items)

    def filter_by_category(self, event=None):
        """Filter items based on selected category."""
        self.populate_items()

    def populate_items(self):
        """Clears and repopulates the scrollable frame with item cards."""
        scrollable_frame = self.canvas.nametowidget(self.canvas.itemcget(self.canvas_window, 'window'))

        # Clear existing items
        for widget in scrollable_frame.winfo_children():
            widget.destroy()

        # --- Dynamic Column Calculation ---
        canvas_width = self.canvas.winfo_width()
        if canvas_width < 2: # Widget not drawn yet, can't calculate
            return

        card_plus_padding_width = 300 + 30 # Approx. card width + (padx * 2)
        num_cols = max(1, canvas_width // card_plus_padding_width)

        self._last_canvas_width = canvas_width # Update last known width

        # Filter items by selected category
        selected_category = self.category_var.get()
        filtered_items = []
        
        for item in self.controller.items:
            if selected_category == "All Categories" or item.get('category', '') == selected_category:
                filtered_items.append(item)

        # Repopulate grid with filtered item cards
        max_cols = num_cols
        for i, item in enumerate(filtered_items):
            row = i // max_cols
            col = i % max_cols
            card = self.create_item_card(scrollable_frame, item)
            card.grid(row=row, column=col, padx=15, pady=15, sticky="nsew")
        
        # Schedule center_frame to run after the layout has been updated
        # This ensures we get the correct width for the scrollable_frame
        self.after(10, self.center_frame)

    def center_frame(self, event=None):
        """Callback function to center the scrollable frame inside the canvas."""
        scrollable_frame = self.canvas.nametowidget(self.canvas.itemcget(self.canvas_window, 'window'))
        
        # Force the geometry manager to process layout changes
        scrollable_frame.update_idletasks()
        
        canvas_width = self.canvas.winfo_width()
        frame_width = scrollable_frame.winfo_width()
        
        x_pos = (canvas_width - frame_width) / 2
        if x_pos < 0:
            x_pos = 0
            
        self.canvas.coords(self.canvas_window, x_pos, 0)

    def reset_state(self):
        """Resets the kiosk screen to its initial state."""
        # Refresh category list from controller config so any changes made by
        # the admin are immediately available to buyers when the kiosk is shown.
        try:
            cfg = getattr(self.controller, 'config', {})
            categories = ["All Categories"] + cfg.get('categories', [])
            # Update combobox values if it exists
            if hasattr(self, 'category_combo'):
                self.category_combo['values'] = categories
                # Preserve selection when possible, otherwise reset
                if self.category_var.get() not in categories:
                    self.category_var.set('All Categories')
        except Exception:
            # Non-fatal: continue to populate items even if categories fail
            pass

        self.populate_items()