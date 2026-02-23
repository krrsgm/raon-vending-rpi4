import tkinter as tk
from tkinter import font as tkfont, ttk
from PIL import Image
import os
import io
import platform
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
        self._resize_job = None
        self.image_cache = {} # To prevent images from being garbage-collected
        self._category_cache = {} # Cache for category detection (item_name -> categories)

        # --- Color and Font Scheme ---
        self.colors = {
            'background': '#f0f4f8',
            'card_bg': '#ffffff',
            'text_fg': "#1d3502",
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
            'category': tkfont.Font(family="Helvetica", size=8),
            'control_small': tkfont.Font(family="Helvetica", size=9),
            'control_bold': tkfont.Font(family="Helvetica", size=9, weight="bold"),
            'cart_btn': tkfont.Font(family="Helvetica", size=14, weight="bold"),
        }
        
        # Pre-compute keyword map for fast category detection (only once, not per item)
        self._keyword_map = {
            'Resistor': ['resistor', 'ohm'],
            'Capacitor': ['capacitor', 'farad', 'µf', 'uf', 'pf'],
            'IC': ['ic', 'chip', 'integrated circuit'],
            'Amplifier': ['amplifier', 'amp', 'opamp', 'op-amp'],
            'Board': ['board', 'pcb', 'breadboard', 'shield'],
            'Bundle': ['bundle', 'kit', 'pack'],
            'Wires': ['wire', 'cable', 'cord', 'lead']
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
        """Creates a single item card widget with dimensions: 1in width x 2.5in height."""
        # Determine stock status and color-coding
        quantity = item_data.get('quantity', 0)
        default_threshold = 3  # Default low stock threshold
        
        # Determine stock status color
        if quantity <= 0:
            stock_status = 'out_of_stock'
            border_color = '#e74c3c'  # Red
            stock_indicator = '❌ OUT'
        elif quantity <= default_threshold:
            stock_status = 'low_stock'
            border_color = '#f39c12'  # Orange/Yellow
            stock_indicator = f'⚠️ {quantity}'
        else:
            stock_status = 'in_stock'
            border_color = '#27ae60'  # Green
            stock_indicator = f'✓ {quantity}'
        
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
            # Normalize path separators (convert backslash to forward slash for cross-platform consistency)
            image_path = image_path.replace('\\', '/')
            # Try to resolve the image path - could be relative or absolute
            resolved_path = None
            debug_log = []
            debug_log.append(f"Looking for image: {image_path}")
            
            # If it's an absolute path, check if it exists
            if os.path.isabs(image_path) and os.path.exists(image_path):
                resolved_path = image_path
                debug_log.append(f"✓ Found as absolute path")
            else:
                # Try as relative path from project root via get_absolute_path
                abs_path = get_absolute_path(image_path)
                debug_log.append(f"  get_absolute_path -> {abs_path}")
                if os.path.exists(abs_path):
                    resolved_path = abs_path
                    debug_log.append(f"  ✓ Exists at get_absolute_path result")
                else:
                    debug_log.append(f"  ✗ Does not exist")
                    
                # Try as relative path from current directory
                if not resolved_path and os.path.exists(image_path):
                    resolved_path = image_path
                    debug_log.append(f"✓ Found in current directory: {image_path}")
                
                # Also try from images/ directly if no images/ prefix
                if not resolved_path and not image_path.startswith('images/'):
                    fallback = f"images/{os.path.basename(image_path)}"
                    abs_fallback = get_absolute_path(fallback)
                    debug_log.append(f"  Trying fallback: {fallback} -> {abs_fallback}")
                    if os.path.exists(abs_fallback):
                        resolved_path = abs_fallback
                        debug_log.append(f"  ✓ Found via fallback")
                    elif os.path.exists(fallback):
                        resolved_path = fallback
                        debug_log.append(f"  ✓ Found fallback in cwd")
            
            if resolved_path:
                try:
                    # Open, resize, and display the image
                    img = Image.open(resolved_path)
                    
                    # Resize image to fit the frame height while maintaining aspect ratio
                    base_height = image_height - 8  # Account for padding
                    h_percent = (base_height / float(img.size[1]))
                    w_size = int((float(img.size[0]) * float(h_percent)))
                    img = img.resize((w_size, base_height), Image.Resampling.LANCZOS)

                    photo = pil_to_photoimage(img)
                    image_label.config(image=photo)
                    image_label.image = photo # Keep a reference!
                except Exception as e:
                    print(f"Error loading image {resolved_path}: {e}")
                    print("\n".join(debug_log))
                    image_label.config(text="Image Error", font=self.fonts['image_placeholder'], fg=self.colors['gray_fg'])
            else:
                # Show placeholder if image not found
                print(f"Image not found: {image_path}")
                print("\n".join(debug_log))
                image_label.config(text="No Image", font=self.fonts['image_placeholder'], fg=self.colors['gray_fg'])
        else:
            # Show placeholder if no image
            image_label.config(text="No Image", font=self.fonts['image_placeholder'], fg=self.colors['gray_fg'])



        # Frame for text content - minimal padding
        text_frame = tk.Frame(card, bg=self.colors['card_bg'])
        text_frame.pack(fill='x', padx=2)

        # 1. Name of item
        name_label = tk.Label(
            text_frame,
            text=item_data.get('name',''),
            font=self.fonts['name'],
            bg=self.colors['card_bg'],
            fg=self.colors['text_fg'],
            anchor='w'
        )
        name_label.pack(fill='x', pady=(6, 2))

        # 1b. Category based on item name keywords
        item_categories = self._get_categories_from_item_name(item_data.get('name', ''))
        category_text = ', '.join(item_categories) if item_categories else 'Misc'
        category_label = tk.Label(
            text_frame,
            text=f"Category: {category_text}",
            font=self.fonts['category'],
            bg=self.colors['card_bg'],
            fg='#8B7355',
            anchor='w'
        )
        category_label.pack(fill='x', pady=(0, 2))

        # 2. Short description
        desc_label = tk.Label(
            text_frame,
            text=item_data.get('description',''),
            font=self.fonts['description'],
            bg=self.colors['card_bg'],
            fg=self.colors['gray_fg'],
            wraplength=260,
            justify='left',
            anchor='nw'
        )
        desc_label.pack(fill='x', pady=(0, 8))

        # Bottom controls: price (left) and qty + add button (right)
        bottom_frame = tk.Frame(card, bg=self.colors['card_bg'])
        bottom_frame.pack(fill='x', padx=10, pady=(0, 10))

        # Use configured currency symbol from controller.config when available
        cfg = getattr(self.controller, 'config', {}) or {}
        currency = cfg.get('currency_symbol', getattr(self.controller, 'currency_symbol', '₱'))
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
        
        cart_btn = tk.Button(right_frame, text='Cart', bg='white', fg='#2222a8', relief='flat', font=self.fonts['cart_btn'], padx=20, pady=10, command=lambda: self.controller.show_cart())
        cart_btn.pack()

        # Main content area: left sidebar + main product area
        content = tk.Frame(self, bg=self.colors['background'])
        content.pack(fill='both', expand=True)
        
        # Left sidebar
        sidebar = tk.Frame(content, width=260, bg='#f7fafc')
        sidebar.pack(side='left', fill='y', padx=(12,6), pady=12)
        sidebar.pack_propagate(False)

        # (Search box removed — category-only browsing)

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
                            item_name = item.get('name', '')
                            # Get categories from item name keywords
                            item_cats = self._get_categories_from_item_name(item_name)
                            categories.update(item_cats)
                    except Exception:
                        continue
            else:
                # No assigned items, use default categories from item names if any
                for item in self.controller.items:
                    try:
                        item_name = item.get('name', '')
                        item_cats = self._get_categories_from_item_name(item_name)
                        categories.update(item_cats)
                    except Exception:
                        continue
            
            return ['All Components'] + sorted([c for c in categories if c != 'All Components'])
        
        # Initial population
        categories = build_categories()
        
        for cat in categories:
            b = tk.Button(self.categories_frame, text=cat, relief='flat', bg='#f7fafc', anchor='w', command=lambda c=cat: self._on_category_click(c))
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

        # Enable mouse wheel / touchpad scrolling for the kiosk (cross-platform)
        def _on_mousewheel_kiosk(event):
            try:
                # Prefer using event.delta (Windows/macOS). delta is multiple of 120 on Windows.
                if hasattr(event, 'delta') and event.delta:
                    # Normalize to number of scroll units
                    step = int(event.delta / 120)
                    # Reverse sign for natural scrolling consistency
                    if step != 0:
                        self.canvas.yview_scroll(-step, 'units')
                        return
                # Fallback for X11 mouse wheel (Button-4/5)
                if getattr(event, 'num', None) == 4:
                    self.canvas.yview_scroll(-3, 'units')
                elif getattr(event, 'num', None) == 5:
                    self.canvas.yview_scroll(3, 'units')
            except Exception:
                pass

        # Bind wheel events for different platforms
        try:
            # Windows and macOS: bind to canvas and scrollable frame too
            self.canvas.bind_all('<MouseWheel>', _on_mousewheel_kiosk)
            scrollable_frame.bind('<MouseWheel>', _on_mousewheel_kiosk)
        except Exception:
            pass
        try:
            # Linux (X11)
            self.canvas.bind_all('<Button-4>', _on_mousewheel_kiosk)
            self.canvas.bind_all('<Button-5>', _on_mousewheel_kiosk)
            scrollable_frame.bind('<Button-4>', _on_mousewheel_kiosk)
            scrollable_frame.bind('<Button-5>', _on_mousewheel_kiosk)
        except Exception:
            pass

        # Populate grid with item cards
        self.populate_items()

        # System Status Panel (shows hardware and sensor status)
        self.status_panel = SystemStatusPanel(self, controller=self.controller)
        self.status_panel.pack(side='bottom', fill='x')

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

    def _get_categories_from_item_name(self, item_name):
        """Extract categories from item name based on keywords (cached).
        
        Returns a list of categories the item belongs to based on keywords.
        If no keywords match, returns ['Misc'].
        An item can belong to multiple categories if multiple keywords are found.
        """
        # Check cache first
        if item_name in self._category_cache:
            return self._category_cache[item_name]
        
        if not item_name:
            result = ['Misc']
            self._category_cache[item_name] = result
            return result
        
        name_lower = item_name.lower()
        categories = set()
        
        # Check each category for keywords using pre-computed keyword map
        for cat, keywords in self._keyword_map.items():
            for keyword in keywords:
                if keyword in name_lower:
                    categories.add(cat)
                    break  # Found this category, move to next
        
        # If no categories matched, put in Misc
        result = sorted(list(categories)) if categories else ['Misc']
        self._category_cache[item_name] = result
        return result

    def populate_items(self):
        """Clears and repopulates the scrollable frame with item cards."""
        scrollable_frame = self.canvas.nametowidget(self.canvas.itemcget(self.canvas_window, 'window'))

        # Clear existing items
        for widget in scrollable_frame.winfo_children():
            widget.destroy()

        # --- Dynamic Column Calculation Based on Screen Size ---
        # Calculate how many cards can fit in the available width
        canvas_width = self.canvas.winfo_width()
        if canvas_width < 2:
            # Canvas not yet drawn, use default
            num_cols = 4
        else:
            # Calculate columns: (available_width) / (card_width + spacing)
            # spacing_half is on each side, so total spacing between cards is 2 * spacing_half
            total_card_with_spacing = self.card_width + self.card_spacing
            num_cols = max(1, canvas_width // total_card_with_spacing)
            # Ensure at least 3 columns for better use of screen space, at most 8 for smaller screens
            num_cols = max(3, min(8, num_cols))

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
                for slot in assigned:
                    try:
                        if not slot or not isinstance(slot, dict):
                            continue
                        terms = slot.get('terms', [])
                        if len(terms) > term_idx and terms[term_idx]:
                            extracted.append(terms[term_idx])
                    except Exception:
                        continue
                if extracted:
                    source_items = extracted
            else:
                # assume old-style list of item dicts
                source_items = [s for s in assigned if s]

        if source_items is None:
            source_items = list(self.controller.items)

        # Filter items by selected category based on item name keywords
        selected_category = getattr(self, '_active_category', 'All Components')
        filtered_items = []
        
        for item in source_items:
            # Get categories for this item based on name keywords
            item_categories = self._get_categories_from_item_name(item.get('name', ''))
            
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
        # Clear category cache since item list may have changed
        self._category_cache = {}
        
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
                            item_name = item.get('name', '')
                            # Get categories from item name keywords
                            item_cats = self._get_categories_from_item_name(item_name)
                            categories.update(item_cats)
                    except Exception:
                        continue
            else:
                # No assigned items, use default categories from item names if any
                for item in self.controller.items:
                    try:
                        item_name = item.get('name', '')
                        item_cats = self._get_categories_from_item_name(item_name)
                        categories.update(item_cats)
                    except Exception:
                        continue
            
            # Sort categories (keep "All Components" first)
            cat_list = ['All Components'] + sorted([c for c in categories if c != 'All Components'])
            
            # Rebuild category buttons
            for cat in cat_list:
                b = tk.Button(self.categories_frame, text=cat, relief='flat', bg='#f7fafc', anchor='w', command=lambda c=cat: self._on_category_click(c))
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
        self.populate_items()

    def _set_active_category_button(self, cat):
        """Visually mark the active category button."""
        for k, btn in getattr(self, '_category_buttons', {}).items():
            try:
                btn.configure(bg='#f7fafc', fg='black')
            except Exception:
                pass
        try:
            btn = self._category_buttons.get(cat)
            if btn:
                btn.configure(bg='#e6f0ff', fg='black')
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
