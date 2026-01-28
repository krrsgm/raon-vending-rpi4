import tkinter as tk
from tkinter import font as tkfont, messagebox, filedialog, ttk
import json
import os
from PIL import Image, Image


class ItemEditWindow(tk.Toplevel):
    """A Toplevel window for adding or editing an item."""

    def __init__(self, parent, controller, item_data=None):
        super().__init__(parent)
        self.controller = controller
        self.item_data = item_data

        self.title("Edit Item" if item_data else "Add New Item")
        self._center_window()
        self.configure(bg="#f0f4f8")

        self.fields = {}
        self.create_widgets()
        if item_data:
            self.populate_fields()

        # Center the window on the main application window
        # self._center_window()

        # Make the window modal
        self.transient(parent)
        self.grab_set()

        # Bind the Escape key to close the window, preventing the main window's handler
        self.bind("<Escape>", self.handle_escape_press)

    def _center_window(self):
        """Centers this Toplevel window on the main application window."""
        width = 500
        height = 350

        # Get the main application window (the controller)
        parent_window = self.controller
        parent_x = parent_window.winfo_x()
        parent_y = parent_window.winfo_y()
        parent_width = parent_window.winfo_width()
        parent_height = parent_window.winfo_height()

        x = parent_x + (parent_width // 2) - (width // 2)
        y = parent_y + (parent_height // 2) - (height // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    def handle_escape_press(self, event):
        """Handles the escape key press to close the window and stop event propagation."""
        self.destroy()
        # Return "break" to prevent the event from reaching the main window's binding
        return "break"

    def create_widgets(self):
        main_frame = tk.Frame(self, bg="#f0f4f8", padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        field_font = tkfont.Font(family="Helvetica", size=12)
        label_font = tkfont.Font(family="Helvetica", size=12, weight="bold")

        # --- Form Fields ---
        # Name field
        tk.Label(main_frame, text="Name", font=label_font, bg="#f0f4f8").grid(
            row=0, column=0, sticky="w", pady=(10, 2)
        )
        name_entry = tk.Entry(main_frame, font=field_font, width=40)
        name_entry.grid(row=0, column=1, sticky="ew", pady=(10, 2))
        self.fields["name"] = name_entry

        # Category field with combobox
        tk.Label(main_frame, text="Category", font=label_font, bg="#f0f4f8").grid(
            row=1, column=0, sticky="w", pady=(10, 2)
        )
        # Get existing categories from config
        categories = self.controller.config.get('categories', [])
        if not categories:
            categories = ["Uncategorized"]  # Default category if none exist
        category_combo = ttk.Combobox(main_frame, values=categories, font=field_font, width=38)
        category_combo.grid(row=1, column=1, sticky="ew", pady=(10, 2))
        category_combo.set(categories[0])  # Set default value
        self.fields["category"] = category_combo

        # Remaining fields
        remaining_fields = [
            ("Description", "description", True),
            ("Price", "price", False),
            ("Quantity", "quantity", False),
            ("Image Path", "image", False),
        ]

        for i, (label_text, key, is_textarea) in enumerate(remaining_fields, start=2):
            tk.Label(main_frame, text=label_text, font=label_font, bg="#f0f4f8").grid(
                row=i, column=0, sticky="w", pady=(10, 2)
            )
            if is_textarea:
                widget = tk.Text(main_frame, height=4, width=40, font=field_font)
            else:
                widget = tk.Entry(main_frame, font=field_font, width=40)
            widget.grid(row=i, column=1, sticky="ew", pady=(10, 2))
            self.fields[key] = widget

        main_frame.grid_columnconfigure(1, weight=1)

        # --- Action Buttons ---
        button_frame = tk.Frame(main_frame, bg="#f0f4f8", pady=20)
        button_frame.grid(
            row=6, column=0, columnspan=2, sticky="ew"  # After the 6 form fields
        )

        save_button = tk.Button(
            button_frame,
            text="Save",
            command=self.save_item,
            bg="#27ae60",
            fg="white",
            font=label_font,
            relief="flat",
            padx=15,
            pady=5,
        )
        save_button.pack(side="right")

        cancel_button = tk.Button(
            button_frame,
            text="Cancel",
            command=self.destroy,
            bg="#7f8c8d",
            fg="white",
            font=label_font,
            relief="flat",
            padx=15,
            pady=5,
        )
        cancel_button.pack(side="right", padx=10)

    def populate_fields(self):
        """Fills the form fields with existing item data."""
        for key, widget in self.fields.items():
            value = self.item_data.get(key, "")
            if isinstance(widget, tk.Text):
                widget.delete("1.0", tk.END)
                widget.insert("1.0", str(value))
            elif isinstance(widget, ttk.Combobox):
                # Handle category combobox - ensure category is in the list
                if value:  # If item has a category
                    current_categories = list(widget['values'])
                    if value not in current_categories:
                        # Add this category to the list if it's not there
                        current_categories.append(value)
                        widget['values'] = current_categories
                    widget.set(value)
            else:
                widget.delete(0, tk.END)
                widget.insert(0, str(value))

    def save_item(self):
        """Gathers data from fields, validates, and calls controller."""
        new_data = {}
        try:
            for key, widget in self.fields.items():
                if isinstance(widget, tk.Text):
                    value = widget.get("1.0", "end-1c").strip()
                else:
                    value = widget.get().strip()

                if key in ["price", "quantity"]:
                    if not value:
                        raise ValueError(f"{key.capitalize()} cannot be empty.")
                    new_data[key] = float(value) if key == "price" else int(value)
                elif key == "name" and not value:
                    raise ValueError("Name cannot be empty.")
                else:
                    new_data[key] = value
        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e), parent=self)
            return

        if self.item_data:  # Editing existing item
            self.controller.update_item(self.item_data["name"], new_data)
            self.destroy()
        else:  # Adding new item
            # If the item has a category that isn't in the saved config, add it
            try:
                category = new_data.get('category', '').strip()
                if category:
                    cfg = dict(getattr(self.controller, 'config', {}))
                    cats = cfg.get('categories', [])
                    if category not in cats:
                        cats.append(category)
                        cfg['categories'] = cats
                        # persist updated config
                        try:
                            with open(self.controller.config_path, 'w') as cf:
                                json.dump(cfg, cf, indent=4)
                        except Exception:
                            pass
                        # update in-memory config and notify kiosk
                        self.controller.config = cfg
                        if 'KioskFrame' in getattr(self.controller, 'frames', {}):
                            try:
                                self.controller.frames['KioskFrame'].update_kiosk_config()
                            except Exception:
                                pass
            except Exception:
                pass

            success = self.controller.add_item(new_data)
            if success:
                self.destroy()
            else:
                messagebox.showerror(
                    "Duplicate Item",
                    f"An item with the name '{new_data['name']}' already exists.",
                    parent=self
                )


class KioskConfigWindow(tk.Toplevel):
    """Modal window to configure kiosk header/footer and display settings."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.title("Kiosk Configuration")
        self.configure(bg="#f0f4f8")
        self._center_window()
        self.create_widgets()
        self.transient(parent)
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())

    def _center_window(self):
        width = 700
        height = 680
        parent = self.controller
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):
        cfg = getattr(self.controller, 'config', {})
        frame = tk.Frame(self, bg="#f0f4f8", padx=16, pady=12)
        frame.pack(fill='both', expand=True)

        label_font = tkfont.Font(family="Helvetica", size=12, weight="bold")
        field_font = tkfont.Font(family="Helvetica", size=12)

        # Machine name
        tk.Label(frame, text="Machine Name", font=label_font, bg="#f0f4f8").grid(row=0, column=0, sticky='w')
        self.machine_name_entry = tk.Entry(frame, font=field_font, width=50)
        self.machine_name_entry.grid(row=0, column=1, sticky='ew', pady=6)
        self.machine_name_entry.insert(0, cfg.get('machine_name', 'RAON'))

        # Machine subtitle
        tk.Label(frame, text="Machine Subtitle", font=label_font, bg="#f0f4f8").grid(row=1, column=0, sticky='w')
        self.machine_sub_entry = tk.Entry(frame, font=field_font, width=50)
        self.machine_sub_entry.grid(row=1, column=1, sticky='ew', pady=6)
        self.machine_sub_entry.insert(0, cfg.get('machine_subtitle', 'RApid Access Outlet for Electronic Necessities'))

        # Header logo path + browse + preview
        tk.Label(frame, text="Header Logo Path", font=label_font, bg="#f0f4f8").grid(row=2, column=0, sticky='nw', pady=6)
        logo_frame = tk.Frame(frame, bg="#f0f4f8")
        logo_frame.grid(row=2, column=1, sticky='ew', pady=6)
        self.logo_entry = tk.Entry(logo_frame, font=field_font, width=38)
        self.logo_entry.pack(side='left', fill='x', expand=True)
        self.logo_entry.insert(0, cfg.get('header_logo_path', ''))
        self.logo_entry.bind('<KeyRelease>', self.update_logo_preview)
        browse_btn = tk.Button(logo_frame, text="Browse", command=self.browse_logo)
        browse_btn.pack(side='left', padx=4)
        preview_btn = tk.Button(logo_frame, text="Preview", command=self.preview_logo)
        preview_btn.pack(side='left', padx=4)
        
        # Logo preview placeholder
        tk.Label(frame, text="Logo Preview:", font=label_font, bg="#f0f4f8").grid(row=3, column=0, sticky='nw')
        self.logo_preview_frame = tk.Frame(frame, bg="#ffffff", relief='sunken', borderwidth=2, width=400, height=100)
        self.logo_preview_frame.grid(row=3, column=1, sticky='ew', pady=6)
        self.logo_preview_frame.grid_propagate(False)
        self.logo_preview_label = tk.Label(self.logo_preview_frame, text="[No logo selected]", bg="#ffffff", fg="#7f8c8d")
        self.logo_preview_label.pack(expand=True)
        self.logo_preview_image = None

        # Display diagonal
        tk.Label(frame, text="Display diagonal (in)", font=label_font, bg="#f0f4f8").grid(row=4, column=0, sticky='w')
        self.diagonal_entry = tk.Entry(frame, font=field_font, width=20)
        self.diagonal_entry.grid(row=4, column=1, sticky='w', pady=6)
        self.diagonal_entry.insert(0, str(cfg.get('display_diagonal_inches', 13.3)))

        # Categories Management
        tk.Label(frame, text="Categories (one per line)", font=label_font, bg="#f0f4f8").grid(row=5, column=0, sticky='nw')
        self.categories_text = tk.Text(frame, height=4, font=field_font, width=50)
        self.categories_text.grid(row=5, column=1, sticky='ew', pady=6)
        categories = cfg.get('categories', [])
        if isinstance(categories, list):
            self.categories_text.insert('1.0', '\n'.join(categories))
        else:
            self.categories_text.insert('1.0', str(categories))

        # Group members (multiline)
        tk.Label(frame, text="Group Members (one per line)", font=label_font, bg="#f0f4f8").grid(row=6, column=0, sticky='nw')
        self.members_text = tk.Text(frame, height=6, font=field_font, width=50)
        self.members_text.grid(row=6, column=1, sticky='ew', pady=6)
        members = cfg.get('group_members', [])
        if isinstance(members, list):
            self.members_text.insert('1.0', '\n'.join(members))
        else:
            self.members_text.insert('1.0', str(members))

        frame.grid_columnconfigure(1, weight=1)

        btn_frame = tk.Frame(frame, bg="#f0f4f8")
        btn_frame.grid(row=7, column=0, columnspan=2, sticky='e', pady=(12,0))
        save_btn = tk.Button(btn_frame, text="Save", bg="#27ae60", fg='white', command=self.save_config)
        save_btn.pack(side='right')
        cancel_btn = tk.Button(btn_frame, text="Cancel", bg="#7f8c8d", fg='white', command=self.destroy)
        cancel_btn.pack(side='right', padx=8)

    def browse_logo(self):
        path = filedialog.askopenfilename(title='Select header logo', filetypes=[('Image files', '*.png;*.jpg;*.jpeg;*.gif;*.bmp')])
        if path:
            self.logo_entry.delete(0, tk.END)
            self.logo_entry.insert(0, path)
            self.update_logo_preview()
    
    def update_logo_preview(self, event=None):
        """Update logo preview as user types the path."""
        logo_path = self.logo_entry.get().strip()
        
        # Clear previous preview
        self.logo_preview_label.config(image='')
        self.logo_preview_image = None
        
        if not logo_path:
            self.logo_preview_label.config(text="[No logo selected]")
            return
        
        if not os.path.exists(logo_path):
            self.logo_preview_label.config(text=f"[File not found]")
            return
        
        try:
            img = Image.open(logo_path)
            # Scale to fit preview frame (max 390x90 to fit in 400x100 with padding)
            img.thumbnail((390, 90), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.logo_preview_image = photo  # Keep reference
            self.logo_preview_label.config(image=photo, text="")
        except Exception as e:
            self.logo_preview_label.config(text=f"[Error: {str(e)[:30]}]")
    
    def preview_logo(self):
        """Show a larger preview of the selected logo."""
        logo_path = self.logo_entry.get().strip()
        if not logo_path:
            messagebox.showinfo('No Logo', 'Please select a logo path first.', parent=self)
            return
        if not os.path.exists(logo_path):
            messagebox.showerror('File Not Found', f'Logo file not found: {logo_path}', parent=self)
            return
        
        try:
            # Create a preview window
            preview_win = tk.Toplevel(self)
            preview_win.title('Logo Preview')
            img = Image.open(logo_path)
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(preview_win, image=photo)
            lbl.image = photo
            lbl.pack(padx=10, pady=10)
            preview_win.geometry(f"{img.width + 20}x{img.height + 20}")
        except Exception as e:
            messagebox.showerror('Preview Error', f'Could not preview logo: {e}', parent=self)

    def save_config(self):
        # Gather and validate
        new_cfg = dict(getattr(self.controller, 'config', {}))
        new_cfg['machine_name'] = self.machine_name_entry.get().strip() or 'RAON'
        new_cfg['machine_subtitle'] = self.machine_sub_entry.get().strip() or 'RApid Access Outlet for Electronic Necessities'
        new_cfg['header_logo_path'] = self.logo_entry.get().strip()
        try:
            new_cfg['display_diagonal_inches'] = float(self.diagonal_entry.get().strip())
        except Exception:
            messagebox.showerror('Invalid Input', 'Display diagonal must be a number.', parent=self)
            return

        # Save categories
        categories_raw = self.categories_text.get('1.0', 'end-1c')
        categories = [c.strip() for c in categories_raw.splitlines() if c.strip()]
        new_cfg['categories'] = categories

        members_raw = self.members_text.get('1.0', 'end-1c')
        members = [m.strip() for m in members_raw.splitlines() if m.strip()]
        new_cfg['group_members'] = members

        # Write to config file
        try:
            with open(self.controller.config_path, 'w') as f:
                json.dump(new_cfg, f, indent=4)
            self.controller.config = new_cfg
            # Notify kiosk frame to update if present
            if 'KioskFrame' in getattr(self.controller, 'frames', {}):
                try:
                    self.controller.frames['KioskFrame'].update_kiosk_config()
                except Exception as e:
                    print(f"Failed to update kiosk frame: {e}")
            self.destroy()
        except Exception as e:
            messagebox.showerror('Save Error', f'Failed to save config: {e}', parent=self)


class AdminScreen(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg="#f0f4f8")  # Light background
        self.controller = controller
        self.scan_start_x = 0  # For drag-to-scroll

        self.fonts = {
            "header": tkfont.Font(family="Helvetica", size=24, weight="bold"),
            "item_name": tkfont.Font(family="Helvetica", size=14, weight="bold"),
            "item_details": tkfont.Font(family="Helvetica", size=12),
            "item_description": tkfont.Font(family="Helvetica", size=11),
            "button": tkfont.Font(family="Helvetica", size=12, weight="bold"),
        }
        self.colors = {
            "background": "#f0f4f8",
            "header_fg": "#2c3e50",
            "card_bg": "#ffffff",
            "border": "#dfe6e9",
            "edit_btn_bg": "#3498db",
            "remove_btn_bg": "#e74c3c",
            "btn_fg": "#ffffff",
        }

        self.create_widgets()
        self.bind("<<ShowFrame>>", lambda e: self.populate_items())

        exit_label = tk.Label(
            self,
            text="Press 'Esc' to return to Selection Screen",
            font=("Helvetica", 12),
            fg="#7f8c8d",  # Gray text
            bg="#f0f4f8",
        )
        exit_label.pack(side="bottom", pady=20)

    def create_widgets(self):
        # --- Header ---
        header = tk.Frame(self, bg=self.colors["background"])
        header.pack(fill="x", padx=20, pady=20)
        tk.Label(
            header,
            text="Manage Items",
            font=self.fonts["header"],
            bg=self.colors["background"],
            fg=self.colors["header_fg"],
        ).pack(side="left")

        # "Add New Item" button removed — admin now uses Assign Slots

        # Kiosk configuration button (opens modal to edit header/footer)
        kiosk_cfg_btn = tk.Button(
            header,
            text="Kiosk Config",
            font=self.fonts["button"],
            bg="#3498db",
            fg=self.colors["btn_fg"],
            relief="flat",
            padx=12,
            pady=5,
            command=self.open_kiosk_config,
        )
        kiosk_cfg_btn.pack(side="right", padx=(0, 8))

        # Button to open Assign Items screen (6x10 grid)
        assign_slots_btn = tk.Button(
            header,
            text="Assign Slots",
            font=self.fonts["button"],
            bg="#8e44ad",
            fg=self.colors["btn_fg"],
            relief="flat",
            padx=12,
            pady=5,
            command=lambda: getattr(self.controller, 'show_assign_items', lambda: None)(),
        )
        assign_slots_btn.pack(side="right", padx=(0, 8))

        # --- Scrollable Item List ---
        canvas_container = tk.Frame(self, bg=self.colors["background"])
        canvas_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.canvas = tk.Canvas(
            canvas_container, bg=self.colors["background"], highlightthickness=0
        )
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.colors["background"])

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )

        self.canvas.pack(side="left", fill="both", expand=True)

        # --- Bindings for Scrolling ---
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.scrollable_frame.bind("<ButtonPress-1>", self.on_canvas_press)
        self.scrollable_frame.bind("<B1-Motion>", self.on_canvas_drag)

        # Bind mouse wheel to scroll (works on all frames)
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def on_canvas_configure(self, event):
        """On canvas resize, update the width of the inner frame."""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

    def on_canvas_press(self, event):
        """Records the starting y-position and fixed x-position of a mouse drag."""
        self.canvas.scan_mark(event.x, event.y)
        self.scan_start_x = event.x

    def on_canvas_drag(self, event):
        """Moves the canvas view vertically based on mouse drag."""
        self.canvas.scan_dragto(self.scan_start_x, event.y, gain=1)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def populate_items(self):
        # Clear existing items
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Repopulate with current items
        for item in self.controller.items:
            card = self.create_item_card(self.scrollable_frame, item)
            card.pack(fill="x", padx=10, pady=5)

    def create_item_card(self, parent, item_data):
        card = tk.Frame(
            parent,
            bg=self.colors["card_bg"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
        )
        card.grid_columnconfigure(0, weight=1)

        info_frame = tk.Frame(card, bg=card["bg"])
        info_frame.grid(row=0, column=0, padx=15, pady=10, sticky="ew")

        tk.Label(
            info_frame,
            text=item_data["name"],
            font=self.fonts["item_name"],
            bg=card["bg"],
            anchor="w",
        ).pack(fill="x")
        # Display category
        tk.Label(
            info_frame,
            text=f"Category: {item_data.get('category', 'Uncategorized')}",  # Default to 'Uncategorized' if no category
            font=self.fonts["item_description"],
            bg=card["bg"],
            fg="#3498db",  # Blue color for category
            anchor="w"
        ).pack(fill="x", pady=(2, 4))

        tk.Label(
            info_frame,
            text=item_data["description"],
            font=self.fonts["item_description"],
            bg=card["bg"],
            fg="#7f8c8d",
            anchor="w",
            justify="left",
            wraplength=600,  # Adjust as needed for your screen width
        ).pack(fill="x", pady=(2, 4))
        tk.Label(
            info_frame,
            text=f"Price: {self.controller.currency_symbol}{item_data['price']:.2f} | Qty: {item_data['quantity']}",
            font=self.fonts["item_details"],
            bg=card["bg"],
            fg="#7f8c8d",
            anchor="w",
        ).pack(fill="x")

        button_frame = tk.Frame(card, bg=card["bg"])
        button_frame.grid(row=0, column=1, padx=15, pady=10, sticky="e")

        edit_button = tk.Button(
            button_frame,
            text="Edit",
            font=self.fonts["button"],
            bg=self.colors["edit_btn_bg"],
            fg=self.colors["btn_fg"],
            relief="flat",
            command=lambda i=item_data: self.edit_item(i),
        )
        edit_button.pack(side="left", padx=(0, 5))

        remove_button = tk.Button(
            button_frame,
            text="Remove",
            font=self.fonts["button"],
            bg=self.colors["remove_btn_bg"],
            fg=self.colors["btn_fg"],
            relief="flat",
            command=lambda i=item_data: self.remove_item(i),
        )
        remove_button.pack(side="left")

        # --- Bind drag-scroll events to all widgets on the card ---
        # This ensures that dragging anywhere on the card scrolls the canvas.
        # The buttons will still work because their `command` handles the click.
        widgets_to_bind = [card, info_frame] + info_frame.winfo_children()

        for widget in widgets_to_bind:
            # Exclude buttons from having their primary click action overridden
            if not isinstance(widget, tk.Button):
                widget.bind("<ButtonPress-1>", self.on_canvas_press)
                widget.bind("<B1-Motion>", self.on_canvas_drag)
            # The button_frame and its buttons are not bound, so their commands work.


        return card

    def add_new_item(self):
        ItemEditWindow(self, self.controller)

    def open_kiosk_config(self):
        KioskConfigWindow(self, self.controller)

    def edit_item(self, item_data):
        ItemEditWindow(self, self.controller, item_data)

    def remove_item(self, item_to_remove):
        if messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to remove '{item_to_remove['name']}'?",
        ):
            self.controller.remove_item(item_to_remove)
