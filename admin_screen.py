import tkinter as tk
from tkinter import font as tkfont, messagebox, filedialog, ttk
import json
import os
import time
import threading
import platform
from PIL import Image
import io
from system_status_panel import SystemStatusPanel
from fix_paths import get_absolute_path
from display_profile import get_display_profile
from coin_hopper import CoinHopper
from arduino_serial_utils import detect_arduino_serial_port
try:
    from dht22_handler import get_shared_serial_reader
except Exception:
    get_shared_serial_reader = None

def pil_to_photoimage(pil_image):
    """Convert PIL Image to Tkinter PhotoImage using PPM format (no ImageTk needed)"""
    with io.BytesIO() as output:
        pil_image.save(output, format="PPM")
        data = output.getvalue()
    return tk.PhotoImage(data=data)


def _get_touch_metrics(controller):
    """Build touch sizing based on current screen density."""
    profile = get_display_profile(controller)
    ppi = profile["ppi"]

    touch_px = max(44, int(ppi * 0.30))
    button_font_size = max(12, int(touch_px * 0.30))
    field_font_size = max(12, int(touch_px * 0.29))

    return {
        "touch_px": touch_px,
        "button_font_size": button_font_size,
        "field_font_size": field_font_size,
        "label_font_size": max(12, field_font_size),
        "button_padx": max(14, int(touch_px * 0.45)),
        "button_pady": max(8, int(touch_px * 0.20)),
        "row_pady": max(8, int(touch_px * 0.18)),
        "entry_ipady": max(4, int(touch_px * 0.10)),
        "section_padx": max(16, int(touch_px * 0.40)),
        "section_pady": max(12, int(touch_px * 0.30)),
        "combo_style": "AdminTouch.TCombobox",
    }


def _ensure_admin_touch_ttk_styles(widget, metrics):
    """Define ttk styles with larger touch targets for admin forms."""
    try:
        style = ttk.Style(widget)
        style.configure(
            metrics["combo_style"],
            font=("Helvetica", metrics["field_font_size"]),
            padding=(8, max(6, metrics["entry_ipady"] + 1), 8, max(6, metrics["entry_ipady"] + 1)),
            arrowsize=max(14, metrics["field_font_size"] + 4),
        )
    except Exception:
        pass


def _fit_window_to_screen(controller, desired_width, desired_height):
    """Clamp modal size so it always stays visible on the current display."""
    try:
        screen_w = max(320, int(controller.winfo_screenwidth()) - 40)
        screen_h = max(240, int(controller.winfo_screenheight()) - 40)
    except Exception:
        screen_w = desired_width
        screen_h = desired_height

    width = max(320, min(int(desired_width), screen_w))
    height = max(240, min(int(desired_height), screen_h))
    return width, height


