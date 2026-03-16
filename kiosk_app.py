import tkinter as tk
from tkinter import font as tkfont, ttk
from PIL import Image
import os
import io
import re
import platform
from collections import deque
from dht22_handler import DHT22Display
from system_status_panel import SystemStatusPanel
from fix_paths import get_absolute_path

def pil_to_photoimage(pil_image):
    """Convert PIL Image to Tkinter PhotoImage using PPM format (no ImageTk needed)"""
    with io.BytesIO() as output:
        pil_image.save(output, format="PPM")
        data = output.getvalue()
    return tk.PhotoImage(data=data)

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
        self._press_x_root = 0
        self._press_y_root = 0
        self._drag_threshold_px = 8
        self._resize_job = None
        self.image_cache = {} # To prevent images from being garbage-collected
        self._deferred_image_queue = deque()
        self._deferred_loader_job = None
        self._image_path_cache = {}  # raw image path -> resolved absolute path or None
        self._missing_image_paths_logged = set()
        self._last_layout_signature = None
        self._last_num_cols = None
        self._scrollable_frame = None
        # Tunable: how many images to load per batch and delay between batches (ms)
        self._deferred_batch = int(getattr(controller, 'config', {}).get('deferred_image_batch', 12))
        self._deferred_delay = int(getattr(controller, 'config', {}).get('deferred_image_delay_ms', 20))
        self._category_cache = {} # Cache for category detection (item_name -> categories)

        # --- Color and Font Scheme ---
        # Modern, high-contrast palette for readability on the kiosk display
        self.colors = {
            'background': '#f6f7fb',
            'card_bg': '#ffffff',
            'text_fg': "#102132",
            'gray_fg': '#7b8794',
            'price_fg': '#0f9d58',
            'border': '#e5e9f2',
            'disabled_bg': '#f1f3f7',
            'out_of_stock_fg': '#e53935'
        }
        self.fonts = {
            'header': tkfont.Font(family="Helvetica", size=24, weight="bold"),
            'name': tkfont.Font(family="Helvetica", size=17, weight="bold"),
            'description': tkfont.Font(family="Helvetica", size=12),
            'price': tkfont.Font(family="Helvetica", size=15, weight="bold"),
            'quantity': tkfont.Font(family="Helvetica", size=12),
            'image_placeholder': tkfont.Font(family="Helvetica", size=14),
            'out_of_stock': tkfont.Font(family="Helvetica", size=14, weight="bold"),
            'category': tkfont.Font(family="Helvetica", size=9),
            'control_small': tkfont.Font(family="Helvetica", size=10),
            'control_bold': tkfont.Font(family="Helvetica", size=10, weight="bold"),
            'cart_btn': tkfont.Font(family="Helvetica", size=15, weight="bold"),
        }
        
        # Category rules are compiled once to keep filtering fast and accurate.
        self._category_rules = {
            'Resistor': [r'\bresistor\b', r'\br\d+\b', r'\bohm\b', r'\bkohm\b'],
            'Capacitor': [r'\bcapacitor\b', r'\bfarad\b', r'\buf\b', r'\bpf\b'],
            'IC': [r'\bic\d+\b', r'\bintegrated\s*circuit\b', r'\b74(?:ls)?\d+\b', r'\b555\b', r'\blm\d+\b'],
            'Amplifier': [r'\bamplifier\b', r'\bop[- ]?amp\b'],
            'Board': [r'\bboard\b', r'\bpcb\b', r'\bbreadboard\b', r'\bshield\b', r'\barduino\b', r'\buno\b'],
            'Bundle': [r'\bbundle\b', r'\bkit\b', r'\bpack\b', r'\bsolder\b'],
            'Wires': [r'\bwire(s)?\b', r'\bjumper\b', r'\bcable\b', r'\bcord\b', r'\blead(s)?\b', r'\bawg\b', r'\balligator\b'],
            'Switches': [r'\bswitch(es)?\b', r'\bpush\s*button(s)?\b', r'\bbutton(s)?\b'],
            'Semiconductor': [r'\bdiode\b', r'\btransistor\b', r'\bled\b', r'\bregulator\b'],
            'Sensor': [r'\bsensor\b', r'\bpir\b', r'\bphotodiode\b', r'\bir\b'],
        }
        self._compiled_category_rules = {
            cat: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for cat, patterns in self._category_rules.items()
        }

        # Simple notice if change hoppers are empty
        self._change_notice_state = None
        
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
            self.ppi = diagonal_pixels / diagonal_inches if diagonal_inches > 0 else 165.68
        except Exception:
            # Fallback to a reasonable default PPI
            self.ppi = 165.68
        
        # Detect if running on Raspberry Pi for better card sizing
        is_pi = platform.machine() in ['armv7l', 'armv6l', 'aarch64']
        
        # Calculate card dimensions (responsive to screen size)
        if is_pi:
            # On Pi 7" touchscreen (1024x600), use smaller cards for 4-5 per row
            self.card_width = int(self.ppi * 1.5)   # 1.5 inches (optimized for Pi)
            self.card_height = int(self.ppi * 2.2)  # 2.2 inches (optimized for Pi)
            self.card_spacing = int(self.ppi * (0.3 / 2.54))  # 0.3cm spacing
        else:
            # On larger desktop displays, use standard sizing
            self.card_width = int(self.ppi * 2.0)   # 2.0 inches
            self.card_height = int(self.ppi * 3.0)  # 3.0 inches
            self.card_spacing = int(self.ppi * (0.5 / 2.54))  # 0.5cm spacing

        # Get screen dimensions for proportional sizing
        screen_height = controller.winfo_screenheight()
        self.header_px = int(screen_height * 0.15)  # 15% of screen height for header
        self.footer_px = int(screen_height * 0.05)  # 5% of screen height for footer
        self.touch_dead_zone_top_px = 100
        self.touch_dead_zone_bottom_start_px = 1700
        self.touch_dead_zone_bottom_px = max(0, int(screen_height - self.touch_dead_zone_bottom_start_px))

        # Fonts proportional to screen height
        title_size = int(screen_height * 0.035)  # 3.5% of height
        self.fonts['machine_title'] = tkfont.Font(family="Michroma", size=title_size, weight="bold")
        self.fonts['machine_subtitle'] = tkfont.Font(family="Michroma", size=max(7, self.header_px // 16))
        self.fonts['footer'] = tkfont.Font(family="Helvetica", size=max(7, self.footer_px // 10))
        # Placeholder logo font
        self.fonts['logo_placeholder'] = tkfont.Font(family="Michroma", size=max(8, self.header_px // 12), weight="bold")
        # Read configurable values from controller config
        cfg = getattr(controller, 'config', {})
        self.machine_name = cfg.get('machine_name', 'RAON')
        self.machine_subtitle = cfg.get('machine_subtitle', 'Rapid Access Outlet for Electronic Necessities')
        self.header_logo_path = cfg.get('header_logo_path', '')
        self.group_members = cfg.get('group_members', [])

        self.items = controller.items
        self.configure(bg=self.colors['background'])
        # Create widgets and expose header/footer widgets so they can be updated
        self.create_widgets()
    
        def cleanup(self):
            """Cancel deferred image loader job and clear queue to prevent leaks/freezes."""
            if self._deferred_loader_job:
                try:
                    self.after_cancel(self._deferred_loader_job)
                except Exception:
                    pass
                self._deferred_loader_job = None
            self._deferred_image_queue.clear()


    def on_canvas_press(self, event):
        """Records the starting y-position and fixed x-position of a mouse drag."""
        try:
            canvas_x = self.winfo_pointerx() - self.canvas.winfo_rootx()
            canvas_y = self.winfo_pointery() - self.canvas.winfo_rooty()
        except Exception:
            canvas_x, canvas_y = event.x, event.y
        self.canvas.scan_mark(canvas_x, canvas_y)
        self.scan_start_x = canvas_x

    def on_canvas_drag(self, event):
        """Moves the canvas view vertically based on mouse drag."""
        # Use the stored scan_start_x to prevent horizontal movement
        try:
            canvas_y = self.winfo_pointery() - self.canvas.winfo_rooty()
        except Exception:
            canvas_y = event.y
        self.canvas.scan_dragto(self.scan_start_x, canvas_y, gain=1)

    def on_item_press(self, event, item_data):
        """Handles the initial press on an item card."""
        self._is_dragging = False
        try:
            self._press_x_root = int(getattr(event, "x_root", 0) or 0)
            self._press_y_root = int(getattr(event, "y_root", 0) or 0)
        except Exception:
            self._press_x_root = 0
            self._press_y_root = 0
        # Prepare for drag scrolling in canvas coordinates.
        self.on_canvas_press(event)
        # Store item data for a potential tap.
        self._clicked_item_data = item_data

    def on_item_drag(self, event):
        """Handles dragging that starts on an item card."""
        try:
            dx = abs(int(getattr(event, "x_root", 0) or 0) - self._press_x_root)
            dy = abs(int(getattr(event, "y_root", 0) or 0) - self._press_y_root)
            if dx >= self._drag_threshold_px or dy >= self._drag_threshold_px:
                self._is_dragging = True
        except Exception:
            self._is_dragging = True
        # Perform the canvas drag
        self.on_canvas_drag(event)

    def on_item_release(self, event):
        """Resets state on mouse release."""
        if self._click_job:
            try:
                self.after_cancel(self._click_job)
            except Exception:
                pass
            self._click_job = None
        if not self._is_dragging and self._clicked_item_data:
            self.perform_item_click()
        self._is_dragging = False

    def perform_item_click(self):
        """Navigates to the item screen. Called only if no drag occurs."""
        if self._clicked_item_data:
            self.controller.show_item(self._clicked_item_data)

    def _is_descendant_widget(self, widget, ancestor):
        """Return True when widget is ancestor itself or one of its descendants."""
        w = widget
        while w is not None:
            if w == ancestor:
                return True
            try:
                parent_name = w.winfo_parent()
                if not parent_name:
                    break
                w = w.nametowidget(parent_name)
            except Exception:
                break
        return False

    def _pointer_over_canvas(self):
        """Check if current pointer is over the item canvas or its child widgets."""
        try:
            hovered = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
            return self._is_descendant_widget(hovered, self.canvas)
        except Exception:
            return False

    def _event_from_product_area(self, event):
        """Return True when a wheel event comes from, or is hovering over, the product list."""
        try:
            widget = getattr(event, "widget", None)
            if self._is_descendant_widget(widget, self.canvas):
                return True
            if self._scrollable_frame and self._is_descendant_widget(widget, self._scrollable_frame):
                return True
            return self._pointer_over_canvas()
        except Exception:
            return False

    def _on_mousewheel_kiosk(self, event):
        """Cross-platform wheel handler for vertical scrolling in the product area."""
        try:
            if not self._event_from_product_area(event):
                return

            step = 0
            # Linux X11 wheel events.
            if getattr(event, 'num', None) == 4:
                step = -3
            elif getattr(event, 'num', None) == 5:
                step = 3
            else:
                # Windows/macOS/hi-res wheels: delta may be +/-120, +/-1, or another small value.
                delta = int(getattr(event, 'delta', 0) or 0)
                if delta != 0:
                    if abs(delta) >= 120:
                        step = -int(delta / 120)
                    else:
                        step = -1 if delta > 0 else 1

            if step != 0:
                self.canvas.yview_scroll(step, 'units')
                return 'break'
        except Exception:
            pass

    def _bind_wheel_recursive(self, widget):
        """Bind wheel events to a widget and all descendants for consistent item-hover scrolling."""
        if widget is None:
            return
        try:
            widget.bind('<MouseWheel>', self._on_mousewheel_kiosk, add='+')
            widget.bind('<Button-4>', self._on_mousewheel_kiosk, add='+')
            widget.bind('<Button-5>', self._on_mousewheel_kiosk, add='+')
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._bind_wheel_recursive(child)
        except Exception:
            pass

    def _truncate_text(self, text, max_chars):
        """Keep card text concise so larger fonts still fit cleanly."""
        value = str(text or "").strip()
        if len(value) <= max_chars:
            return value
        return value[:max(1, max_chars - 3)].rstrip() + "..."

    def create_item_card(self, parent, item_data):
        """Creates a single item card widget with dimensions: 1in width x 2.5in height."""
        # Determine stock status and color-coding
        quantity = item_data.get('quantity', 0)
        default_threshold = item_data.get('low_stock_threshold', 3)  # Per-item override
        
        # Determine stock status color
        if quantity <= 0:
            stock_status = 'out_of_stock'
            border_color = '#e74c3c'  # Red
            stock_indicator = 'OUT'
        elif quantity <= default_threshold:
            stock_status = 'low_stock'
            border_color = '#f39c12'  # Orange/Yellow
            stock_indicator = f'LOW {quantity}'
        else:
            stock_status = 'in_stock'
            border_color = '#27ae60'  # Green
            stock_indicator = f'OK {quantity}'
        
        card = tk.Frame(
            parent,
            bg=self.colors['card_bg'],
            highlightbackground=border_color,  # Color-coded border
            highlightthickness=3,  # Thicker border for visibility
            bd=0,
            width=self.card_width,
            height=self.card_height
        )
        card.pack_propagate(False)  # Fix the size to 1in x 2.5in

        # Stock Status Badge (top-right corner)
        badge_frame = tk.Frame(card, bg=border_color, height=20)
        badge_frame.pack(side='top', fill='x')
        badge_frame.pack_propagate(False)
        
        badge_label = tk.Label(
            badge_frame,
            text=f'  {stock_indicator}  ',
            font=self.fonts['control_bold'],
            bg=border_color,
            fg='white'
        )
        badge_label.pack(expand=True)

        # Image Placeholder - 60% of card height with minimal padding
        image_height = int(self.card_height * 0.55)  # Reduced to accommodate badge
        image_frame = tk.Frame(card, bg=self.colors['card_bg'], height=image_height)
        image_frame.pack(fill='x', padx=2, pady=2)
        image_frame.pack_propagate(False) # Prevents child widgets from resizing it
        
        image_label = tk.Label(image_frame, bg=self.colors['card_bg'])
        image_label.pack(expand=True)

        image_path = item_data.get("image")
        if image_path:
            resolved_path = self._resolve_image_path(image_path)
            
            if resolved_path:
                try:
                    # Queue image for deferred loading to avoid blocking UI
                    # If already cached, use it immediately
                    if resolved_path in self.image_cache:
                        photo = self.image_cache[resolved_path]
                        image_label.config(image=photo)
                        image_label.image = photo
                    else:
                        # Store desired target height so loader can resize appropriately
                        image_label._deferred_image = (resolved_path, image_height - 8)
                        image_label.config(text='')
                        # Add to queue and ensure loader is running
                        self._deferred_image_queue.append(image_label)
                        if not self._deferred_loader_job:
                            self._deferred_loader_job = self.after(10, self._process_deferred_batch)
                except Exception as e:
                    print(f"Error loading image {resolved_path}: {e}")
                    image_label.config(text="Image Error", font=self.fonts['image_placeholder'], fg=self.colors['gray_fg'])
            else:
                # Show placeholder if image not found
                normalized = str(image_path).replace('\\', '/')
                if normalized and normalized not in self._missing_image_paths_logged:
                    self._missing_image_paths_logged.add(normalized)
                    print(f"[KioskFrame] Image not found: {normalized}")
                image_label.config(text="No Image", font=self.fonts['image_placeholder'], fg=self.colors['gray_fg'])
        else:
            # Show placeholder if no image
            image_label.config(text="No Image", font=self.fonts['image_placeholder'], fg=self.colors['gray_fg'])



        # Frame for text content - minimal padding
        # Bottom controls: price (left) and qty + stock warning (right) stay pinned at the bottom.
        bottom_frame = tk.Frame(card, bg=self.colors['card_bg'])
        bottom_frame.pack(side='bottom', fill='x', padx=10, pady=(0, 10))

        text_frame = tk.Frame(card, bg=self.colors['card_bg'])
        # Let text area grow but cap its content heights so price/stock always visible.
        text_frame.pack(fill='both', expand=True, padx=2)

        # 1. Name of item
        name_text = self._truncate_text(item_data.get('name', ''), 48)
        name_label = tk.Label(
            text_frame,
            text=name_text,
            font=self.fonts['name'],
            bg=self.colors['card_bg'],
            fg=self.colors['text_fg'],
            anchor='w',
            justify='left',
            wraplength=max(160, self.card_width - 22),
            height=2  # cap to 2 lines to avoid pushing price out
        )
        name_label.pack(fill='x', pady=(6, 2))

        # 1b. Category based on item name keywords
        item_categories = self._get_categories_for_item(item_data)
        if item_categories:
            shown_categories = item_categories[:2]
            suffix = "..." if len(item_categories) > 2 else ""
            category_text = f"{', '.join(shown_categories)}{suffix}"
        else:
            category_text = 'Misc'
        category_label = tk.Label(
            text_frame,
            text=f"Category: {category_text}",
            font=self.fonts['category'],
            bg=self.colors['card_bg'],
            fg='#8B7355',
            anchor='w',
            justify='left',
            wraplength=max(110, self.card_width - 22),
            height=2  # limit height so warnings stay visible
        )
        category_label.pack(fill='x', pady=(0, 2))

        # 2. Short description
        description_text = self._truncate_text(item_data.get('description', ''), 90)
        desc_label = tk.Label(
            text_frame,
            text=description_text,
            font=self.fonts['description'],
            bg=self.colors['card_bg'],
            fg=self.colors['gray_fg'],
            wraplength=max(110, self.card_width - 22),
            justify='left',
            anchor='nw',
            height=3  # enforce 3-line cap to keep price/stock in view
        )
        desc_label.pack(fill='x', pady=(0, 8))

        # Use normalized currency symbol from controller to avoid stale "$" in UI.
        currency = str(getattr(self.controller, 'currency_symbol', "\u20b1") or "\u20b1").strip()
        if (not currency) or (currency in {"$", "US$", "USD", "PHP", "Php", "php"}):
            currency = "\u20b1"
        price_lbl = tk.Label(
            bottom_frame,
            text=f"{currency}{item_data.get('price',0):.2f}",
            font=self.fonts['price'],
            bg=self.colors['card_bg'],
            fg=self.colors['price_fg']
        )
        price_lbl.pack(side='left')

        # Note: Add button removed. Users click item to navigate to detail view where adding happens.
        
        # Add low-stock warning if quantity is low
        if 0 < quantity <= default_threshold:
            warning_frame = tk.Frame(bottom_frame, bg='#fff3cd')
            warning_frame.pack(side='right', padx=5)
            warning_label = tk.Label(
                warning_frame,
                text=f'Only {quantity} left!',
                font=self.fonts['control_small'],
                bg='#fff3cd',
                fg='#856404'
            )
            warning_label.pack(padx=3, pady=1)

        # Bind click/drag behavior for cards that are purchasable
        if item_data.get('quantity',0) > 0:
            press_action = lambda e, data=item_data: self.on_item_press(e, data)
            # Bind only to parts of the card that should navigate on click; skip controls (spinbox/add button)
            widgets_to_bind = [card, image_frame, image_label, text_frame, name_label, desc_label, price_lbl]
            for w in widgets_to_bind:
                try:
                    w.bind("<ButtonPress-1>", press_action)
                    w.bind("<B1-Motion>", self.on_item_drag)
                    w.bind("<ButtonRelease-1>", self.on_item_release)
                except Exception:
                    pass
        else:
            disabled_bg = self.colors['disabled_bg']
            card.config(bg=disabled_bg)
            for widget in card.winfo_children():
                if isinstance(widget, tk.Frame):
                    widget.config(bg=disabled_bg)
                    for child in widget.winfo_children():
                        try:
                            child.config(bg=disabled_bg)
                        except Exception:
                            pass
            # Place out-of-stock label on the right where controls were, to avoid overlapping price
            out_lbl = tk.Label(bottom_frame, text="Out of Stock", font=self.fonts['out_of_stock'], bg=disabled_bg, fg=self.colors['out_of_stock_fg'])
            out_lbl.pack(side='right')
            drag_only_widgets = [card, image_frame, image_label, text_frame, name_label, desc_label, price_lbl, out_lbl]
            for w in drag_only_widgets:
                try:
                    w.bind("<ButtonPress-1>", self.on_canvas_press)
                    w.bind("<B1-Motion>", self.on_canvas_drag)
                except Exception:
                    pass

        # Ensure wheel scroll works even while cursor is directly on card widgets.
        self._bind_wheel_recursive(card)

        return card

    def create_widgets(self):
        # Top blue header bar similar to the screenshot
        header_bg = '#2222a8'
        self.header = tk.Frame(self, bg=header_bg, height=self.header_px)
        self.header.pack(side='top', fill='x')
        self.header.pack_propagate(False)

        left_frame = tk.Frame(self.header, bg=header_bg)
        left_frame.pack(side='left', padx=12, pady=8)
        
        # Logo image or placeholder - make it bigger
        logo_image_frame = tk.Frame(left_frame, bg=header_bg, width=160, height=int(self.header_px * 0.85))
        logo_image_frame.pack(side='left', padx=(0, 12))
        logo_image_frame.pack_propagate(False)
        
        self.logo_image_label = tk.Label(logo_image_frame, bg=header_bg)
        self.logo_image_label.pack(expand=True)
        self.load_header_logo()
        
        # Logo and text container
        logo_text_frame = tk.Frame(left_frame, bg=header_bg)
        logo_text_frame.pack(anchor='w')
        
        # Machine name and subtitle
        self.logo_label = tk.Label(logo_text_frame, text=self.machine_name, bg=header_bg, fg='white', font=self.fonts['machine_title'])
        self.logo_label.pack(anchor='w')
        
        # Subtitle below machine name
        subtitle_label = tk.Label(logo_text_frame, text=self.machine_subtitle, bg=header_bg, fg='white', font=self.fonts['machine_subtitle'])
        subtitle_label.pack(anchor='w')

        right_frame = tk.Frame(self.header, bg=header_bg)
        right_frame.pack(side='right', padx=12)

        # Keep top dead-zone visuals for branding only (logo/header),
        # and place touch controls below Y=50.
        controls_bar = tk.Frame(self, bg=header_bg, height=max(66, self.touch_dead_zone_top_px + 16))
        controls_bar.pack(side='top', fill='x')
        controls_bar.pack_propagate(False)

        controls_right = tk.Frame(controls_bar, bg=header_bg)
        controls_right.pack(side='right', padx=12, pady=6)

        cart_btn = tk.Button(
            controls_right,
            text='Cart',
            bg='white',
            fg='#2222a8',
            activebackground='#dfe8ff',
            activeforeground='#1f2f85',
            relief='flat',
            borderwidth=0,
            highlightthickness=0,
            cursor='hand2',
            font=self.fonts['cart_btn'],
            padx=22,
            pady=11,
            command=lambda: self.controller.show_cart()
        )
        cart_btn.pack()
        cart_btn.bind('<Enter>', lambda _e: cart_btn.configure(bg='#dfe8ff'))
        cart_btn.bind('<Leave>', lambda _e: cart_btn.configure(bg='white'))

        # Change-stock notice for buyers (exact amount warning)
        notice_wrap = tk.Frame(controls_bar, bg=header_bg)
        notice_wrap.pack(side="right", padx=12)
        self.change_notice_label = tk.Label(
            notice_wrap,
            text="",
            bg="white",
            fg="#e11d48",
            font=("Helvetica", 14, "bold"),
            relief="solid",
            bd=1,
            padx=10,
            pady=4
        )
        self.change_notice_label.pack()
        self._update_change_notice()
        try:
            self.after(4000, self._update_change_notice_periodic)
        except Exception:
            pass

        # Main content area: left sidebar + main product area
        content = tk.Frame(self, bg=self.colors['background'])
        content.pack(fill='both', expand=True)
        
        # Left sidebar
        sidebar_width = max(250, int(self.controller.winfo_screenwidth() * 0.22))
        self._category_button_wraplength = max(120, sidebar_width - 32)
        sidebar = tk.Frame(content, width=sidebar_width, bg='#f7fafc')
        sidebar.pack(side='left', fill='y', padx=(12,6), pady=12)
        sidebar.pack_propagate(False)

        # (Search box removed - category-only browsing)

        # Categories display: extract dynamically from assigned items
        ttk.Label(sidebar, text='Component Categories', background='#f7fafc', font=self.fonts['description']).pack(anchor='w', padx=8, pady=(12,4))
        self.categories_frame = tk.Frame(sidebar, bg='#f7fafc')
        self.categories_frame.pack(fill='both', expand=True, padx=8)
        
        # Build categories list: either from assigned items or from config
        self._category_buttons = {}
        self._active_category = 'All Components'
        
        def build_categories():
            """Build category list from assigned items using auto-detected keywords."""
            categories = set(['All Components'])
            assigned = getattr(self.controller, 'assigned_slots', None)
            
            # If we have assigned items, extract categories from them
            if isinstance(assigned, list) and any(assigned):
                term_idx = getattr(self.controller, 'assigned_term', 0) or 0
                for slot in assigned:
                    try:
                        if not slot or not isinstance(slot, dict):
                            continue
                        terms = slot.get('terms', [])
                        if len(terms) > term_idx and terms[term_idx]:
                            item = terms[term_idx]
                            item_cats = self._get_categories_for_item(item)
                            categories.update(item_cats)
                    except Exception:
                        continue
            else:
                # No assigned items, use default categories from item names if any
                for item in self.controller.items:
                    try:
                        item_cats = self._get_categories_for_item(item)
                        categories.update(item_cats)
                    except Exception:
                        continue
            
            return ['All Components'] + sorted([c for c in categories if c != 'All Components'])
        
        # Initial population
        categories = build_categories()
        
        for cat in categories:
            b = tk.Button(
                self.categories_frame,
                text=cat,
                relief='flat',
                bg='#f7fafc',
                fg='#2c3e50',
                activebackground='#e6f0ff',
                activeforeground='#1f2f85',
                borderwidth=0,
                highlightthickness=0,
                cursor='hand2',
                anchor='w',
                padx=12,
                pady=7,
                justify='left',
                wraplength=self._category_button_wraplength,
                command=lambda c=cat: self._on_category_click(c)
            )
            b.pack(fill='x', pady=2)
            self._category_buttons[cat] = b
        
        # Highlight default
        if 'All Components' in self._category_buttons:
            self._set_active_category_button('All Components')

        # Main product area
        main_area = tk.Frame(content, bg=self.colors['background'])
        main_area.pack(side='left', fill='both', expand=True, padx=(6,12), pady=12)
        main_area.bind('<Configure>', self.on_resize)

        # Scrollable canvas for items
        self.canvas = tk.Canvas(main_area, bg=self.colors['background'], highlightthickness=0)
        scrollable_frame = tk.Frame(self.canvas, bg=self.colors['background'])
        self._scrollable_frame = scrollable_frame
        scrollable_frame.bind('<ButtonPress-1>', self.on_canvas_press)
        scrollable_frame.bind('<B1-Motion>', self.on_canvas_drag)
        # keep scrollregion in sync when children change
        scrollable_frame.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas_window = self.canvas.create_window((0,0), window=scrollable_frame, anchor='nw')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.bind('<ButtonPress-1>', self.on_canvas_press)
        self.canvas.bind('<B1-Motion>', self.on_canvas_drag)

        # Ensure the internal frame always matches the canvas width so grid columns
        # can expand properly and cards don't get squeezed on narrow frames.
        def _sync_width(event):
            try:
                self.canvas.itemconfig(self.canvas_window, width=event.width)
            except Exception:
                pass

        # Bind canvas resize to sync the embedded window width
        self.canvas.bind('<Configure>', _sync_width)

        # Bind wheel events for different platforms
        try:
            # Windows and macOS: bind globally plus direct canvas/frame.
            self.canvas.bind_all('<MouseWheel>', self._on_mousewheel_kiosk)
            self.canvas.bind('<MouseWheel>', self._on_mousewheel_kiosk, add='+')
            scrollable_frame.bind('<MouseWheel>', self._on_mousewheel_kiosk, add='+')
        except Exception:
            pass
        try:
            # Linux (X11)
            self.canvas.bind_all('<Button-4>', self._on_mousewheel_kiosk)
            self.canvas.bind_all('<Button-5>', self._on_mousewheel_kiosk)
            self.canvas.bind('<Button-4>', self._on_mousewheel_kiosk, add='+')
            self.canvas.bind('<Button-5>', self._on_mousewheel_kiosk, add='+')
            scrollable_frame.bind('<Button-4>', self._on_mousewheel_kiosk, add='+')
            scrollable_frame.bind('<Button-5>', self._on_mousewheel_kiosk, add='+')
        except Exception:
            pass

        # Populate grid with item cards after first paint to reduce startup lag
        self.after(1, self.populate_items)

        # System Status Panel occupies the lower non-touch zone (Y >= 1600).
        status_zone_height = max(320, self.touch_dead_zone_bottom_px if self.touch_dead_zone_bottom_px > 0 else max(70, self.footer_px))
        self.status_zone = tk.Frame(self, bg='#111111', height=status_zone_height)
        self.status_zone.pack(side='bottom', fill='x')
        self.status_zone.pack_propagate(False)

        self.status_panel = SystemStatusPanel(self.status_zone, controller=self.controller, panel_height=status_zone_height)
        self.status_panel.pack(fill='both', expand=True)

        # Note: Developer names are now shown in system status panel only (no redundant footer)

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
                self.logo_image = pil_to_photoimage(img)
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

    def _update_change_notice(self):
        """Show 'exact amount' notice if either change hopper is empty."""
        label = getattr(self, 'change_notice_label', None)
        if not label:
            return
        try:
            stock = self.controller.get_coin_change_stock()
            one = int(stock.get("one_peso", {}).get("count", 0))
            five = int(stock.get("five_peso", {}).get("count", 0))
            if one <= 0 or five <= 0:
                label.config(text="Exact amount only — no change", fg="#e11d48", bg="white")
            else:
                label.config(text="", fg="#e11d48", bg="white")
        except Exception:
            label.config(text="")

    def _update_change_notice_periodic(self):
        """Periodic poll to refresh change notice if stock changes."""
        try:
            self._update_change_notice()
        finally:
            try:
                self.after(4000, self._update_change_notice_periodic)
            except Exception:
                pass

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

        # Rebuild only when column count would actually change.
        new_cols = self._compute_num_cols(int(getattr(event, 'width', 0) or 0))
        if new_cols != self._last_num_cols:
            self._resize_job = self.after(80, self.populate_items)
        self._last_canvas_width = int(getattr(event, 'width', 0) or 0)

    def filter_by_category(self, event=None):
        """Filter items based on selected category."""
        self.populate_items()

    def _normalize_category_name(self, raw_category, allow_passthrough=False):
        """Map noisy raw category names into a stable display category."""
        text = str(raw_category or "").strip().lower()
        if not text:
            return None

        normalize_rules = [
            ("Resistor", ("resistor", "ohm")),
            ("Capacitor", ("capacitor", "farad", "uf", "pf")),
            ("IC", ("integrated circuit", "logic ic")),
            ("Amplifier", ("amplifier", "opamp", "op-amp")),
            ("Board", ("board", "pcb", "breadboard", "arduino", "uno", "shield")),
            ("Bundle", ("bundle", "kit", "pack", "solder")),
            ("Wires", ("wire", "jumper", "cable", "cord", "lead", "awg", "alligator")),
            ("Switches", ("switch", "button", "push button")),
            ("Semiconductor", ("diode", "transistor", "led", "regulator")),
            ("Sensor", ("sensor", "pir", "photodiode", "ir")),
        ]
        for normalized, keywords in normalize_rules:
            for keyword in keywords:
                if keyword in text:
                    return normalized

        if allow_passthrough:
            cleaned = re.sub(r"\s+", " ", text).strip()
            if cleaned:
                return cleaned.title()
        return None

    def _get_categories_for_item(self, item):
        """Resolve categories for an item dict, preferring explicit category fields."""
        if isinstance(item, dict):
            explicit = item.get("category")
            explicit_categories = []
            if isinstance(explicit, str):
                explicit_categories = [p.strip() for p in re.split(r"[|,/;]+", explicit) if p.strip()]
            elif isinstance(explicit, (list, tuple, set)):
                explicit_categories = [str(p).strip() for p in explicit if str(p).strip()]

            normalized_explicit = []
            for raw_cat in explicit_categories:
                normalized = self._normalize_category_name(raw_cat, allow_passthrough=True)
                if normalized:
                    normalized_explicit.append(normalized)
            if normalized_explicit:
                return sorted(set(normalized_explicit))

            return self._get_categories_from_item_name(item.get("name", ""))

        return self._get_categories_from_item_name(str(item or ""))

    def _get_categories_from_item_name(self, item_name):
        """Extract categories from an item name using normalized regex rules."""
        normalized_name = str(item_name or "").strip()
        cache_key = normalized_name.lower()
        if cache_key in self._category_cache:
            return self._category_cache[cache_key]

        if not normalized_name:
            result = ["Misc"]
            self._category_cache[cache_key] = result
            return result

        categories = set()
        searchable_parts = [normalized_name]

        # Capture meaningful chunks from "CODE - CATEGORY - DETAILS" style names.
        for part in [p.strip() for p in normalized_name.split(" - ") if p.strip()]:
            searchable_parts.append(part)

        # Tokenized fallback chunks for names with slashes/parentheses/commas.
        for token in re.split(r"[/(),]", normalized_name):
            token = token.strip()
            if token:
                searchable_parts.append(token)

        for text in searchable_parts:
            normalized_text = text.lower()
            normalized_cat = self._normalize_category_name(normalized_text)
            if normalized_cat:
                categories.add(normalized_cat)

            for cat, patterns in self._compiled_category_rules.items():
                for pattern in patterns:
                    if pattern.search(normalized_text):
                        categories.add(cat)
                        break

        result = sorted(categories) if categories else ["Misc"]
        self._category_cache[cache_key] = result
        return result

    def populate_items(self):
        """Clears and repopulates the scrollable frame with item cards."""
        scrollable_frame = self._scrollable_frame
        if scrollable_frame is None:
            return

        num_cols = self._compute_num_cols(self.canvas.winfo_width())
        self._last_num_cols = num_cols

        # Decide source of items: use assigned slots if present, otherwise master list
        assigned = getattr(self.controller, 'assigned_slots', None)
        source_items = None
        # Handle two possible shapes: old list-of-item-dicts, or new list-of-slot-wrappers with 'terms'
        if isinstance(assigned, list) and any(assigned):
            first = assigned[0]
            if isinstance(first, dict) and 'terms' in first:
                # It's the per-slot wrapper format; extract current term index published by admin
                term_idx = getattr(self.controller, 'assigned_term', 0) or 0
                extracted = []
                for idx, slot in enumerate(assigned):
                    try:
                        if not slot or not isinstance(slot, dict):
                            continue
                        terms = slot.get('terms', [])
                        if len(terms) > term_idx and terms[term_idx]:
                            item_data = dict(terms[term_idx])
                            item_data['_slot_number'] = idx + 1
                            extracted.append(item_data)
                    except Exception:
                        continue
                if extracted:
                    source_items = extracted
            else:
                # assume old-style list of item dicts
                source_items = []
                for idx, slot in enumerate(assigned):
                    if not slot or not isinstance(slot, dict):
                        continue
                    item_data = dict(slot)
                    item_data.setdefault('_slot_number', idx + 1)
                    source_items.append(item_data)

        if source_items is None:
            source_items = list(self.controller.items)

        # Filter items by selected category based on item name keywords
        selected_category = getattr(self, '_active_category', 'All Components')
        filtered_items = []
        
        for item in source_items:
            # Get categories for this item based on name keywords
            item_categories = self._get_categories_for_item(item)
            
            # Check if item matches selected category
            sel_cat = (selected_category or '').strip().lower()
            if sel_cat in ['all components', 'all categories']:
                filtered_items.append(item)
            else:
                # Check if item's categories include the selected one (case-insensitive)
                for item_cat in item_categories:
                    if item_cat.lower() == sel_cat:
                        filtered_items.append(item)
                        break

        # Skip expensive rebuild if visual layout is effectively unchanged.
        layout_signature = self._build_items_layout_signature(filtered_items, selected_category, num_cols)
        if layout_signature == self._last_layout_signature:
            return
        self._last_layout_signature = layout_signature

        # Clear existing items and pending image jobs.
        if self._deferred_loader_job:
            try:
                self.after_cancel(self._deferred_loader_job)
            except Exception:
                pass
            self._deferred_loader_job = None
        self._deferred_image_queue.clear()
        for widget in scrollable_frame.winfo_children():
            widget.destroy()

        # Repopulate grid with filtered item cards (4 columns)
        max_cols = num_cols
        
        # Configure grid columns to expand evenly
        for col in range(max_cols):
            scrollable_frame.grid_columnconfigure(col, weight=1)
        
        for i, item in enumerate(filtered_items):
            row = i // max_cols
            col = i % max_cols
            card = self.create_item_card(scrollable_frame, item)
            # Use calculated 5cm spacing between cards
            spacing_half = self.card_spacing // 2
            card.grid(row=row, column=col, padx=spacing_half, pady=spacing_half, sticky="nsew")
        
        # Schedule center_frame to run after the layout has been updated
        # This ensures we get the correct width for the scrollable_frame
        self.after(10, self.center_frame)

    def center_frame(self, event=None):
        """Callback function to center the scrollable frame inside the canvas."""
        scrollable_frame = self._scrollable_frame
        if scrollable_frame is None:
            return
        
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
        # Clear category cache since item list may have changed
        self._category_cache = {}
        self._last_layout_signature = None
        self._image_path_cache = {}
        self._missing_image_paths_logged = set()
        
        # Rebuild category buttons from assigned items (fresh list after admin changes)
        try:
            # Clear old category buttons
            for cat_btn in self._category_buttons.values():
                try:
                    cat_btn.destroy()
                except Exception:
                    pass
            self._category_buttons = {}
            
            # Rebuild categories list dynamically from item names using keywords
            categories = set(['All Components'])
            assigned = getattr(self.controller, 'assigned_slots', None)
            
            if isinstance(assigned, list) and any(assigned):
                term_idx = getattr(self.controller, 'assigned_term', 0) or 0
                for slot in assigned:
                    try:
                        if not slot or not isinstance(slot, dict):
                            continue
                        terms = slot.get('terms', [])
                        if len(terms) > term_idx and terms[term_idx]:
                            item = terms[term_idx]
                            item_cats = self._get_categories_for_item(item)
                            categories.update(item_cats)
                    except Exception:
                        continue
            else:
                # No assigned items, use default categories from item names if any
                for item in self.controller.items:
                    try:
                        item_cats = self._get_categories_for_item(item)
                        categories.update(item_cats)
                    except Exception:
                        continue
            
            # Sort categories (keep "All Components" first)
            cat_list = ['All Components'] + sorted([c for c in categories if c != 'All Components'])
            
            # Rebuild category buttons
            for cat in cat_list:
                b = tk.Button(
                    self.categories_frame,
                    text=cat,
                    relief='flat',
                    bg='#f7fafc',
                    fg='#2c3e50',
                    activebackground='#e6f0ff',
                    activeforeground='#1f2f85',
                    borderwidth=0,
                    highlightthickness=0,
                    cursor='hand2',
                    anchor='w',
                    padx=12,
                    pady=7,
                    justify='left',
                    wraplength=getattr(self, '_category_button_wraplength', 220),
                    command=lambda c=cat: self._on_category_click(c)
                )
                b.pack(fill='x', pady=2)
                self._category_buttons[cat] = b
            
            # Reset active category to "All Components"
            self._active_category = 'All Components'
            self._set_active_category_button('All Components')
            
        except Exception as e:
            print(f"[KioskFrame] Error rebuilding categories: {e}")

        self.populate_items()

    def _on_category_click(self, cat):
        """Handle category button clicks: set active category and refresh."""
        self._active_category = cat
        self._set_active_category_button(cat)
        # Always reset product list scroll to top when changing category.
        try:
            self.canvas.yview_moveto(0.0)
        except Exception:
            pass
        self.populate_items()
        # Run once after layout refresh too, so top position is preserved.
        try:
            self.after_idle(lambda: self.canvas.yview_moveto(0.0))
        except Exception:
            pass

    def _set_active_category_button(self, cat):
        """Visually mark the active category button."""
        for k, btn in getattr(self, '_category_buttons', {}).items():
            try:
                btn.configure(bg='#f7fafc', fg='#2c3e50')
            except Exception:
                pass
        try:
            btn = self._category_buttons.get(cat)
            if btn:
                btn.configure(bg='#dbe4ff', fg='#1f2f85')
        except Exception:
            pass

    def load_header_logo(self):
        """Load and display header logo image from config path."""
        try:
            logo_path = self.header_logo_path.strip() if self.header_logo_path else ''
            resolved_logo = None
            
            # Try config path first
            if logo_path:
                resolved_logo = get_absolute_path(logo_path)
                if not os.path.exists(resolved_logo):
                    # Try without path resolution in case it's absolute
                    if os.path.exists(logo_path):
                        resolved_logo = logo_path
                    else:
                        resolved_logo = None
            
            # If config path didn't work, search for common logo filenames
            if not resolved_logo:
                common_names = ['LOGO.png', 'logo.png', 'Logo.png', 'LOGO.jpg', 'logo.jpg']
                for fname in common_names:
                    test_path = get_absolute_path(fname)
                    if os.path.exists(test_path):
                        resolved_logo = test_path
                        break
            
            # If still not found, show placeholder
            if not resolved_logo:
                placeholder_text = (self.machine_name[:1] if self.machine_name else 'R').upper()
                self.logo_image_label.config(text=placeholder_text, font=self.fonts['logo_placeholder'], 
                                            fg='white', bg='#2222a8')
                return
            
            # Check cache first
            if resolved_logo in self.image_cache:
                photo = self.image_cache[resolved_logo]
                self.logo_image_label.config(image=photo, text='')
                return
            
            # Load and resize image
            img = Image.open(resolved_logo)
            max_width = 160
            max_height = int(self.header_px * 0.85)
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage and display
            photo = pil_to_photoimage(img)
            self.image_cache[resolved_logo] = photo
            self.logo_image_label.config(image=photo, text='')
        except Exception as e:
            # On error, show placeholder
            print(f"[KioskFrame] Failed to load logo: {e}")
            placeholder_text = (self.machine_name[:1] if self.machine_name else 'R').upper()
            self.logo_image_label.config(text=placeholder_text, font=self.fonts['logo_placeholder'],
                                        fg='white', bg='#2222a8')

    def _process_deferred_batch(self):
        """Process a batch of deferred image loads to avoid blocking the UI."""
        try:
            count = 0
            while self._deferred_image_queue and count < max(1, self._deferred_batch):
                image_label = self._deferred_image_queue.popleft()
                try:
                    info = getattr(image_label, '_deferred_image', None)
                    if not info:
                        continue
                    resolved_path, target_h = info
                    if resolved_path in self.image_cache:
                        photo = self.image_cache[resolved_path]
                        image_label.config(image=photo)
                        image_label.image = photo
                        continue

                    img = Image.open(resolved_path)
                    # Resize to target height while keeping aspect ratio
                    h_percent = (target_h / float(img.size[1])) if img.size[1] else 1.0
                    w_size = int((float(img.size[0]) * float(h_percent)))
                    if w_size < 1:
                        w_size = 1
                    if target_h < 1:
                        target_h = 1
                    img = img.resize((w_size, target_h), Image.Resampling.LANCZOS)
                    photo = pil_to_photoimage(img)
                    # Cache and set on label
                    self.image_cache[resolved_path] = photo
                    image_label.config(image=photo)
                    image_label.image = photo
                except Exception:
                    try:
                        image_label.config(text='No Image', font=self.fonts['image_placeholder'], fg=self.colors['gray_fg'])
                    except Exception:
                        pass
                count += 1

            # Schedule next batch if queue not empty
            if self._deferred_image_queue:
                self._deferred_loader_job = self.after(self._deferred_delay, self._process_deferred_batch)
            else:
                self._deferred_loader_job = None
        except Exception:
            self._deferred_loader_job = None

    def _compute_num_cols(self, canvas_width):
        """Compute grid columns for current canvas width."""
        if canvas_width < 2:
            return 1
        total_card_with_spacing = max(1, self.card_width + self.card_spacing)
        num_cols = max(1, canvas_width // total_card_with_spacing)
        return max(1, min(8, num_cols))

    def _build_items_layout_signature(self, items, selected_category, num_cols):
        """Build a compact signature to skip redundant full-grid rebuilds."""
        entries = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                price_val = float(item.get('price', 0) or 0)
            except Exception:
                price_val = 0.0
            try:
                qty_val = int(item.get('quantity', 0) or 0)
            except Exception:
                qty_val = 0
            entries.append((
                item.get('name', ''),
                price_val,
                qty_val,
                item.get('image', ''),
            ))
        return (str(selected_category or ''), int(num_cols), tuple(entries))

    def _resolve_image_path(self, image_path):
        """Resolve image path once and cache the result (or None)."""
        raw = str(image_path or "").replace('\\', '/').strip()
        if not raw:
            return None
        if raw in self._image_path_cache:
            return self._image_path_cache[raw]

        resolved_path = None
        if os.path.isabs(raw) and os.path.exists(raw):
            resolved_path = raw
        else:
            abs_path = get_absolute_path(raw)
            if os.path.exists(abs_path):
                resolved_path = abs_path
            elif os.path.exists(raw):
                resolved_path = raw
            elif not raw.startswith('images/'):
                fallback = f"images/{os.path.basename(raw)}"
                abs_fallback = get_absolute_path(fallback)
                if os.path.exists(abs_fallback):
                    resolved_path = abs_fallback
                elif os.path.exists(fallback):
                    resolved_path = fallback

        self._image_path_cache[raw] = resolved_path
        return resolved_path