class ItemEditWindow(tk.Toplevel):
    """A Toplevel window for adding or editing an item."""

    def __init__(self, parent, controller, item_data=None):
        super().__init__(parent)
        self.controller = controller
        self.item_data = item_data
        self.is_edit_mode = item_data is not None
        self.touch = _get_touch_metrics(controller)
        _ensure_admin_touch_ttk_styles(self, self.touch)

        self.title("Edit Item" if item_data else "Add New Item")
        self._center_window()
        self.configure(bg="#f0f4f8")

        self.fields = {}
        self.create_widgets()
        if item_data:
            self.populate_fields()
            self._lock_non_stock_fields()

        # Center the window on the main application window
        # self._center_window()

        # Make the window modal
        self.transient(parent)
        self.grab_set()

        # Bind the Escape key to close the window, preventing the main window's handler
        self.bind("<Escape>", self.handle_escape_press)

    def _center_window(self):
        """Centers this Toplevel window on the main application window."""
        desired_width = max(560, int(self.controller.winfo_screenwidth() * 0.52))
        desired_height = max(440, int(self.controller.winfo_screenheight() * 0.62))
        width, height = _fit_window_to_screen(self.controller, desired_width, desired_height)

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

    def _adjust_numeric_entry(self, entry, delta, integer=False, minimum=0):
        """Adjust a numeric entry value using touch buttons."""
        try:
            raw = entry.get().strip()
            value = int(raw) if integer else float(raw)
        except Exception:
            value = 0 if integer else 0.0

        value += delta
        if value < minimum:
            value = minimum

        entry.delete(0, tk.END)
        if integer:
            entry.insert(0, str(int(value)))
        else:
            entry.insert(0, f"{float(value):.2f}")

    def _create_stepper_field(self, parent, row, key, field_font, integer=False, step=1):
        """Create a touch-friendly numeric field with minus/plus buttons."""
        value_frame = tk.Frame(parent, bg="#f0f4f8")
        value_frame.grid(row=row, column=1, sticky="w", pady=(self.touch["row_pady"], 4))

        button_font = tkfont.Font(family="Helvetica", size=max(12, self.touch["button_font_size"]), weight="bold")
        minus_btn = tk.Button(
            value_frame,
            text="-",
            font=button_font,
            bg="#7f8c8d",
            fg="white",
            relief="flat",
            width=3,
            padx=max(8, self.touch["button_padx"] - 8),
            pady=max(4, self.touch["button_pady"] - 2),
            command=lambda: self._adjust_numeric_entry(self.fields[key], -step, integer=integer),
        )
        minus_btn.pack(side="left")

        entry = tk.Entry(value_frame, font=field_font, width=12, justify="center")
        entry.pack(side="left", padx=8, ipady=self.touch["entry_ipady"])

        plus_btn = tk.Button(
            value_frame,
            text="+",
            font=button_font,
            bg="#27ae60",
            fg="white",
            relief="flat",
            width=3,
            padx=max(8, self.touch["button_padx"] - 8),
            pady=max(4, self.touch["button_pady"] - 2),
            command=lambda: self._adjust_numeric_entry(self.fields[key], step, integer=integer),
        )
        plus_btn.pack(side="left")

        self.fields[key] = entry
        return entry

    def create_widgets(self):
        main_frame = tk.Frame(
            self,
            bg="#f0f4f8",
            padx=self.touch["section_padx"],
            pady=self.touch["section_pady"],
        )
        main_frame.pack(fill="both", expand=True)

        field_font = tkfont.Font(family="Helvetica", size=self.touch["field_font_size"])
        label_font = tkfont.Font(family="Helvetica", size=self.touch["label_font_size"], weight="bold")
        row_pady = self.touch["row_pady"]

        # --- Form Fields ---
        # Name field
        tk.Label(main_frame, text="Name", font=label_font, bg="#f0f4f8").grid(
            row=0, column=0, sticky="w", pady=(row_pady, 4)
        )
        name_entry = tk.Entry(main_frame, font=field_font, width=40)
        name_entry.grid(row=0, column=1, sticky="ew", pady=(row_pady, 4), ipady=self.touch["entry_ipady"])
        self.fields["name"] = name_entry

        # Category field with combobox
        tk.Label(main_frame, text="Category", font=label_font, bg="#f0f4f8").grid(
            row=1, column=0, sticky="w", pady=(row_pady, 4)
        )
        # Get existing categories from config
        categories = self.controller.config.get('categories', [])
        if not categories:
            categories = ["Uncategorized"]  # Default category if none exist
        category_combo = ttk.Combobox(
            main_frame,
            values=categories,
            font=field_font,
            width=38,
            style=self.touch["combo_style"],
        )
        category_combo.grid(row=1, column=1, sticky="ew", pady=(row_pady, 4), ipady=self.touch["entry_ipady"])
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
                row=i, column=0, sticky="w", pady=(row_pady, 4)
            )
            if is_textarea:
                widget = tk.Text(main_frame, height=5, width=40, font=field_font)
                widget.config(padx=8, pady=6)
            elif key == "price":
                widget = self._create_stepper_field(main_frame, i, key, field_font, integer=False, step=1)
            elif key == "quantity":
                widget = self._create_stepper_field(main_frame, i, key, field_font, integer=True, step=1)
            else:
                widget = tk.Entry(main_frame, font=field_font, width=40)
            if key not in {"price", "quantity"}:
                widget.grid(
                    row=i,
                    column=1,
                    sticky="ew",
                    pady=(row_pady, 4),
                    ipady=0 if is_textarea else self.touch["entry_ipady"],
                )
                self.fields[key] = widget

        if self.is_edit_mode:
            tk.Label(
                main_frame,
                text="Edit mode: only Price and Quantity can be changed.",
                font=tkfont.Font(family="Helvetica", size=10, weight="bold"),
                bg="#f0f4f8",
                fg="#2c3e50",
                anchor="w",
            ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(8, 0))

        main_frame.grid_columnconfigure(1, weight=1)

        # --- Action Buttons ---
        button_frame = tk.Frame(main_frame, bg="#f0f4f8", pady=max(16, row_pady))
        button_frame.grid(
            row=7 if self.is_edit_mode else 6, column=0, columnspan=2, sticky="ew"  # After the form fields
        )

        save_button = tk.Button(
            button_frame,
            text="Save",
            command=self.save_item,
            bg="#27ae60",
            fg="white",
            font=label_font,
            relief="flat",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
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
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
        )
        cancel_button.pack(side="right", padx=12)

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

    def _lock_non_stock_fields(self):
        """In edit mode, keep only price/quantity editable."""
        editable = {"price", "quantity"}
        for key, widget in self.fields.items():
            if key in editable:
                continue
            try:
                if isinstance(widget, tk.Text):
                    widget.config(state="disabled")
                elif isinstance(widget, ttk.Combobox):
                    widget.configure(state="disabled")
                elif isinstance(widget, tk.Entry):
                    widget.config(state="readonly")
            except Exception:
                pass

    def save_item(self):
        """Gathers data from fields, validates, and calls controller."""
        if self.item_data:  # Editing existing item
            # Edit mode only updates price and quantity; other fields are preserved.
            try:
                price_raw = self.fields["price"].get().strip()
                qty_raw = self.fields["quantity"].get().strip()
                if not price_raw:
                    raise ValueError("Price cannot be empty.")
                if not qty_raw:
                    raise ValueError("Quantity cannot be empty.")
                price_val = float(price_raw)
                qty_val = int(qty_raw)
            except ValueError as e:
                messagebox.showerror("Invalid Input", str(e), parent=self)
                return

            merged_data = dict(self.item_data)
            merged_data["price"] = price_val
            merged_data["quantity"] = qty_val
            self.controller.update_item(self.item_data["name"], merged_data)
            self.destroy()
        else:  # Adding new item
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
        self.touch = _get_touch_metrics(controller)
        _ensure_admin_touch_ttk_styles(self, self.touch)
        self.title("Kiosk Configuration")
        self.configure(bg="#f0f4f8")
        self._center_window()
        self.create_widgets()
        self.transient(parent)
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())

    def _center_window(self):
        width = max(320, int(self.controller.winfo_screenwidth()))
        height = max(240, int(self.controller.winfo_screenheight()))
        try:
            self.attributes("-fullscreen", True)
        except Exception:
            self.geometry(f"{width}x{height}+0+0")

    def create_widgets(self):
        cfg = getattr(self.controller, 'config', {})
        frame = tk.Frame(
            self,
            bg="#f0f4f8",
            padx=self.touch["section_padx"],
            pady=self.touch["section_pady"],
        )
        frame.pack(fill='both', expand=True)

        label_font = tkfont.Font(family="Helvetica", size=self.touch["label_font_size"], weight="bold")
        field_font = tkfont.Font(family="Helvetica", size=self.touch["field_font_size"])
        row_pady = self.touch["row_pady"]

        # Machine name
        tk.Label(frame, text="Machine Name", font=label_font, bg="#f0f4f8").grid(row=0, column=0, sticky='w', pady=(row_pady, 0))
        self.machine_name_entry = tk.Entry(frame, font=field_font, width=50)
        self.machine_name_entry.grid(row=0, column=1, sticky='ew', pady=(row_pady, 0), ipady=self.touch["entry_ipady"])
        self.machine_name_entry.insert(0, cfg.get('machine_name', 'RAON'))

        # Machine subtitle
        tk.Label(frame, text="Machine Subtitle", font=label_font, bg="#f0f4f8").grid(row=1, column=0, sticky='w', pady=(row_pady, 0))
        self.machine_sub_entry = tk.Entry(frame, font=field_font, width=50)
        self.machine_sub_entry.grid(row=1, column=1, sticky='ew', pady=(row_pady, 0), ipady=self.touch["entry_ipady"])
        self.machine_sub_entry.insert(0, cfg.get('machine_subtitle', 'RApid Access Outlet for Electronic Necessities'))

        # Header logo path + browse + preview
        tk.Label(frame, text="Header Logo Path", font=label_font, bg="#f0f4f8").grid(row=2, column=0, sticky='nw', pady=(row_pady, 0))
        logo_frame = tk.Frame(frame, bg="#f0f4f8")
        logo_frame.grid(row=2, column=1, sticky='ew', pady=(row_pady, 0))
        self.logo_entry = tk.Entry(logo_frame, font=field_font, width=38)
        self.logo_entry.pack(side='left', fill='x', expand=True, ipady=self.touch["entry_ipady"])
        self.logo_entry.insert(0, cfg.get('header_logo_path', ''))
        self.logo_entry.bind('<KeyRelease>', self.update_logo_preview)
        browse_btn = tk.Button(
            logo_frame,
            text="Browse",
            command=self.browse_logo,
            font=label_font,
            relief="flat",
            bg="#3498db",
            fg="white",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
        )
        browse_btn.pack(side='left', padx=6)
        preview_btn = tk.Button(
            logo_frame,
            text="Preview",
            command=self.preview_logo,
            font=label_font,
            relief="flat",
            bg="#8e44ad",
            fg="white",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
        )
        preview_btn.pack(side='left', padx=6)
        
        # Logo preview placeholder
        tk.Label(frame, text="Logo Preview:", font=label_font, bg="#f0f4f8").grid(row=3, column=0, sticky='nw', pady=(row_pady, 0))
        self.logo_preview_frame = tk.Frame(frame, bg="#ffffff", relief='sunken', borderwidth=2, width=400, height=120)
        self.logo_preview_frame.grid(row=3, column=1, sticky='ew', pady=(row_pady, 0))
        self.logo_preview_frame.grid_propagate(False)
        self.logo_preview_label = tk.Label(self.logo_preview_frame, text="[No logo selected]", bg="#ffffff", fg="#7f8c8d")
        self.logo_preview_label.pack(expand=True)
        self.logo_preview_image = None

        # Display diagonal
        tk.Label(frame, text="Display diagonal (in)", font=label_font, bg="#f0f4f8").grid(row=4, column=0, sticky='w', pady=(row_pady, 0))
        self.diagonal_entry = tk.Entry(frame, font=field_font, width=20)
        self.diagonal_entry.grid(row=4, column=1, sticky='w', pady=(row_pady, 0), ipady=self.touch["entry_ipady"])
        self.diagonal_entry.insert(0, str(cfg.get('display_diagonal_inches', 13.3)))

        # Categories Management
        tk.Label(frame, text="Categories (one per line)", font=label_font, bg="#f0f4f8").grid(row=5, column=0, sticky='nw', pady=(row_pady, 0))
        self.categories_text = tk.Text(frame, height=4, font=field_font, width=50)
        self.categories_text.config(padx=8, pady=6)
        self.categories_text.grid(row=5, column=1, sticky='ew', pady=(row_pady, 0))
        categories = cfg.get('categories', [])
        if isinstance(categories, list):
            self.categories_text.insert('1.0', '\n'.join(categories))
        else:
            self.categories_text.insert('1.0', str(categories))

        # Group members (multiline)
        tk.Label(frame, text="Group Members (one per line)", font=label_font, bg="#f0f4f8").grid(row=6, column=0, sticky='nw', pady=(row_pady, 0))
        self.members_text = tk.Text(frame, height=6, font=field_font, width=50)
        self.members_text.config(padx=8, pady=6)
        self.members_text.grid(row=6, column=1, sticky='ew', pady=(row_pady, 0))
        members = cfg.get('group_members', [])
        if isinstance(members, list):
            self.members_text.insert('1.0', '\n'.join(members))
        else:
            self.members_text.insert('1.0', str(members))

        frame.grid_columnconfigure(1, weight=1)

        btn_frame = tk.Frame(frame, bg="#f0f4f8")
        btn_frame.grid(row=7, column=0, columnspan=2, sticky='e', pady=(max(12, row_pady + 4), 0))
        save_btn = tk.Button(
            btn_frame,
            text="Save",
            bg="#27ae60",
            fg='white',
            font=label_font,
            relief="flat",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=self.save_config,
        )
        save_btn.pack(side='right')
        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            bg="#7f8c8d",
            fg='white',
            font=label_font,
            relief="flat",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=self.destroy,
        )
        cancel_btn.pack(side='right', padx=10)

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
            photo = pil_to_photoimage(img)
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
            photo = pil_to_photoimage(img)
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


class CoinStockEditWindow(tk.Toplevel):
    """Modal window to edit hopper coin stock and low-stock thresholds."""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.touch = _get_touch_metrics(controller)
        self.title("Edit Coin Stock")
        self._count_session = None
        self._count_job = None
        self._count_thread = None
        self._count_status = tk.StringVar(value="Auto-count idle")
        self.configure(bg="#f0f4f8")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self._center_window()
        self._build()
        self.bind("<Escape>", lambda e: self.destroy())

    def _center_window(self):
        width = max(320, int(self.controller.winfo_screenwidth()))
        height = max(240, int(self.controller.winfo_screenheight()))
        try:
            self.attributes("-fullscreen", True)
        except Exception:
            self.geometry(f"{width}x{height}+0+0")

    def _adjust_numeric_entry(self, entry, delta):
        try:
            value = int(entry.get().strip() or 0)
        except Exception:
            value = 0
        value = max(0, value + int(delta))
        entry.delete(0, tk.END)
        entry.insert(0, str(value))

    def _build_stepper_entry(self, parent, row, column, font, initial_value):
        value_frame = tk.Frame(parent, bg="#f0f4f8")
        value_frame.grid(
            row=row,
            column=column,
            sticky="w",
            pady=(self.touch["row_pady"], 0),
            padx=(8, 0),
        )

        button_font = ("Helvetica", max(11, self.touch["button_font_size"]), "bold")
        minus_btn = tk.Button(
            value_frame,
            text="-",
            bg="#7f8c8d",
            fg="white",
            relief="flat",
            font=button_font,
            width=3,
            padx=max(6, self.touch["button_padx"] - 10),
            pady=max(4, self.touch["button_pady"] - 2),
        )
        minus_btn.pack(side="left")

        entry = tk.Entry(value_frame, width=10, font=font, justify="center")
        entry.pack(side="left", padx=8, ipady=self.touch["entry_ipady"])
        entry.insert(0, str(initial_value))

        plus_btn = tk.Button(
            value_frame,
            text="+",
            bg="#27ae60",
            fg="white",
            relief="flat",
            font=button_font,
            width=3,
            padx=max(6, self.touch["button_padx"] - 10),
            pady=max(4, self.touch["button_pady"] - 2),
        )
        plus_btn.pack(side="left")

        minus_btn.config(command=lambda: self._adjust_numeric_entry(entry, -1))
        plus_btn.config(command=lambda: self._adjust_numeric_entry(entry, 1))
        return entry

    def _build(self):
        stock = {}
        try:
            stock = self.controller.get_coin_change_stock()
        except Exception:
            stock = {
                "one_peso": {"count": 0, "low_threshold": 20},
                "five_peso": {"count": 0, "low_threshold": 20},
            }

        frame = tk.Frame(
            self,
            bg="#f0f4f8",
            padx=self.touch["section_padx"],
            pady=self.touch["section_pady"],
        )
        frame.pack(fill="both", expand=True)

        title_font = ("Helvetica", max(14, self.touch["button_font_size"] + 2), "bold")
        label_font = ("Helvetica", max(11, self.touch["field_font_size"] - 1))
        label_bold_font = ("Helvetica", max(11, self.touch["field_font_size"] - 1), "bold")

        tk.Label(
            frame,
            text="Coin Hopper Setup",
            bg="#f0f4f8",
            fg="#2c3e50",
            font=title_font,
            anchor="w",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))

        tk.Label(frame, text="Denomination", bg="#f0f4f8", font=label_bold_font).grid(row=1, column=0, sticky="w")
        tk.Label(frame, text="Current Count", bg="#f0f4f8", font=label_bold_font).grid(row=1, column=1, sticky="w")
        tk.Label(frame, text="Low Threshold", bg="#f0f4f8", font=label_bold_font).grid(row=1, column=2, sticky="w")
        tk.Label(frame, text="Auto Count", bg="#f0f4f8", font=label_bold_font).grid(row=1, column=3, sticky="w")

        tk.Label(frame, text="₱1 coins", bg="#f0f4f8", font=label_font).grid(
            row=2,
            column=0,
            sticky="w",
            pady=(self.touch["row_pady"], 0),
        )
        self.one_count_entry = self._build_stepper_entry(
            frame, 2, 1, label_font, stock.get("one_peso", {}).get("count", 0)
        )
        self.one_threshold_entry = self._build_stepper_entry(
            frame, 2, 2, label_font, stock.get("one_peso", {}).get("low_threshold", 20)
        )
        tk.Button(
            frame,
            text="Count P1",
            bg="#2980b9",
            fg="white",
            relief="flat",
            font=label_bold_font,
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=lambda: self._toggle_hopper_count(1),
        ).grid(row=2, column=3, sticky="w", padx=(8, 0), pady=(self.touch["row_pady"], 0))

        tk.Label(frame, text="₱5 coins", bg="#f0f4f8", font=label_font).grid(
            row=3,
            column=0,
            sticky="w",
            pady=(self.touch["row_pady"], 0),
        )
        self.five_count_entry = self._build_stepper_entry(
            frame, 3, 1, label_font, stock.get("five_peso", {}).get("count", 0)
        )
        self.five_threshold_entry = self._build_stepper_entry(
            frame, 3, 2, label_font, stock.get("five_peso", {}).get("low_threshold", 20)
        )
        tk.Button(
            frame,
            text="Count P5",
            bg="#8e44ad",
            fg="white",
            relief="flat",
            font=label_bold_font,
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=lambda: self._toggle_hopper_count(5),
        ).grid(row=3, column=3, sticky="w", padx=(8, 0), pady=(self.touch["row_pady"], 0))

        status = tk.Label(
            frame,
            textvariable=self._count_status,
            bg="#f0f4f8",
            fg="#34495e",
            font=("Helvetica", max(10, self.touch["field_font_size"] - 2)),
            anchor="w",
            justify="left",
            wraplength=780,
        )
        status.grid(row=4, column=0, columnspan=4, sticky="we", pady=(10, 4))

        btns = tk.Frame(frame, bg="#f0f4f8")
        btns.grid(row=5, column=0, columnspan=4, sticky="e", pady=(14, 0))

        tk.Button(
            btns,
            text="Save",
            bg="#27ae60",
            fg="white",
            relief="flat",
            font=label_bold_font,
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=self._save,
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            btns,
            text="Back",
            bg="#7f8c8d",
            fg="white",
            relief="flat",
            font=label_bold_font,
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=self.destroy,
        ).pack(side="right")

    def _save(self):
        self._stop_hopper_count(apply=False)
        try:
            one_count = max(0, int(self.one_count_entry.get().strip() or 0))
            five_count = max(0, int(self.five_count_entry.get().strip() or 0))
            one_threshold = max(0, int(self.one_threshold_entry.get().strip() or 0))
            five_threshold = max(0, int(self.five_threshold_entry.get().strip() or 0))
        except Exception:
            messagebox.showerror("Invalid Input", "Counts and thresholds must be whole numbers >= 0.", parent=self)
            return

        try:
            self.controller.update_coin_change_stock(
                one_count=one_count,
                five_count=five_count,
                one_threshold=one_threshold,
                five_threshold=five_threshold,
            )
            self.destroy()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save coin stock: {e}", parent=self)

    # --- Auto-count helpers ---
    def _ensure_reader(self):
        # Prefer existing shared reader; do not modify global config/state beyond that.
        reader = getattr(self.controller, "_arduino_reader", None)
        if reader and getattr(reader, "connected", False):
            return reader
        if get_shared_serial_reader:
            try:
                hw = getattr(self.controller, "config", {}).get("hardware", {}) if isinstance(getattr(self.controller, "config", {}), dict) else {}
                port = (
                    hw.get("coin_acceptor", {}).get("serial_port")
                    or hw.get("bill_acceptor", {}).get("serial_port")
                    or detect_arduino_serial_port()
                )
                # Use a transient reader; do not attach to controller to avoid side-effects.
                reader = get_shared_serial_reader(port, 115200)
                return reader
            except Exception:
                return None
        return None

    def _ensure_hopper(self):
        # Create a temporary hopper instance so we don't affect other components.
        try:
            hw = getattr(self.controller, "config", {}).get("hardware", {}) if isinstance(getattr(self.controller, "config", {}), dict) else {}
            cfg_port = (
                hw.get("coin_hopper", {}).get("serial_port")
                or hw.get("bill_acceptor", {}).get("serial_port")
                or hw.get("coin_acceptor", {}).get("serial_port")
            )
            port = cfg_port
            if port and platform.system() != "Linux" and str(port).startswith("/dev/"):
                port = None
            if not port:
                port = detect_arduino_serial_port()
            hopper = CoinHopper(serial_port=port, baudrate=115200)
            if hopper.connect():
                return hopper
            auto_port = detect_arduino_serial_port()
            if auto_port and auto_port != port:
                hopper = CoinHopper(serial_port=auto_port, baudrate=115200)
                if hopper.connect():
                    return hopper
        except Exception:
            return None
        return None

    def _toggle_hopper_count(self, denom):
        session = self._count_session or {}
        if session.get("active") and session.get("denom") == denom:
            self._stop_hopper_count(apply=True)
            return

        reader = self._ensure_reader()
        hopper = self._ensure_hopper()
        if not reader or not getattr(reader, "connected", False):
            messagebox.showerror("Coin Counter", "Coin sensor is not connected.", parent=self)
            return
        if not hopper:
            messagebox.showerror("Coin Hopper", "Coin hopper is not connected.", parent=self)
            return
        try:
            if getattr(reader, "suspended", False):
                reader.resume()
        except Exception:
            pass
        try:
            hopper.ensure_relays_off()
            hopper.send_command("RELAY_ON")
        except Exception:
            pass
        opened = hopper.open_hopper(denom)
        if not opened:
            ports = self._serial_ports_text()
            extra = f"\nPorts seen: {ports}" if ports else ""
            messagebox.showerror("Coin Hopper", f"Failed to start P{denom} hopper.{extra}", parent=self)
            try:
                hopper.disconnect()
            except Exception:
                pass
            return
        try:
            start_total = float(reader.get_coin_total() or 0.0)
        except Exception:
            start_total = 0.0
        self._count_session = {
            "active": True,
            "denom": denom,
            "reader": reader,
            "hopper": hopper,
            "start_total": start_total,
            "last_total": start_total,
            "count": 0,
            "last_coin_ts": time.time(),
        }
        self._count_status.set(f"Counting P{denom}... hopper open, waiting for coins.")
        self._start_poll()

    def _start_poll(self):
        self._stop_poll()

        def _poll():
            session = self._count_session
            if not session or not session.get("active"):
                return
            reader = session.get("reader")
            denom = session.get("denom")
            try:
                total = float(reader.get_coin_total() or 0.0)
            except Exception:
                total = None
            if total is not None:
                last_total = session.get("last_total", total)
                delta = total - last_total
                session["last_total"] = total
                if delta > 0 and denom:
                    coins = int(round(delta / float(denom)))
                    if coins > 0:
                        session["count"] = max(0, session.get("count", 0) + coins)
                        session["last_coin_ts"] = time.time()
                        entry = self.one_count_entry if denom == 1 else self.five_count_entry
                        entry.delete(0, tk.END)
                        entry.insert(0, str(session["count"]))
                        self._count_status.set(f"Counting P{denom}: {session['count']} coin(s)")
            idle_for = time.time() - session.get("last_coin_ts", 0)
            if idle_for >= 2.0:
                self._count_status.set(f"No coins for 2s. Stopping P{denom} hopper and applying count.")
                self._stop_hopper_count(apply=True)
                return
            self._count_job = self.after(400, _poll)

        self._count_job = self.after(400, _poll)

    def _start_dispense_thread(self, denom, hopper, reader):
        if self._count_thread and self._count_thread.is_alive():
            return

        def runner():
            try:
                ok, dispensed, msg = hopper.dispense_coins(
                    denomination=denom,
                    count=500,
                    timeout_ms=60000,
                    callback=self._set_status_from_thread,
                )
            except Exception as e:
                ok, dispensed, msg = False, 0, f"Error: {e}"
            self.after(0, lambda: self._finish_dispense_result(ok, dispensed, msg, denom))

        self._count_thread = threading.Thread(target=runner, daemon=True)
        self._count_thread.start()

    def _set_status_from_thread(self, text):
        try:
            self.after(0, lambda: self._count_status.set(str(text)))
        except Exception:
            pass

    def _finish_dispense_result(self, ok, dispensed, msg, denom):
        session = self._count_session or {}
        session["count"] = max(0, int(dispensed or 0))
        session["active"] = False
        self._count_session = session
        if not ok and msg:
            try:
                messagebox.showerror("Coin Hopper", msg, parent=self)
            except Exception:
                pass
        self._stop_hopper_count(apply=True)

    def _stop_poll(self):
        if self._count_job:
            try:
                self.after_cancel(self._count_job)
            except Exception:
                pass
            self._count_job = None

    def _stop_hopper_count(self, apply=True):
        session = self._count_session
        if not session:
            return
        self._stop_poll()
        hopper = session.get("hopper")
        denom = session.get("denom")
        self._count_thread = None
        if hopper:
            try:
                hopper.close_hopper(denom)
                hopper.ensure_relays_off()
            except Exception:
                pass
        if apply and denom in (1, 5):
            count = max(0, int(session.get("count", 0)))
            entry = self.one_count_entry if denom == 1 else self.five_count_entry
            entry.delete(0, tk.END)
            entry.insert(0, str(count))
            self._count_status.set(f"Applied P{denom} count: {count}")
        else:
            self._count_status.set("Auto-count idle")
        hopper = session.get("hopper")
        if hopper:
            try:
                hopper.disconnect()
            except Exception:
                pass
        self._count_session = None
    def _serial_ports_text(self):
        try:
            if not list_ports:
                return ""
            return ", ".join([p.device for p in list_ports.comports()])
        except Exception:
            return ""

class AdminScreen(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg="#f0f4f8")  # Light background
        self.controller = controller
        self.scan_start_x = 0  # For drag-to-scroll
        self.display_profile = get_display_profile(controller)
        self.touch = _get_touch_metrics(controller)
        screen_height = self.display_profile["layout_height"]
        self.header_px = max(96, int(screen_height * 0.14))
        self.touch_dead_zone_top_px = self.display_profile["touch_dead_zone_top_px"]
        self.touch_dead_zone_bottom_start_px = self.display_profile["touch_dead_zone_bottom_start_px"]
        self.touch_dead_zone_bottom_px = self.display_profile["touch_dead_zone_bottom_px"]
        cfg = getattr(self.controller, "config", {}) if isinstance(getattr(self.controller, "config", {}), dict) else {}
        self.machine_name = cfg.get("machine_name", "RAON")
        self.machine_subtitle = cfg.get("machine_subtitle", "Rapid Access Outlet for Electronic Necessities")
        self.header_logo_path = cfg.get("header_logo_path", "")
        self.logo_image = None
        self.logo_cache = {}

        self.fonts = {
            "header": tkfont.Font(family="Helvetica", size=max(22, self.touch["button_font_size"] + 10), weight="bold"),
            "item_name": tkfont.Font(family="Helvetica", size=max(14, self.touch["field_font_size"] + 1), weight="bold"),
            "item_details": tkfont.Font(family="Helvetica", size=max(12, self.touch["field_font_size"])),
            "item_description": tkfont.Font(family="Helvetica", size=max(11, self.touch["field_font_size"] - 1)),
            "button": tkfont.Font(family="Helvetica", size=max(12, self.touch["button_font_size"]), weight="bold"),
            "machine_title": tkfont.Font(family="Helvetica", size=max(18, int(self.header_px * 0.30)), weight="bold"),
            "machine_subtitle": tkfont.Font(family="Helvetica", size=max(10, int(self.header_px * 0.16))),
            "logo_placeholder": tkfont.Font(family="Helvetica", size=max(14, int(self.header_px * 0.28)), weight="bold"),
        }
        self._machine_title_base_size = int(self.fonts["machine_title"].cget("size"))
        self._machine_subtitle_base_size = int(self.fonts["machine_subtitle"].cget("size"))
        self.colors = {
            "background": "#f0f4f8",
            "header_fg": "#2c3e50",
            "card_bg": "#ffffff",
            "border": "#dfe6e9",
            "edit_btn_bg": "#3498db",
            "remove_btn_bg": "#e74c3c",
            "btn_fg": "#ffffff",
            "brand_bg": "#2222a8",
        }

        # Kiosk-like branding header (logo + machine text).
        self.brand_header = tk.Frame(self, bg=self.colors["brand_bg"], height=self.header_px)
        self.brand_header.pack(side="top", fill="x")
        self.brand_header.pack_propagate(False)

        brand_left = tk.Frame(self.brand_header, bg=self.colors["brand_bg"])
        brand_left.pack(side="left", padx=12, pady=8)

        logo_frame = tk.Frame(
            brand_left,
            bg=self.colors["brand_bg"],
            width=160,
            height=int(self.header_px * 0.82),
        )
        logo_frame.pack(side="left", padx=(0, 12))
        logo_frame.pack_propagate(False)

        self.logo_image_label = tk.Label(logo_frame, bg=self.colors["brand_bg"], fg="white")
        self.logo_image_label.pack(expand=True)

        logo_text_frame = tk.Frame(brand_left, bg=self.colors["brand_bg"])
        logo_text_frame.pack(anchor="w")
        self.logo_text_frame = logo_text_frame

        self.brand_title_label = tk.Label(
            logo_text_frame,
            text=self.machine_name,
            bg=self.colors["brand_bg"],
            fg="white",
            font=self.fonts["machine_title"],
            anchor="w",
            justify="left",
        )
        self.brand_title_label.pack(anchor="w")

        self.brand_subtitle_label = tk.Label(
            logo_text_frame,
            text=self.machine_subtitle,
            bg=self.colors["brand_bg"],
            fg="white",
            font=self.fonts["machine_subtitle"],
            anchor="w",
            justify="left",
        )
        self.brand_subtitle_label.pack(anchor="w")
        self.brand_header.bind("<Configure>", self._on_brand_resize)
        self.load_header_logo()
        self._fit_brand_text()

        # Bottom system status area (replace black strip with live status panel).
        status_height = max(260, self.touch_dead_zone_bottom_px if self.touch_dead_zone_bottom_px > 0 else self.display_profile["status_panel_height_px"])
        self.status_zone = tk.Frame(self, bg="#111111", height=status_height)
        self.status_zone.pack(side="bottom", fill="x")
        self.status_zone.pack_propagate(False)
        self.status_panel = SystemStatusPanel(self.status_zone, controller=self.controller, panel_height=status_height)
        self.status_panel.pack(fill="both", expand=True)

        # Touch-active area for all admin controls/content.
        self.touch_container = tk.Frame(self, bg=self.colors["background"])
        self.touch_container.pack(fill="both", expand=True)

        self.create_widgets()
        self.bind("<<ShowFrame>>", self._on_show_frame)

        exit_label = tk.Label(
            self.touch_container,
            text="Press 'Esc' to return to Selection Screen",
            font=("Helvetica", max(12, self.touch["field_font_size"])),
            fg="#7f8c8d",  # Gray text
            bg="#f0f4f8",
        )
        exit_label.pack(side="bottom", pady=max(20, self.touch["row_pady"] + 8))

    def _on_show_frame(self, event=None):
        self._refresh_brand_header()
        self.populate_items()

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
        self._fit_brand_text()

    def _on_brand_resize(self, event=None):
        self._fit_brand_text()

    def _fit_brand_text(self):
        """Ensure header title/subtitle stay visible on one screen width."""
        try:
            header_w = self.brand_header.winfo_width()
            if header_w <= 1:
                header_w = int(self.controller.winfo_screenwidth())
            available = max(220, header_w - 260)  # reserve logo + paddings

            title_font = self.fonts["machine_title"]
            title_size = self._machine_title_base_size
            title_font.configure(size=title_size)
            while title_size > 14 and title_font.measure(self.machine_name or "") > available:
                title_size -= 1
                title_font.configure(size=title_size)

            subtitle_font = self.fonts["machine_subtitle"]
            subtitle_size = self._machine_subtitle_base_size
            subtitle_font.configure(size=subtitle_size)
            while subtitle_size > 9 and subtitle_font.measure(self.machine_subtitle or "") > available:
                subtitle_size -= 1
                subtitle_font.configure(size=subtitle_size)

            self.brand_title_label.config(wraplength=available)
            self.brand_subtitle_label.config(wraplength=available)
        except Exception:
            pass

    def load_header_logo(self):
        """Load header logo from config path; fallback to common logo files/initials."""
        self.logo_image = None
        logo_path = str(self.header_logo_path or "").strip()
        resolved_logo = None

        if logo_path:
            resolved_logo = get_absolute_path(logo_path)
            if not os.path.exists(resolved_logo):
                resolved_logo = logo_path if os.path.exists(logo_path) else None

        if not resolved_logo:
            common_names = ["LOGO.png", "logo.png", "Logo.png", "LOGO.jpg", "logo.jpg"]
            for fname in common_names:
                test_path = get_absolute_path(fname)
                if os.path.exists(test_path):
                    resolved_logo = test_path
                    break

        if resolved_logo and resolved_logo in self.logo_cache:
            self.logo_image = self.logo_cache[resolved_logo]
            self.logo_image_label.config(image=self.logo_image, text="")
            self.logo_image_label.image = self.logo_image
            return

        if resolved_logo:
            try:
                img = Image.open(resolved_logo)
                max_h = int(self.header_px * 0.80)
                max_w = 180
                resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                img.thumbnail((max_w, max_h), resample)
                self.logo_image = pil_to_photoimage(img)
                self.logo_cache[resolved_logo] = self.logo_image
                self.logo_image_label.config(image=self.logo_image, text="")
                self.logo_image_label.image = self.logo_image
                return
            except Exception as e:
                print(f"[AdminScreen] Failed to load header logo: {e}")

        fallback = (self.machine_name[:1] if self.machine_name else "R").upper()
        self.logo_image_label.config(
            image="",
            text=fallback,
            font=self.fonts["logo_placeholder"],
            fg="white",
            bg=self.colors["brand_bg"],
        )

    def _build_touch_button(self, parent, text, bg, command):
        return tk.Button(
            parent,
            text=text,
            font=self.fonts["button"],
            bg=bg,
            fg=self.colors["btn_fg"],
            relief="flat",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=command,
        )

    def create_widgets(self):
        root = self.touch_container

        # --- Header ---
        header = tk.Frame(root, bg=self.colors["background"])
        header_top_pady = max(8, self.touch["section_pady"] - 8)
        header_bottom_pady = max(12, self.touch["section_pady"] - 2)
        header.pack(
            fill="x",
            padx=max(20, self.touch["section_padx"]),
            pady=(header_top_pady, header_bottom_pady),
        )
        title_row = tk.Frame(header, bg=self.colors["background"])
        title_row.pack(fill="x")

        tk.Label(
            title_row,
            text="Manage Items",
            font=self.fonts["header"],
            bg=self.colors["background"],
            fg=self.colors["header_fg"],
        ).pack(side="left")

        actions_row = tk.Frame(header, bg=self.colors["background"])
        actions_row.pack(fill="x", pady=(max(6, self.touch["row_pady"] - 2), 0))

        # "Add New Item" button removed — admin now uses Assign Slots

        back_btn = self._build_touch_button(
            actions_row,
            text="Back",
            bg="#7f8c8d",
            command=lambda: self.controller.show_frame("SelectionScreen"),
        )
        back_btn.pack(side="right", padx=(0, 8))

        # Button to open Assign Items screen (6x10 grid)
        assign_slots_btn = self._build_touch_button(
            actions_row,
            text="Assign Slots",
            bg="#8e44ad",
            command=lambda: getattr(self.controller, 'show_assign_items', lambda: None)(),
        )
        assign_slots_btn.pack(side="right", padx=(0, 8))

        # Button to view logs
        logs_btn = self._build_touch_button(
            actions_row,
            text="View Logs",
            bg="#27ae60",
            command=lambda: self.controller.show_frame("LogsScreen"),
        )
        logs_btn.pack(side="right", padx=(0, 8))

        # Button to edit hopper coin counts and thresholds
        coin_edit_btn = self._build_touch_button(
            actions_row,
            text="Edit Coins",
            bg="#f39c12",
            command=self.open_coin_stock_editor,
        )
        coin_edit_btn.pack(side="right", padx=(0, 8))

        # --- Coin Change Dashboard ---
        coin_dash = tk.Frame(
            root,
            bg="#ffffff",
            highlightbackground=self.colors["border"],
            highlightthickness=1,
            padx=max(14, self.touch["section_padx"] - 4),
            pady=max(10, self.touch["section_pady"] - 4),
        )
        coin_dash.pack(fill="x", padx=max(20, self.touch["section_padx"]), pady=(0, 10))

        tk.Label(
            coin_dash,
            text="Change Coin Stock",
            bg="#ffffff",
            fg="#2c3e50",
            font=("Helvetica", max(12, self.touch["field_font_size"] + 1), "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self.coin_total_value_label = tk.Label(
            coin_dash,
            text="Total change value: ₱0",
            bg="#ffffff",
            fg="#2c3e50",
            font=("Helvetica", max(11, self.touch["field_font_size"]), "bold"),
            anchor="w",
        )
        self.coin_total_value_label.grid(row=0, column=1, sticky="e")

        self.coin_one_info_label = tk.Label(
            coin_dash,
            text="₱1 Coins: 0 pcs | Threshold: 0 | Value: ₱0",
            bg="#ffffff",
            fg="#2c3e50",
            font=("Helvetica", max(11, self.touch["field_font_size"])),
            anchor="w",
        )
        self.coin_one_info_label.grid(row=1, column=0, sticky="w", pady=(8, 2))
        self.coin_one_status_label = tk.Label(
            coin_dash,
            text="Status: OK",
            bg="#ffffff",
            fg="#27ae60",
            font=("Helvetica", max(11, self.touch["field_font_size"]), "bold"),
            anchor="e",
        )
        self.coin_one_status_label.grid(row=1, column=1, sticky="e", pady=(8, 2))

        self.coin_five_info_label = tk.Label(
            coin_dash,
            text="₱5 Coins: 0 pcs | Threshold: 0 | Value: ₱0",
            bg="#ffffff",
            fg="#2c3e50",
            font=("Helvetica", max(11, self.touch["field_font_size"])),
            anchor="w",
        )
        self.coin_five_info_label.grid(row=2, column=0, sticky="w", pady=2)
        self.coin_five_status_label = tk.Label(
            coin_dash,
            text="Status: OK",
            bg="#ffffff",
            fg="#27ae60",
            font=("Helvetica", max(11, self.touch["field_font_size"]), "bold"),
            anchor="e",
        )
        self.coin_five_status_label.grid(row=2, column=1, sticky="e", pady=2)

        coin_dash.grid_columnconfigure(0, weight=1)
        coin_dash.grid_columnconfigure(1, weight=0)

        # --- Scrollable Item List ---
        canvas_container = tk.Frame(root, bg=self.colors["background"])
        canvas_container.pack(
            fill="both",
            expand=True,
            padx=max(20, self.touch["section_padx"]),
            pady=(0, 20),
        )

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
        self._bind_wheel_recursive(self.canvas)
        self._bind_wheel_recursive(self.scrollable_frame)
        self.refresh_coin_dashboard()

    def on_canvas_configure(self, event):
        """On canvas resize, update the width of the inner frame."""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)

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
        try:
            hovered = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
            return self._is_descendant_widget(hovered, self.canvas)
        except Exception:
            return False

    def _event_from_item_area(self, event):
        try:
            widget = getattr(event, "widget", None)
            if self._is_descendant_widget(widget, self.canvas):
                return True
            if self._is_descendant_widget(widget, self.scrollable_frame):
                return True
            return self._pointer_over_canvas()
        except Exception:
            return False

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
        try:
            canvas_y = self.winfo_pointery() - self.canvas.winfo_rooty()
        except Exception:
            canvas_y = event.y
        self.canvas.scan_dragto(self.scan_start_x, canvas_y, gain=1)

    def _on_mousewheel(self, event):
        """Cross-platform wheel handler for the admin item list only."""
        try:
            if not self._event_from_item_area(event):
                return

            step = 0
            if getattr(event, "num", None) == 4:
                step = -3
            elif getattr(event, "num", None) == 5:
                step = 3
            else:
                delta = int(getattr(event, "delta", 0) or 0)
                if delta != 0:
                    if abs(delta) >= 120:
                        step = -int(delta / 120)
                    else:
                        step = -1 if delta > 0 else 1

            if step != 0:
                self.canvas.yview_scroll(step, "units")
                return "break"
        except Exception:
            pass

    def _bind_wheel_recursive(self, widget):
        """Bind wheel events to a widget and all descendants for consistent scrolling."""
        if widget is None:
            return
        try:
            widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
            widget.bind("<Button-4>", self._on_mousewheel, add="+")
            widget.bind("<Button-5>", self._on_mousewheel, add="+")
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._bind_wheel_recursive(child)
        except Exception:
            pass

    def populate_items(self):
        self.refresh_coin_dashboard()
        # Clear existing items
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Repopulate with current items
        for item in self.controller.items:
            card = self.create_item_card(self.scrollable_frame, item)
            card.pack(fill="x", padx=10, pady=max(6, self.touch["row_pady"] - 2))
            self._bind_wheel_recursive(card)

    def create_item_card(self, parent, item_data):
        card = tk.Frame(
            parent,
            bg=self.colors["card_bg"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
        )
        card.grid_columnconfigure(0, weight=1)

        info_frame = tk.Frame(card, bg=card["bg"])
        info_frame.grid(row=0, column=0, padx=15, pady=(self.touch["row_pady"], 10), sticky="ew")

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
        button_frame.grid(row=0, column=1, padx=15, pady=(self.touch["row_pady"], 10), sticky="se")

        edit_button = tk.Button(
            button_frame,
            text="Edit",
            font=self.fonts["button"],
            bg=self.colors["edit_btn_bg"],
            fg=self.colors["btn_fg"],
            relief="flat",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
            command=lambda i=item_data: self.edit_item(i),
        )
        edit_button.pack(side="left", padx=(0, 8))

        remove_button = tk.Button(
            button_frame,
            text="Remove",
            font=self.fonts["button"],
            bg=self.colors["remove_btn_bg"],
            fg=self.colors["btn_fg"],
            relief="flat",
            padx=self.touch["button_padx"],
            pady=self.touch["button_pady"],
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

    def open_coin_stock_editor(self):
        CoinStockEditWindow(self, self.controller)

    def _format_coin_status(self, count, threshold):
        if count <= 0:
            return ("OUT OF STOCK", "#e74c3c")
        if count <= threshold:
            return ("LOW STOCK", "#f39c12")
        return ("OK", "#27ae60")

    def refresh_coin_dashboard(self):
        try:
            stock = self.controller.get_coin_change_stock()
        except Exception:
            stock = {
                "one_peso": {"count": 0, "low_threshold": 0},
                "five_peso": {"count": 0, "low_threshold": 0},
            }

        one_count = int(stock.get("one_peso", {}).get("count", 0))
        one_threshold = int(stock.get("one_peso", {}).get("low_threshold", 0))
        five_count = int(stock.get("five_peso", {}).get("count", 0))
        five_threshold = int(stock.get("five_peso", {}).get("low_threshold", 0))

        one_value = one_count * 1
        five_value = five_count * 5
        total_value = one_value + five_value

        one_status, one_color = self._format_coin_status(one_count, one_threshold)
        five_status, five_color = self._format_coin_status(five_count, five_threshold)

        self.coin_total_value_label.config(text=f"Total change value: ₱{total_value}")
        self.coin_one_info_label.config(
            text=f"₱1 Coins: {one_count} pcs | Threshold: {one_threshold} | Value: ₱{one_value}"
        )
        self.coin_one_status_label.config(text=f"Status: {one_status}", fg=one_color)
        self.coin_five_info_label.config(
            text=f"₱5 Coins: {five_count} pcs | Threshold: {five_threshold} | Value: ₱{five_value}"
        )
        self.coin_five_status_label.config(text=f"Status: {five_status}", fg=five_color)

    def edit_item(self, item_data):
        ItemEditWindow(self, self.controller, item_data)

    def remove_item(self, item_to_remove):
        if messagebox.askyesno(
            "Confirm Deletion",
            f"Are you sure you want to remove '{item_to_remove['name']}'?",
        ):
            self.controller.remove_item(item_to_remove)
