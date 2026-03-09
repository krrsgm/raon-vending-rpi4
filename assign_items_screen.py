import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False
import json
import os
import io
import time
from esp32_client import pulse_slot, send_command
from fix_paths import get_absolute_path
import copy
from system_status_panel import SystemStatusPanel

def pil_to_photoimage(pil_image):
    """Convert PIL Image to Tkinter PhotoImage using PPM format (no ImageTk needed)"""
    with io.BytesIO() as output:
        pil_image.save(output, format="PPM")
        data = output.getvalue()
    return tk.PhotoImage(data=data)


def _get_touch_metrics(anchor):
    """Compute touch-friendly sizing from screen size and configured diagonal."""
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
    small_font = max(9, base_font - 1)

    return {
        "touch_px": touch_px,
        "base_font": base_font,
        "button_font": button_font,
        "small_font": small_font,
        "title_font": max(14, button_font + 5),
        "row_pady": max(6, int(touch_px * 0.16)),
        "section_pad": max(10, int(touch_px * 0.24)),
        "button_padx": max(10, int(touch_px * 0.35)),
        "button_pady": max(6, int(touch_px * 0.16)),
        "entry_padding": max(4, int(touch_px * 0.10)),
        "slot_spacing": max(4, int(touch_px * 0.10)),
        "card_padding": max(4, int(touch_px * 0.12)),
    }


def _ensure_assign_touch_styles(widget, touch):
    """Define ttk styles used by assign screen/dialogs for larger touch targets."""
    try:
        style = ttk.Style(widget)
        style.configure("AssignTouch.TLabel", font=("Helvetica", touch["base_font"]))
        style.configure("AssignTouch.Title.TLabel", font=("Helvetica", touch["title_font"], "bold"))
        style.configure("AssignTouch.Small.TLabel", font=("Helvetica", touch["small_font"]))
        style.configure(
            "AssignTouch.TButton",
            font=("Helvetica", touch["button_font"], "bold"),
            padding=(touch["button_padx"], touch["button_pady"]),
        )
        style.configure(
            "AssignTouch.Small.TButton",
            font=("Helvetica", max(9, touch["small_font"]), "bold"),
            padding=(max(6, touch["button_padx"] - 4), max(4, touch["button_pady"] - 2)),
        )
        style.configure(
            "AssignTouch.TEntry",
            font=("Helvetica", touch["base_font"]),
            padding=(8, touch["entry_padding"], 8, touch["entry_padding"]),
        )
        style.configure(
            "AssignTouch.TCombobox",
            font=("Helvetica", touch["base_font"]),
            padding=(8, touch["entry_padding"], 8, touch["entry_padding"]),
            arrowsize=max(14, touch["base_font"] + 4),
        )
        style.configure(
            "AssignTouch.Term.TCombobox",
            font=("Helvetica", max(touch["button_font"], touch["base_font"] + 2), "bold"),
            padding=(10, max(touch["entry_padding"], 6), 10, max(touch["entry_padding"], 6)),
            arrowsize=max(16, touch["button_font"] + 6),
        )
        style.configure(
            "AssignTouch.Term.TLabel",
            font=("Helvetica", max(touch["button_font"], touch["base_font"] + 1), "bold"),
        )
        style.configure("AssignTouch.TLabelframe.Label", font=("Helvetica", touch["base_font"], "bold"))
    except Exception:
        pass


def _fit_window_to_screen(anchor, desired_width, desired_height):
    try:
        max_w = max(320, int(anchor.winfo_screenwidth()) - 40)
        max_h = max(240, int(anchor.winfo_screenheight()) - 40)
    except Exception:
        max_w, max_h = desired_width, desired_height
    return max(320, min(int(desired_width), max_w)), max(240, min(int(desired_height), max_h))


class PriceStockDialog(tk.Toplevel):
    """Modal dialog to edit price, stock, image, and other item fields.

    If `read_only` is True the fields are disabled and the dialog acts as a viewer.
    """
    def __init__(self, parent, item_data=None, read_only=False, category_options=None):
        """
        Args:
            parent: parent window
            item_data: dict with item details
        """
        super().__init__(parent)
        self.item_data = item_data or {}
        self.result = None
        self.read_only = bool(read_only)
        self.touch = _get_touch_metrics(parent)
        _ensure_assign_touch_styles(self, self.touch)
        
        self.title("Edit Item Details")
        self.transient(parent)
        self.grab_set()
        self.category_options = category_options or []
        desired_w = int(self.winfo_screenwidth() * 0.70)
        desired_h = int(self.winfo_screenheight() * 0.78)
        width, height = _fit_window_to_screen(self, desired_w, desired_h)
        self.geometry(f"{width}x{height}")
        self._create_widgets()
    
    def _create_widgets(self):
        frame = ttk.Frame(self, padding=self.touch["section_pad"])
        frame.pack(fill="both", expand=True)
        
        # Title
        ttk.Label(frame, text="Edit Item Details", style="AssignTouch.Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, self.touch["row_pady"] + 4))
        
        # Item name (display only)
        item_name = self.item_data.get('name', 'Unknown')
        ttk.Label(frame, text=f"Item: {item_name}", style="AssignTouch.Small.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, self.touch["row_pady"]))

        # Price / stock / threshold with touch steppers
        ttk.Label(frame, text="Price (\u20b1):", style="AssignTouch.TLabel").grid(row=2, column=0, sticky="w", pady=self.touch["row_pady"])
        self.price_entry = self._build_stepper_entry(frame, 2, initial_value=self.item_data.get('price', 0.0), integer=False, step=1.0)

        ttk.Label(frame, text="Stock Quantity:", style="AssignTouch.TLabel").grid(row=3, column=0, sticky="w", pady=self.touch["row_pady"])
        self.qty_entry = self._build_stepper_entry(frame, 3, initial_value=self.item_data.get('quantity', 0), integer=True, step=1)

        ttk.Label(frame, text="Low Stock Threshold:", style="AssignTouch.TLabel").grid(row=4, column=0, sticky="w", pady=self.touch["row_pady"])
        self.threshold_entry = self._build_stepper_entry(frame, 4, initial_value=self.item_data.get('low_stock_threshold', 3), integer=True, step=1)
        
        # Category (select from available or type new)
        ttk.Label(frame, text="Category:", style="AssignTouch.TLabel").grid(row=5, column=0, sticky="w", pady=self.touch["row_pady"])
        try:
            self.category_var = tk.StringVar(value=self.item_data.get('category', ''))
            self.category_combo = ttk.Combobox(
                frame,
                textvariable=self.category_var,
                values=self.category_options,
                width=18,
                style="AssignTouch.TCombobox",
            )
            self.category_combo.grid(row=5, column=1, columnspan=2, sticky="ew", pady=self.touch["row_pady"])
            # allow typing new categories
            self.category_combo.configure(state='normal')
        except Exception:
            self.category_entry = ttk.Entry(frame, width=20, style="AssignTouch.TEntry")
            self.category_entry.grid(row=5, column=1, columnspan=2, sticky="ew", pady=self.touch["row_pady"])
            self.category_entry.insert(0, self.item_data.get('category', ''))
        
        # Description
        ttk.Label(frame, text="Description:", style="AssignTouch.TLabel").grid(row=6, column=0, sticky="nw", pady=self.touch["row_pady"])
        self.desc_text = tk.Text(frame, width=40, height=4, font=("Helvetica", self.touch["base_font"]))
        self.desc_text.grid(row=6, column=1, columnspan=2, sticky="ew", pady=self.touch["row_pady"])
        self.desc_text.insert('1.0', self.item_data.get('description', ''))
        
        # Image path
        ttk.Label(frame, text="Image:", style="AssignTouch.TLabel").grid(row=7, column=0, sticky="w", pady=self.touch["row_pady"])
        self.image_entry = ttk.Entry(frame, width=25, style="AssignTouch.TEntry")
        self.image_entry.grid(row=7, column=1, sticky="ew", pady=self.touch["row_pady"])
        self.image_entry.insert(0, self.item_data.get('image', ''))
        
        browse_btn = ttk.Button(frame, text="Browse", style="AssignTouch.TButton", command=self._browse_image)
        browse_btn.grid(row=7, column=2, padx=(8, 0), pady=self.touch["row_pady"])
        # Keep a reference so we can disable it when showing the dialog in restricted modes
        self.browse_btn = browse_btn
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=8, column=0, columnspan=3, sticky="e", pady=(self.touch["row_pady"] + 4, 0))
        
        if self.read_only:
            close_btn = ttk.Button(btn_frame, text="Close", style="AssignTouch.TButton", command=self._on_cancel)
            close_btn.pack(side="right")
        else:
            save_btn = ttk.Button(btn_frame, text="Save", style="AssignTouch.TButton", command=self._on_save)
            save_btn.pack(side="right", padx=6)
            
            cancel_btn = ttk.Button(btn_frame, text="Cancel", style="AssignTouch.TButton", command=self._on_cancel)
            cancel_btn.pack(side="right")
        
        frame.columnconfigure(1, weight=1)

    def _adjust_numeric_entry(self, entry, delta, integer=False):
        try:
            raw = entry.get().strip()
            value = int(raw) if integer else float(raw)
        except Exception:
            value = 0 if integer else 0.0

        value = max(0, value + delta)
        entry.delete(0, tk.END)
        if integer:
            entry.insert(0, str(int(value)))
        else:
            entry.insert(0, f"{float(value):.2f}")

    def _build_stepper_entry(self, parent, row, initial_value, integer=False, step=1):
        value_frame = ttk.Frame(parent)
        value_frame.grid(row=row, column=1, columnspan=2, sticky="w", pady=self.touch["row_pady"])

        minus_btn = ttk.Button(
            value_frame,
            text="-",
            style="AssignTouch.TButton",
            command=lambda: self._adjust_numeric_entry(entry, -step, integer=integer),
            width=3,
        )
        minus_btn.pack(side="left")

        entry = ttk.Entry(value_frame, width=14, style="AssignTouch.TEntry", justify="center")
        entry.pack(side="left", padx=8)
        if integer:
            entry.insert(0, str(int(initial_value or 0)))
        else:
            entry.insert(0, f"{float(initial_value or 0):.2f}")

        plus_btn = ttk.Button(
            value_frame,
            text="+",
            style="AssignTouch.TButton",
            command=lambda: self._adjust_numeric_entry(entry, step, integer=integer),
            width=3,
        )
        plus_btn.pack(side="left")

        return entry
    
    def _browse_image(self):
        """Open file dialog to select an image."""
        path = filedialog.askopenfilename(
            title='Select image',
            filetypes=[('Images', '*.png;*.jpg;*.jpeg;*.gif;*.bmp'), ('All files', '*.*')],
            initialdir='./Product List'
        )
        if path:
            # Convert to relative path if possible
            path = convert_image_path_to_relative(path)
            self.image_entry.delete(0, tk.END)
            self.image_entry.insert(0, path)

    def _set_readonly(self):
        """Disable input widgets when in read-only mode."""
        # Keep price and quantity editable in preset read-only viewer
        # (user requested price/stock editable in preset mode)
        try:
            if hasattr(self, 'category_combo'):
                self.category_combo.state(['disabled'])
            elif hasattr(self, 'category_entry'):
                self.category_entry.state(['disabled'])
        except Exception:
            try:
                if hasattr(self, 'category_combo'):
                    self.category_combo.config(state='disabled')
                elif hasattr(self, 'category_entry'):
                    self.category_entry.config(state='disabled')
            except Exception:
                pass
        try:
            self.image_entry.state(['disabled'])
        except Exception:
            try:
                self.image_entry.config(state='disabled')
            except Exception:
                pass
        # Leave description editable in Preset mode (user request)
        # Disable/hide browse button since image path should not be changed in preset viewer
        try:
            if hasattr(self, 'browse_btn'):
                try:
                    self.browse_btn.state(['disabled'])
                except Exception:
                    try:
                        self.browse_btn.config(state='disabled')
                    except Exception:
                        pass
        except Exception:
            pass
    
    def _on_save(self):
        try:
            price = float(self.price_entry.get().strip()) if self.price_entry.get().strip() else 0.0
        except Exception:
            tk.messagebox.showerror("Validation", "Price must be a number", parent=self)
            return
        
        try:
            qty = int(self.qty_entry.get().strip()) if self.qty_entry.get().strip() else 0
        except Exception:
            tk.messagebox.showerror("Validation", "Stock must be an integer", parent=self)
            return
        
        try:
            threshold = int(self.threshold_entry.get().strip()) if self.threshold_entry.get().strip() else 0
        except Exception:
            tk.messagebox.showerror("Validation", "Low stock threshold must be an integer", parent=self)
            return
        
        # Return updated item data
        self.result = dict(self.item_data)
        self.result['price'] = price
        self.result['quantity'] = qty
        self.result['low_stock_threshold'] = threshold
        try:
            if hasattr(self, 'category_var'):
                self.result['category'] = self.category_var.get().strip()
            elif hasattr(self, 'category_entry'):
                self.result['category'] = self.category_entry.get().strip()
            else:
                self.result['category'] = ''
        except Exception:
            self.result['category'] = self.item_data.get('category', '')
        self.result['description'] = self.desc_text.get('1.0', 'end-1c').strip()
        image_path = self.image_entry.get().strip()
        if image_path:
            image_path = convert_image_path_to_relative(image_path)
        self.result['image'] = image_path
        self.destroy()
    
    def _on_cancel(self):
        self.result = None
        self.destroy()


def convert_image_path_to_relative(absolute_path: str) -> str:
    """
    Convert an absolute image path to a relative path for cross-platform compatibility.
    
    If the path is already relative or is in the images directory, returns it as-is.
    If it's an absolute path, tries to make it relative to the project root or images directory.
    """
    if not absolute_path:
        return absolute_path

    normalized = str(absolute_path).strip().replace('\\', '/')

    # If already relative, keep it relative but normalize separators.
    if not os.path.isabs(normalized):
        if normalized.startswith('./'):
            normalized = normalized[2:]
        return normalized

    try:
        # This module is in project root; use it directly.
        project_root = os.path.dirname(os.path.abspath(__file__))
        project_root_norm = os.path.normpath(project_root)
        abs_norm = os.path.normpath(normalized)

        # If selected image is inside project, store project-relative path.
        common = os.path.commonpath([project_root_norm, abs_norm])
        if common == project_root_norm:
            rel_path = os.path.relpath(abs_norm, project_root_norm)
            return rel_path.replace('\\', '/')

        # If image is outside the project, keep absolute path so it still works.
        return normalized
    except Exception as e:
        print(f"Error converting path {absolute_path}: {e}")
        return normalized


class EditSlotDialog(tk.Toplevel):
    """Modal dialog to select from 3 term options or customize a slot item."""
    def __init__(self, parent, slot_idx=0, term_options=None, current_term_idx=0, category_options=None):
        """
        Args:
            parent: parent window
            slot_idx: slot index (for display)
            term_options: list of [term0_data, term1_data, term2_data] from the slot
            current_term_idx: which term is currently selected (0-2)
        """
        super().__init__(parent)
        self.slot_idx = slot_idx
        self.term_options = term_options or [None, None, None]
        self.current_term_idx = current_term_idx
        self.result = None
        self.customize_mode = False
        self.category_options = category_options or []
        self.touch = _get_touch_metrics(parent)
        _ensure_assign_touch_styles(self, self.touch)
        
        self.title(f"Assign Item to Slot {slot_idx+1}")
        self.transient(parent)
        self.grab_set()
        desired_w = int(self.winfo_screenwidth() * 0.66)
        desired_h = int(self.winfo_screenheight() * 0.70)
        width, height = _fit_window_to_screen(self, desired_w, desired_h)
        self.geometry(f"{width}x{height}")
        self._create_widgets()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=self.touch["section_pad"])
        frame.pack(fill="both", expand=True)

        # Title
        ttk.Label(frame, text=f"Slot {self.slot_idx+1} - Choose an item:", 
                  style="AssignTouch.Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, self.touch["row_pady"] + 4))

        # Build options list: 3 terms + customize
        options_list = []
        self.option_data = []  # Map option index to data
        
        for t_idx in range(3):
            item = None
            try:
                item = self.term_options[t_idx]
            except Exception:
                item = None
            if item:
                # Prefer name, fall back to code if name is empty
                label_name = item.get('name') or item.get('code') or 'Unknown'
                label = f"Term {t_idx+1}: {label_name}"
                self.option_data.append(item)
            else:
                label = f"Term {t_idx+1}: (empty)"
                self.option_data.append(None)
            options_list.append(label)
        
        options_list.append("Customize... (manual entry)")
        self.option_data.append(None)  # placeholder for customize
        
        # Combobox to select option
        ttk.Label(frame, text="Select:", style="AssignTouch.TLabel").grid(row=1, column=0, sticky="w", pady=self.touch["row_pady"])
        # Guard default selection index
        default_value = options_list[self.current_term_idx] if 0 <= self.current_term_idx < len(options_list) else options_list[0]
        self.select_var = tk.StringVar(value=default_value)
        self.select_combo = ttk.Combobox(
            frame,
            values=options_list,
            width=50,
            textvariable=self.select_var,
            state='readonly',
            style="AssignTouch.TCombobox",
        )
        self.select_combo.grid(row=1, column=1, sticky="ew", pady=self.touch["row_pady"])
        
        # Preview frame (shows item details when term selected)
        preview_frame = ttk.LabelFrame(frame, text="Preview", style="AssignTouch.TLabelframe", padding=self.touch["section_pad"] - 2)
        preview_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=self.touch["row_pady"])
        
        self.preview_text = tk.Text(preview_frame, width=60, height=8, state='disabled', font=("Helvetica", self.touch["base_font"]))
        self.preview_text.pack(fill='both', expand=True)
        
        # Update preview when selection changes
        self.select_combo.bind('<<ComboboxSelected>>', self._update_preview)
        self._update_preview()
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="e", pady=(self.touch["row_pady"], 0))
        
        select_btn = ttk.Button(btn_frame, text="Select", style="AssignTouch.TButton", command=self._on_select)
        select_btn.pack(side="right", padx=6)
        
        cancel_btn = ttk.Button(btn_frame, text="Cancel", style="AssignTouch.TButton", command=self._on_cancel)
        cancel_btn.pack(side="right")
        
        frame.columnconfigure(1, weight=1)

    def _update_preview(self, event=None):
        """Update preview text when selection changes."""
        selection = self.select_combo.get()
        self.preview_text.config(state='normal')
        self.preview_text.delete('1.0', tk.END)
        
        if "Customize" in selection:
            self.preview_text.insert('1.0', "(Manual entry mode - all fields editable)")
        else:
            # Find which option was selected
            idx = -1
            for i, opt in enumerate(self.select_combo['values']):
                if opt == selection:
                    idx = i
                    break
            
            if idx >= 0 and idx < len(self.option_data) and self.option_data[idx]:
                item = self.option_data[idx]
                preview = f"""Code: {item.get('code', '')}
Name: {item.get('name', '')}
Category: {item.get('category', '')}
Price: \u20b1{item.get('price', 0):.2f}
Quantity: {item.get('quantity', 1)}
Low Stock Threshold: {item.get('low_stock_threshold', 3)}
Image: {item.get('image', '(none)')}
Description: {item.get('description', '')}"""
                self.preview_text.insert('1.0', preview)
            else:
                self.preview_text.insert('1.0', "(Empty - no item for this term)")
        
        self.preview_text.config(state='disabled')

    def _on_select(self):
        """Handle selection."""
        selection = self.select_combo.get()
        
        if "Customize" in selection:
            # Open customize dialog
            self._open_customize_dialog()
        else:
            # Find which option
            idx = -1
            for i, opt in enumerate(self.select_combo['values']):
                if opt == selection:
                    idx = i
                    break
            
            if idx >= 0 and idx < len(self.option_data) and self.option_data[idx]:
                self.result = dict(self.option_data[idx])  # Copy to avoid shared reference
                self.destroy()
            else:
                tk.messagebox.showwarning("Invalid Selection", "Selected term has no item.", parent=self)

    def _open_customize_dialog(self):
        """Open full customization form."""
        selected_idx = -1
        selection = self.select_combo.get()
        for i, opt in enumerate(self.select_combo['values']):
            if opt == selection:
                selected_idx = i
                break

        seed_data = None
        if 0 <= selected_idx < len(self.option_data):
            candidate = self.option_data[selected_idx]
            if isinstance(candidate, dict):
                seed_data = dict(candidate)

        # If "Customize" is selected directly, prefill from current term when available.
        if not seed_data and 0 <= self.current_term_idx < len(self.option_data):
            candidate = self.option_data[self.current_term_idx]
            if isinstance(candidate, dict):
                seed_data = dict(candidate)

        CustomizeDialog(
            self,
            parent_result_callback=self._on_customize_done,
            category_options=self.category_options,
            initial_data=seed_data,
        )

    def _on_customize_done(self, custom_data):
        """Called when customize dialog completes."""
        if custom_data:
            self.result = custom_data
            self.destroy()

    def _on_cancel(self):
        """Cancel and close."""
        self.result = None
        self.destroy()


class CustomizeDialog(tk.Toplevel):
    """Dialog for manual entry/customization of item details."""
    def __init__(self, parent, parent_result_callback=None, category_options=None, initial_data=None):
        super().__init__(parent)
        self.title("Customize Item")
        self.transient(parent)
        self.grab_set()
        self.touch = _get_touch_metrics(parent)
        _ensure_assign_touch_styles(self, self.touch)
        self.result = None
        self.parent_result_callback = parent_result_callback
        self.category_options = category_options or []
        self.initial_data = dict(initial_data or {})
        desired_w = int(self.winfo_screenwidth() * 0.70)
        desired_h = int(self.winfo_screenheight() * 0.78)
        width, height = _fit_window_to_screen(self, desired_w, desired_h)
        self.geometry(f"{width}x{height}")
        self._create_widgets()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=self.touch["section_pad"])
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Name:", style="AssignTouch.TLabel").grid(row=0, column=0, sticky="w", pady=self.touch["row_pady"])
        self.name_entry = ttk.Entry(frame, width=40, style="AssignTouch.TEntry")
        self.name_entry.grid(row=0, column=1, sticky="ew", pady=self.touch["row_pady"])
        self.name_entry.insert(0, str(self.initial_data.get('name', '') or ''))

        ttk.Label(frame, text="Category:", style="AssignTouch.TLabel").grid(row=1, column=0, sticky="w", pady=self.touch["row_pady"])
        # Provide combobox so admin can pick existing categories or type new
        try:
            self.category_var = tk.StringVar(value=str(self.initial_data.get('category', '') or ''))
            self.category_entry = ttk.Combobox(
                frame,
                textvariable=self.category_var,
                values=self.category_options or [],
                width=40,
                style="AssignTouch.TCombobox",
            )
            self.category_entry.grid(row=1, column=1, sticky="ew", pady=self.touch["row_pady"])
            self.category_entry.configure(state='normal')
        except Exception:
            self.category_entry = ttk.Entry(frame, width=40, style="AssignTouch.TEntry")
            self.category_entry.grid(row=1, column=1, sticky="ew", pady=self.touch["row_pady"])
            self.category_entry.insert(0, str(self.initial_data.get('category', '') or ''))

        ttk.Label(frame, text="Price:", style="AssignTouch.TLabel").grid(row=2, column=0, sticky="w", pady=self.touch["row_pady"])
        self.price_entry = ttk.Entry(frame, width=20, style="AssignTouch.TEntry")
        self.price_entry.grid(row=2, column=1, sticky="w", pady=self.touch["row_pady"])
        self.price_entry.insert(0, str(self.initial_data.get('price', 0.0)))

        ttk.Label(frame, text="Quantity:", style="AssignTouch.TLabel").grid(row=3, column=0, sticky="w", pady=self.touch["row_pady"])
        self.qty_entry = ttk.Entry(frame, width=20, style="AssignTouch.TEntry")
        self.qty_entry.grid(row=3, column=1, sticky="w", pady=self.touch["row_pady"])
        self.qty_entry.insert(0, str(self.initial_data.get('quantity', 0)))

        ttk.Label(frame, text="Low Stock Threshold:", style="AssignTouch.TLabel").grid(row=4, column=0, sticky="w", pady=self.touch["row_pady"])
        self.threshold_entry = ttk.Entry(frame, width=20, style="AssignTouch.TEntry")
        self.threshold_entry.grid(row=4, column=1, sticky="w", pady=self.touch["row_pady"])
        self.threshold_entry.insert(0, str(self.initial_data.get('low_stock_threshold', 3)))

        ttk.Label(frame, text="Image Path:", style="AssignTouch.TLabel").grid(row=5, column=0, sticky="w", pady=self.touch["row_pady"])
        img_frame = ttk.Frame(frame)
        img_frame.grid(row=5, column=1, sticky="ew", pady=self.touch["row_pady"])
        self.image_entry = ttk.Entry(img_frame, width=34, style="AssignTouch.TEntry")
        self.image_entry.pack(side="left", fill="x", expand=True)
        self.image_entry.insert(0, str(self.initial_data.get('image', '') or ''))
        browse = ttk.Button(img_frame, text="Browse", style="AssignTouch.TButton", command=self._browse_image)
        browse.pack(side="left", padx=6)

        ttk.Label(frame, text="Description:", style="AssignTouch.TLabel").grid(row=6, column=0, sticky="nw", pady=self.touch["row_pady"])
        self.desc_text = tk.Text(frame, width=40, height=5, font=("Helvetica", self.touch["base_font"]))
        self.desc_text.grid(row=6, column=1, sticky="ew", pady=self.touch["row_pady"])
        self.desc_text.insert('1.0', str(self.initial_data.get('description', '') or ''))

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, sticky="e", pady=(self.touch["row_pady"], 0))
        save_btn = ttk.Button(btn_frame, text="Save", style="AssignTouch.TButton", command=self._on_save)
        save_btn.pack(side="right", padx=6)
        cancel_btn = ttk.Button(btn_frame, text="Cancel", style="AssignTouch.TButton", command=self._on_cancel)
        cancel_btn.pack(side="right")

        frame.columnconfigure(1, weight=1)

    def _browse_image(self):
        path = filedialog.askopenfilename(title='Select image', filetypes=[('Images','*.png;*.jpg;*.jpeg;*.gif;*.bmp')])
        if path:
            path = convert_image_path_to_relative(path)
            self.image_entry.delete(0, tk.END)
            self.image_entry.insert(0, path)

    def _on_save(self):
        name = self.name_entry.get().strip()
        if not name:
            tk.messagebox.showerror("Validation", "Name is required", parent=self)
            return
        try:
            price = float(self.price_entry.get().strip()) if self.price_entry.get().strip() else 0.0
        except Exception:
            tk.messagebox.showerror("Validation", "Price must be a number", parent=self)
            return
        try:
            qty = int(self.qty_entry.get().strip()) if self.qty_entry.get().strip() else 0
        except Exception:
            tk.messagebox.showerror("Validation", "Quantity must be an integer", parent=self)
            return
        try:
            threshold = int(self.threshold_entry.get().strip()) if self.threshold_entry.get().strip() else 0
        except Exception:
            tk.messagebox.showerror("Validation", "Low stock threshold must be an integer", parent=self)
            return

        image_path = self.image_entry.get().strip()
        if image_path:
            image_path = convert_image_path_to_relative(image_path)

        # Preserve existing fields unless explicitly changed in the form.
        data = dict(self.initial_data)
        if not data.get('code'):
            data['code'] = ''
        data.update({
            'name': name,
            'category': self.category_entry.get().strip(),
            'price': price,
            'quantity': qty,
            'low_stock_threshold': threshold,
            'image': image_path,
            'description': self.desc_text.get('1.0', 'end-1c').strip(),
        })
        if self.parent_result_callback:
            self.parent_result_callback(data)
        self.destroy()

    def _on_cancel(self):
        if self.parent_result_callback:
            self.parent_result_callback(None)
        self.destroy()


class AssignItemsScreen(tk.Frame):
    """Admin screen presenting a 5x8 grid (40 slots) of assignable items."""

    GRID_ROWS = 5
    GRID_COLS = 8
    MAX_SLOTS = GRID_ROWS * GRID_COLS
    SAVE_FILENAME = 'assigned_items.json'
    CUSTOM_SAVE_FILENAME = 'assigned_items_custom.json'
    TERM_COUNT = 3

    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f0f4f8")
        self.controller = controller
        self.touch = _get_touch_metrics(controller)
        _ensure_assign_touch_styles(self, self.touch)
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
        # Each slot contains a dict with key 'terms' -> list of term-specific assignments
        # e.g. {'terms': [term1_dict_or_none, term2_dict_or_none, term3_dict_or_none]}
        self.slots = [{'terms': [None] * self.TERM_COUNT} for _ in range(self.MAX_SLOTS)]
        self.slot_frames = []
        self.selected_slots = set()
        self._thumb_cache = {}
        self.current_term = self._resolve_current_term_from_controller()
        self.custom_mode = False  # Toggle between Preset and Custom modes
        # Snapshot of presets taken when entering custom mode; used to restore originals
        self._presets_snapshot = None
        # In-memory custom assignments (loaded from CUSTOM_SAVE_FILENAME if present)
        self._custom_slots = None
        
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

        # Prefer controller's configured path (if provided). Otherwise use this module's directory
        cfg_path = getattr(controller, 'config_path', None)
        if cfg_path:
            self._data_path = os.path.dirname(cfg_path)
        else:
            # Default to the repository / module directory so saves/loads are colocated with the app
            self._data_path = os.path.dirname(os.path.abspath(__file__))
        self._save_path = os.path.join(self._data_path, self.SAVE_FILENAME)
        self._custom_save_path = os.path.join(self._data_path, self.CUSTOM_SAVE_FILENAME)

        self.brand_header = tk.Frame(self, bg=self.brand_bg, height=self.header_px)
        self.brand_header.pack(side="top", fill="x")
        self.brand_header.pack_propagate(False)

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

        status_height = self.touch_dead_zone_bottom_px if self.touch_dead_zone_bottom_px > 0 else max(70, int(screen_height * 0.08))
        self.status_zone = tk.Frame(self, bg="#111111", height=status_height)
        self.status_zone.pack(side="bottom", fill="x")
        self.status_zone.pack_propagate(False)
        self.status_panel = SystemStatusPanel(self.status_zone, controller=self.controller)
        self.status_panel.pack(fill="both", expand=True)

        self.touch_container = tk.Frame(self, bg="#f0f4f8")
        self.touch_container.pack(fill="both", expand=True)

        self._create_widgets()
        self.load_slots()
        self.bind("<<ShowFrame>>", self._on_show_frame)

    def _on_show_frame(self, event=None):
        self._refresh_brand_header()
        try:
            self.status_panel.refresh_display()
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

    def _create_widgets(self):
        root = self.touch_container
        header = ttk.Frame(root, padding=self.touch["section_pad"])
        header.pack(fill='x')

        # Keep controls visible on larger font scales by splitting header into rows.
        top_row = ttk.Frame(header)
        top_row.pack(fill='x')

        left_section = ttk.Frame(top_row)
        left_section.pack(side='left', fill='x', expand=True)
        ttk.Label(left_section, text="Assign Items to Slots", style="AssignTouch.Title.TLabel").pack(side='left')
        
        # Term selector dropdown
        ttk.Label(left_section, text="Term:", style="AssignTouch.Term.TLabel").pack(side='left', padx=(20, 8))
        self.term_var = tk.StringVar(value=f'Term {self.current_term + 1}')
        term_combo = ttk.Combobox(
            left_section,
            textvariable=self.term_var,
            values=[f'Term {i+1}' for i in range(self.TERM_COUNT)],
            state='readonly',
            width=14,
            style="AssignTouch.Term.TCombobox",
        )
        term_combo.pack(side='left', padx=(0, 12))
        term_combo.bind('<<ComboboxSelected>>', lambda e: self._on_term_change())
        
        # Mode indicator and Custom toggle
        ttk.Label(left_section, text="Mode:", style="AssignTouch.Term.TLabel").pack(side='left', padx=(20, 6))
        self.mode_var = tk.StringVar(value='Preset')
        self.mode_label = ttk.Label(left_section, text='Preset', style="AssignTouch.Term.TLabel", foreground='green')
        self.mode_label.pack(side='left', padx=(0, 8))
        
        custom_btn = ttk.Button(
            left_section,
            text='Switch to Custom',
            style="AssignTouch.TButton",
            command=self._toggle_custom_mode,
            width=18,
        )
        custom_btn.pack(side='left', padx=(0, 12))

        actions_row = ttk.Frame(header)
        actions_row.pack(fill='x', pady=(self.touch["row_pady"], 0))
        nav_frame = ttk.Frame(actions_row)
        nav_frame.pack(side='left')
        ttk.Button(
            nav_frame,
            text="Back",
            style="AssignTouch.TButton",
            command=lambda: self.controller.show_frame("AdminScreen"),
        ).pack(side='left', padx=6)
        btn_frame = ttk.Frame(actions_row)
        btn_frame.pack(side='right')
        ttk.Button(btn_frame, text="Load", style="AssignTouch.TButton", command=self.load_slots).pack(side='left', padx=6)
        ttk.Button(btn_frame, text="Save", style="AssignTouch.TButton", command=self.save_slots).pack(side='left', padx=6)
        ttk.Button(btn_frame, text="Clear All", style="AssignTouch.TButton", command=self.clear_all).pack(side='left', padx=6)

        # Scrollable area for grid (vertical only)
        canvas_container = ttk.Frame(root)
        canvas_container.pack(fill='both', expand=True, padx=self.touch["section_pad"], pady=self.touch["row_pady"])

        self.canvas = tk.Canvas(canvas_container, bg="#f0f4f8", highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_container, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')

        self.grid_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0,0), window=self.grid_frame, anchor='nw')

        # Update scrollregion whenever the grid changes size.
        def _on_grid_config(e):
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox('all'))
            except Exception:
                pass

        self.grid_frame.bind('<Configure>', _on_grid_config)

        # Ensure canvas window expands/shrinks with container
        def _on_canvas_config(e):
            try:
                # keep window width at least canvas width so grid packs correctly
                self.canvas.itemconfig(self.canvas_window, width=self.canvas.winfo_width())
            except Exception:
                pass

        self.canvas.bind('<Configure>', _on_canvas_config)
        # Allow mouse wheel to scroll vertically over the canvas
        def _on_mousewheel(event):
            # Windows and Mac differ; use delta
            delta = 0
            if event.num == 5 or event.delta < 0:
                delta = 1
            elif event.num == 4 or event.delta > 0:
                delta = -1
            self.canvas.yview_scroll(delta, 'units')

        # Bind cross-platform mouse wheel
        self.canvas.bind_all('<MouseWheel>', _on_mousewheel)
        self.canvas.bind_all('<Button-4>', _on_mousewheel)
        self.canvas.bind_all('<Button-5>', _on_mousewheel)

        self.canvas.pack(fill='both', expand=True, side='left')

        # Build grid placeholders
        for r in range(self.GRID_ROWS):
            row_frames = []
            for c in range(self.GRID_COLS):
                idx = r * self.GRID_COLS + c
                frm = ttk.Frame(self.grid_frame, relief='ridge', padding=self.touch["card_padding"])
                frm.grid(
                    row=r,
                    column=c,
                    padx=self.touch["slot_spacing"],
                    pady=self.touch["slot_spacing"],
                    sticky='nsew',
                )
                
                # Slot header with selection marker
                slot_hdr = ttk.Frame(frm)
                slot_hdr.pack(fill='x', pady=(0,2))
                slot_lbl = ttk.Label(slot_hdr, text=f"Slot {idx+1}", style="AssignTouch.Small.TLabel")
                slot_lbl.pack(side='left', fill='x', expand=True)
                sel_marker = ttk.Label(slot_hdr, text=" ", width=2, anchor='center')
                sel_marker.pack(side='right')

                # Content area (compact layout)
                content = ttk.Frame(frm)
                content.pack(fill='both', expand=True, pady=(2,2))

                # Thumbnail (small)
                thumb_lbl = tk.Label(
                    content,
                    text='',
                    width=1,
                    height=4,
                    anchor='center',
                    background='#e8e8e8',
                    relief='sunken',
                    font=("Helvetica", max(8, self.touch["small_font"])),
                )
                thumb_lbl.pack(fill='both', expand=False, pady=(0,2))

                # Item info (name and details)
                info = ttk.Frame(content)
                info.pack(fill='both', expand=True, pady=(0,2))
                name_lbl = ttk.Label(
                    info,
                    text="Empty",
                    style="AssignTouch.Small.TLabel",
                    wraplength=120,
                    justify='left',
                )
                name_lbl.pack(anchor='nw', fill='x')
                details_lbl = ttk.Label(
                    info,
                    text="",
                    style="AssignTouch.Small.TLabel",
                    wraplength=116,
                    justify='left',
                )
                details_lbl.pack(anchor='nw', fill='both', expand=True)

                # Buttons (top/mid/bot vertical layout so all options remain visible)
                btns = ttk.Frame(frm)
                btns.pack(fill='x', pady=(2,0))
                edit_btn = ttk.Button(
                    btns,
                    text="Edit",
                    style="AssignTouch.Small.TButton",
                    command=lambda i=idx: self.edit_slot(i),
                )
                edit_btn.pack(fill='x')
                test_btn = ttk.Button(
                    btns,
                    text="Test",
                    style="AssignTouch.Small.TButton",
                    command=lambda i=idx: self.test_motor(i),
                )
                test_btn.pack(fill='x', pady=1)
                clear_btn = ttk.Button(
                    btns,
                    text="Clear",
                    style="AssignTouch.Small.TButton",
                    command=lambda i=idx: self.clear_slot(i),
                )
                clear_btn.pack(fill='x')

                # selection toggle binding
                def make_toggle(i):
                    def _toggle(event=None):
                        if i in self.selected_slots:
                            self.selected_slots.remove(i)
                        else:
                            self.selected_slots.add(i)
                        self._update_slot_selection_visual(i)
                    return _toggle

                frm.bind('<Button-1>', make_toggle(idx))
                for w in (slot_lbl, thumb_lbl, name_lbl, details_lbl, content, slot_hdr, info):
                    w.bind('<Button-1>', make_toggle(idx))

                row_frames.append({'frame':frm, 'name':name_lbl, 'details':details_lbl, 'thumb':thumb_lbl, 'sel_marker':sel_marker})
            self.slot_frames.append(row_frames)

        # Make columns expand evenly
        for c in range(self.GRID_COLS):
            self.grid_frame.grid_columnconfigure(c, weight=1)

    def _slot_to_position(self, idx):
        r = idx // self.GRID_COLS
        c = idx % self.GRID_COLS
        return r, c

    def _resolve_current_term_from_controller(self):
        """Resolve active term from controller state/config (0-based)."""
        try:
            raw = getattr(self.controller, 'assigned_term', 0)
            term_idx = int(raw)
        except Exception:
            term_idx = 0
        return max(0, min(self.TERM_COUNT - 1, term_idx))

    def _persist_current_term_to_config(self):
        """Persist active term to shared config so dashboard uses the same term."""
        term_idx = max(0, min(self.TERM_COUNT - 1, int(self.current_term)))
        try:
            setattr(self.controller, 'assigned_term', term_idx)
        except Exception:
            pass

        cfg = getattr(self.controller, 'config', None)
        if not isinstance(cfg, dict):
            return
        if cfg.get('assigned_term') == term_idx:
            return

        cfg['assigned_term'] = term_idx
        try:
            save_fn = getattr(self.controller, 'save_config_to_json', None)
            if callable(save_fn):
                save_fn()
            else:
                cfg_path = getattr(self.controller, 'config_path', None)
                if cfg_path:
                    with open(cfg_path, 'w', encoding='utf-8') as f:
                        json.dump(cfg, f, indent=4)
        except Exception as e:
            print(f"[AssignItemsScreen] Failed to persist assigned_term: {e}")

    def _on_term_change(self):
        txt = self.term_var.get() or 'Term 1'
        try:
            # Expect format 'Term N'
            n = int(txt.split()[-1])
            self.current_term = max(0, min(self.TERM_COUNT-1, n-1))
        except Exception:
            self.current_term = 0
        self._persist_current_term_to_config()
        # Refresh all slots to display selected term
        # If slots appear empty, attempt to load from disk first to pick up presets
        try:
            # Quick check: are most slots empty for the selected term?
            empty_count = 0
            for s in self.slots:
                try:
                    if not s or not isinstance(s, dict) or not s.get('terms'):
                        empty_count += 1
                        continue
                    if not s.get('terms')[self.current_term]:
                        empty_count += 1
                except Exception:
                    empty_count += 1
            # If a large portion are empty and a save file exists, reload
            if empty_count > (self.MAX_SLOTS // 2) and os.path.exists(self._save_path):
                try:
                    self.load_slots()
                except Exception:
                    pass
        except Exception:
            pass
        # Refresh UI (text fast, images deferred)
        self.refresh_all()

    def _empty_slots_template(self):
        """Return a fresh empty 40-slot structure in per-term wrapper format."""
        return [{'terms': [None] * self.TERM_COUNT} for _ in range(self.MAX_SLOTS)]

    def _migrate_slots_data(self, data):
        """Normalize persisted slot data into per-slot {'terms': [...]} wrappers."""
        if not isinstance(data, list):
            return None

        migrated = []
        for idx in range(self.MAX_SLOTS):
            entry = data[idx] if idx < len(data) else None
            if entry is None:
                migrated.append({'terms': [None] * self.TERM_COUNT})
                continue
            if isinstance(entry, dict) and 'terms' in entry and isinstance(entry['terms'], list):
                terms = (entry['terms'] + [None] * self.TERM_COUNT)[:self.TERM_COUNT]
                migrated.append({'terms': terms})
                continue
            if isinstance(entry, dict):
                migrated.append({'terms': [entry] + [None] * (self.TERM_COUNT - 1)})
                continue
            migrated.append({'terms': [None] * self.TERM_COUNT})
        return migrated

    def _load_slots_from_path(self, path):
        """Load and normalize slot data from JSON path; returns None if unavailable/invalid."""
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            return self._migrate_slots_data(data)
        except Exception:
            return None

    def _toggle_custom_mode(self):
        """Toggle between Preset and Custom mode."""
        entering = not self.custom_mode
        self.custom_mode = entering

        if self.custom_mode:
            # Entering Custom:
            # 1) snapshot Preset assignments (disk first, memory fallback)
            preset_from_disk = self._load_slots_from_path(self._save_path)
            if preset_from_disk is not None:
                self._presets_snapshot = copy.deepcopy(preset_from_disk)
            else:
                self._presets_snapshot = copy.deepcopy(self.slots)

            # 2) load existing Custom assignments if any, else start with empty slots
            if self._custom_slots is None:
                custom_from_disk = self._load_slots_from_path(self._custom_save_path)
                if custom_from_disk is not None:
                    self._custom_slots = copy.deepcopy(custom_from_disk)
                else:
                    self._custom_slots = self._empty_slots_template()

            self.slots = copy.deepcopy(self._custom_slots)
            self.mode_label.config(text='Custom', foreground='red')
            self.refresh_all()
            self._publish_assignments()
            return

        # Leaving Custom:
        # 1) keep custom edits in memory
        try:
            self._custom_slots = copy.deepcopy(self.slots)
        except Exception:
            pass

        # 2) restore preset snapshot
        try:
            if self._presets_snapshot is not None:
                self.slots = copy.deepcopy(self._presets_snapshot)
            else:
                self.slots = self._empty_slots_template()
            self.refresh_all()
            self._publish_assignments()
        except Exception:
            pass
        finally:
            self._presets_snapshot = None
            self.mode_label.config(text='Preset', foreground='green')

    def auto_assign_current_term(self):
        """Auto-populate all slots with products from current term in assigned_items.json."""
        term_idx = self.current_term
        
        # Confirm action
        if not tk.messagebox.askyesno("Auto-assign Term", 
            f"This will populate all {self.MAX_SLOTS} slots with products from Term {term_idx+1}.\nContinue?", parent=self):
            return
        
        for slot_idx in range(self.MAX_SLOTS):
            # Ensure slot wrapper exists
            if not self.slots[slot_idx]:
                self.slots[slot_idx] = {'terms': [None] * self.TERM_COUNT}
            
            # Get product data from current term (if it exists)
            try:
                term_data = self.slots[slot_idx].get('terms', [None]*self.TERM_COUNT)[term_idx]
                if term_data:
                    # Copy to ensure no shared references
                    self.slots[slot_idx]['terms'][term_idx] = dict(term_data)
                    self.refresh_slot(slot_idx)
            except Exception:
                pass
        
        self._publish_assignments()
        tk.messagebox.showinfo("Auto-assign Complete", 
            f"All {self.MAX_SLOTS} slots populated with Term {term_idx+1} products!", parent=self)

    def edit_slot(self, idx):
        # If this slot appears empty in-memory, try reloading from disk to get latest persisted assignments
        slot_entry = self.slots[idx] if idx < len(self.slots) else None
        if (not self.custom_mode) and ((not slot_entry) or (isinstance(slot_entry, dict) and all(t is None for t in slot_entry.get('terms', [])))):
            try:
                print(f"[DEBUG] edit_slot({idx+1}) _save_path={self._save_path} exists={os.path.exists(self._save_path)}")
                if os.path.exists(self._save_path):
                    try:
                        with open(self._save_path, 'r', encoding='utf-8-sig') as _f:
                            _data = json.load(_f)
                        first = _data[0] if isinstance(_data, list) and len(_data) > 0 else None
                        if first and isinstance(first, dict) and 'terms' in first:
                            term_flags = [bool(t) for t in first.get('terms', [])]
                        else:
                            term_flags = None
                        print(f"[DEBUG] file first slot terms present: {term_flags}")
                    except Exception as e:
                        print(f"[DEBUG] failed reading save file: {e}")
                self.load_slots()
            except Exception as e:
                print(f"[DEBUG] load_slots failed: {e}")

        # Fallback loading from alternate paths
        if not self.custom_mode:
            try:
                slot_after = self.slots[idx] if idx < len(self.slots) else None
                if (not slot_after) or all(t is None for t in slot_after.get('terms', [])):
                    fallback_paths = [
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), self.SAVE_FILENAME),
                        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), self.SAVE_FILENAME),
                        os.path.join(os.path.expanduser('~'), 'Documents', self.SAVE_FILENAME),
                    ]
                    for p in fallback_paths:
                        if p == self._save_path or not os.path.exists(p):
                            continue
                        try:
                            with open(p, 'r', encoding='utf-8-sig') as _f:
                                _data = json.load(_f)
                            if isinstance(_data, list) and len(_data) >= self.MAX_SLOTS:
                                _data = _data[:self.MAX_SLOTS]
                                migrated = []
                                for entry in _data:
                                    if entry is None:
                                        migrated.append({'terms': [None] * self.TERM_COUNT})
                                        continue
                                    if isinstance(entry, dict) and 'terms' in entry and isinstance(entry['terms'], list):
                                        terms = (entry['terms'] + [None] * self.TERM_COUNT)[:self.TERM_COUNT]
                                        migrated.append({'terms': terms})
                                        continue
                                    if isinstance(entry, dict):
                                        migrated.append({'terms': [entry] + [None] * (self.TERM_COUNT - 1)})
                                        continue
                                    migrated.append({'terms': [None] * self.TERM_COUNT})
                                self.slots = migrated
                                print(f"[DEBUG] edit_slot: loaded fallback slots from {p}")
                                break
                        except Exception as e:
                            print(f"[DEBUG] edit_slot: failed reading fallback {p}: {e}")
            except Exception:
                pass

        # Ensure slot wrapper exists
        if not self.slots[idx]:
            self.slots[idx] = {'terms': [None] * self.TERM_COUNT}
        
        # Allow full slot editing in both Preset and Custom modes.
        term_options = self.slots[idx].get('terms') or [None] * self.TERM_COUNT
        dlg = EditSlotDialog(
            self.master,
            slot_idx=idx,
            term_options=term_options,
            current_term_idx=self.current_term,
            category_options=self.get_category_options(),
        )
        self.master.wait_window(dlg)
        if getattr(dlg, 'result', None):
            self.slots[idx]['terms'][self.current_term] = dlg.result
            self.refresh_slot(idx)
            self._publish_assignments()
        return

    def _check_esp32_connection(self, esp32_host):
        """Check if ESP32 is reachable by sending a STATUS command."""
        try:
            result = send_command(esp32_host, "STATUS", timeout=1.0)
            return True, result
        except Exception as e:
            return False, str(e)

    def _parse_active_slots_from_status(self, status_msg):
        """Parse STATUS response (e.g. '1,5,12' or 'NONE') into a set of slot numbers."""
        text = str(status_msg or "").strip()
        if not text or text.upper() == "NONE":
            return set()
        active = set()
        for token in text.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                active.add(int(token))
            except Exception:
                continue
        return active

    def _read_limit_status(self, esp32_host):
        """Read limit-pin debug status from ESP32."""
        try:
            return send_command(esp32_host, "LIMIT_STATUS", timeout=1.0)
        except Exception as e:
            return f"ERR LIMIT_STATUS: {e}"

    def _wait_for_slot_rotation_complete(self, esp32_host, slot_num, timeout_sec=18.0, poll_interval_sec=0.15, debug=False):
        """
        Wait until a slot is no longer active in STATUS.
        In firmware, this corresponds to a completed rotation (2 limit-switch pulses)
        or a failsafe timeout.
        """
        deadline = time.time() + max(1.0, float(timeout_sec))
        last_debug_ts = 0.0
        while time.time() < deadline:
            try:
                status_msg = send_command(esp32_host, "STATUS", timeout=1.0)
                active = self._parse_active_slots_from_status(status_msg)
                if debug:
                    now_ts = time.time()
                    if now_ts - last_debug_ts >= 0.6:
                        limit_dbg = self._read_limit_status(esp32_host)
                        print(f"[TEST MOTOR] Slot {slot_num} LIMIT_STATUS: {limit_dbg}")
                        last_debug_ts = now_ts
                if slot_num not in active:
                    return True
            except Exception:
                pass
            time.sleep(max(0.05, float(poll_interval_sec)))
        return False

    def test_motor(self, idx):
        """Test one full spring rotation for the given slot (2 limit pulses)."""
        import logging
        
        slot_num = idx + 1  # Slots are 1-indexed
        
        # Suppress verbose logging from esp32_client during motor test
        esp32_logger = logging.getLogger('root')
        original_level = esp32_logger.level
        esp32_logger.setLevel(logging.CRITICAL)  # Only show CRITICAL errors
        
        try:
            # Get ESP32 host from controller config
            config = getattr(self.controller, 'config', {})
            esp32_host = config.get('esp32_host', '192.168.4.1')
            
            if not esp32_host:
                messagebox.showerror(
                    "Motor Test Error", 
                    "ESP32 host not configured.\nSet 'esp32_host' in config.json (e.g., 'serial:/dev/ttyUSB0' or '192.168.4.1')",
                    parent=self
                )
                return
            
            print(f"[TEST MOTOR] Testing slot {slot_num} using ESP32 host: {esp32_host}")
            
            # First check if ESP32 is reachable
            print(f"[TEST MOTOR] Checking ESP32 connection...")
            is_connected, status_msg = self._check_esp32_connection(esp32_host)
            
            if not is_connected:
                messagebox.showerror(
                    "Motor Test - Connection Failed", 
                    f"Cannot reach ESP32 at {esp32_host}\n\nConnection Error: {status_msg}\n\nPlease check:\n- ESP32 is powered on and connected\n- Serial port is correct (if using serial)\n- Network is connected (if using TCP)\n- USB cable is properly connected",
                    parent=self
                )
                print(f"[TEST MOTOR] FAILED: Cannot connect to ESP32: {status_msg}")
                return
            
            print(f"[TEST MOTOR] ESP32 connection OK. Status: {status_msg}")
            print(f"[TEST MOTOR] Slot {slot_num} LIMIT_STATUS before pulse: {self._read_limit_status(esp32_host)}")
            
            # Trigger one full spring rotation; firmware stops at 2 limit pulses.
            print(f"[TEST MOTOR] Pulsing slot {slot_num}...")
            # Ensure machine supports only slots 1-40
            if slot_num < 1 or slot_num > self.MAX_SLOTS:
                messagebox.showerror(
                    "Motor Test - Unsupported Slot",
                    f"Slot {slot_num} is out of range. This machine supports slots 1-{self.MAX_SLOTS} only.",
                    parent=self
                )
                print(f"[TEST MOTOR] ERROR: Slot {slot_num} out of supported range (1-{self.MAX_SLOTS})")
                return

            # For supported slots (1-40) use ESP32
            failsafe_ms = 15000
            try:
                hw = config.get('hardware', {}) if isinstance(config, dict) else {}
                failsafe_ms = int(hw.get('vend_rotation_failsafe_ms', 15000))
            except Exception:
                failsafe_ms = 15000

            # Use PULSE with failsafe timeout; completion is based on limit pulses.
            result = pulse_slot(esp32_host, slot_num, failsafe_ms, timeout=3.0)
            
            # Validate response - should contain "OK"
            if result and "OK" in result.upper():
                wait_timeout_sec = max(5.0, (failsafe_ms / 1000.0) + 2.0)
                completed = self._wait_for_slot_rotation_complete(
                    esp32_host=esp32_host,
                    slot_num=slot_num,
                    timeout_sec=wait_timeout_sec,
                    debug=True
                )
                print(f"[TEST MOTOR] Slot {slot_num} LIMIT_STATUS after pulse: {self._read_limit_status(esp32_host)}")
                if completed:
                    messagebox.showinfo(
                        "Motor Test Success",
                        f"Slot {slot_num} completed one rotation (2 limit-switch pulses).\n\nESP32 Response: {result}",
                        parent=self
                    )
                    print(f"[TEST MOTOR] SUCCESS: Slot {slot_num} completed one rotation via 2 pulses.")
                else:
                    messagebox.showwarning(
                        "Motor Test Warning",
                        f"Slot {slot_num} command acknowledged, but rotation completion was not confirmed before timeout.\n\n"
                        f"Failsafe timeout: {failsafe_ms} ms\nESP32 Response: {result}",
                        parent=self
                    )
                    print(f"[TEST MOTOR] WARNING: Slot {slot_num} completion not confirmed within timeout.")
            else:
                messagebox.showerror(
                    "Motor Test Failed",
                    f"Slot {slot_num} did not receive proper confirmation from ESP32\n\nResponse: {result if result else 'No response'}\n\nMake sure:\n- RXTX cable is connected between ESP32 and Raspberry Pi\n- ESP32 firmware is loaded and running\n- Slot number is valid (1-{self.MAX_SLOTS})",
                    parent=self
                )
                
        except TimeoutError as e:
            messagebox.showerror(
                "Motor Test - Connection Timeout", 
                f"ESP32 did not respond in time for slot {slot_num}\n\nHost: {esp32_host}\nError: {str(e)}\n\nPlease check connection and try again.",
                parent=self
            )
            print(f"[TEST MOTOR] TIMEOUT on slot {slot_num}: {str(e)}")
        except ConnectionRefusedError as e:
            messagebox.showerror(
                "Motor Test - Connection Refused", 
                f"ESP32 refused connection for slot {slot_num}\n\nHost: {esp32_host}\n\nThe ESP32 may not be running or listening on this port.",
                parent=self
            )
            print(f"[TEST MOTOR] CONNECTION REFUSED on slot {slot_num}: {str(e)}")
        except Exception as e:
            error_msg = str(e)
            messagebox.showerror(
                "Motor Test Error", 
                f"Failed to test motor for slot {slot_num}:\n\n{error_msg}\n\nHost: {esp32_host}",
                parent=self
            )
            print(f"[TEST MOTOR] ERROR on slot {slot_num}: {error_msg}")
        
        finally:
            # Restore original logging level
            esp32_logger.setLevel(original_level)

    def clear_slot(self, idx):
        # Clear only the currently selected term for this slot
        if not self.slots[idx]:
            return
        try:
            self.slots[idx]['terms'][self.current_term] = None
        except Exception:
            self.slots[idx] = {'terms': [None] * self.TERM_COUNT}
        self.refresh_slot(idx)
        self._publish_assignments()

    def _get_categories_from_item_name(self, item_name):
        """Extract categories from item name based on keywords.
        
        Returns a list of categories the item belongs to based on keywords.
        If no keywords match, returns ['Misc'].
        """
        if not item_name:
            return ['Misc']
        
        name_lower = item_name.lower()
        categories = set()
        
        # Check each category for keywords using pre-computed keyword map
        for cat, keywords in self._keyword_map.items():
            for keyword in keywords:
                if keyword in name_lower:
                    categories.add(cat)
                    break  # Found this category, move to next
        
        # If no categories matched, put in Misc
        if not categories:
            return ['Misc']
        
        return sorted(list(categories))

    def _generate_description_for_item(self, item_name, item_price):
        """Auto-generate a meaningful description based on item category.
        
        Returns a description string with category and specs hint.
        """
        if not item_name:
            return f"Price: \u20b1{item_price:.2f}"
        
        categories = self._get_categories_from_item_name(item_name)
        category_text = ', '.join(categories) if categories else 'Miscellaneous'
        
        # Generate description based on category
        desc_map = {
            'Resistor': 'Resistor - Electronic component for limiting current',
            'Capacitor': 'Capacitor - Energy storage and filtering component',
            'IC': 'Integrated Circuit - Microchip for signal processing',
            'Amplifier': 'Amplifier - Signal amplification component',
            'Board': 'PCB/Board - Circuit board or development board',
            'Bundle': 'Bundle/Kit - Assorted electronic components pack',
            'Wires': 'Wires/Cables - Connection and wiring components',
            'Misc': 'Miscellaneous electronic component'
        }
        
        # Get description from primary category
        base_desc = desc_map.get(categories[0] if categories else 'Misc', 'Electronic component')
        return f"{base_desc} - \u20b1{item_price:.2f}"

    def refresh_slot(self, idx):
        r, c = self._slot_to_position(idx)
        slot_ui = self.slot_frames[r][c]
        # Show info for current term only
        term_idx = self.current_term
        data = None
        try:
            slot = self.slots[idx]
            if slot and 'terms' in slot and len(slot['terms']) > term_idx:
                data = slot['terms'][term_idx]
        except Exception:
            data = None

        if data:
            slot_ui['name'].config(text=(data.get('name','') or '')[:18])
            # Get auto-detected categories from item name
            item_categories = self._get_categories_from_item_name(data.get('name', ''))
            category_text = ', '.join(item_categories) if item_categories else 'Misc'
            slot_ui['details'].config(text=f"{category_text} | {data.get('quantity',0)} pcs | \u20b1{data.get('price',0):.2f}")
        else:
            slot_ui['name'].config(text='Empty')
            slot_ui['details'].config(text='')
        # handle thumbnail if available - image loading is deferred via scheduled batches
        try:
            img_path = data.get('image','') if data else ''
        except Exception:
            img_path = ''
        # Only load images synchronously when requested via the deferred loader
        img = None
        resolved_img_path = self._resolve_image_path(img_path)
        cache_key = (idx, term_idx, resolved_img_path)
        if resolved_img_path and PIL_AVAILABLE and os.path.exists(resolved_img_path):
            img = self._thumb_cache.get(cache_key)
            if img:
                slot_ui['thumb'].config(image=img, text='')
                slot_ui['thumb'].image = img
            else:
                # Show placeholder until deferred loader converts to thumbnail
                slot_ui['thumb'].config(text='Image', image='')
        else:
            slot_ui['thumb'].config(text='No Image', image='')

    def refresh_all(self):
        # Fast refresh: update text/details quickly, defer image thumbnail generation
        for idx in range(self.MAX_SLOTS):
            self.refresh_slot(idx)
        # Schedule background thumbnail loading in small batches to avoid UI freeze
        try:
            self._schedule_load_images(batch=8, delay=40)
        except Exception:
            pass

    def _schedule_load_images(self, batch=8, delay=40):
        """Load thumbnails in small batches to keep UI responsive."""
        if getattr(self, '_img_load_job', None):
            # already scheduled
            return
        self._img_load_index = 0
        def _step():
            start = self._img_load_index
            end = min(self.MAX_SLOTS, start + batch)
            for i in range(start, end):
                try:
                    # Force image load by re-running thumbnail code
                    r, c = self._slot_to_position(i)
                    slot_ui = self.slot_frames[r][c]
                    term_idx = self.current_term
                    slot = self.slots[i]
                    data = None
                    if slot and 'terms' in slot and len(slot['terms']) > term_idx:
                        data = slot['terms'][term_idx]
                    img_path = data.get('image','') if data else ''
                    resolved_img_path = self._resolve_image_path(img_path)
                    cache_key = (i, term_idx, resolved_img_path)
                    if resolved_img_path and PIL_AVAILABLE and os.path.exists(resolved_img_path):
                        if not self._thumb_cache.get(cache_key):
                            try:
                                pil = Image.open(resolved_img_path)
                                pil.thumbnail((80,80))
                                img = pil_to_photoimage(pil)
                                self._thumb_cache[cache_key] = img
                                slot_ui['thumb'].config(image=img, text='')
                                slot_ui['thumb'].image = img
                            except Exception:
                                slot_ui['thumb'].config(text='No Image', image='')
                except Exception:
                    pass
            self._img_load_index = end
            if self._img_load_index < self.MAX_SLOTS:
                self._img_load_job = self.after(delay, _step)
            else:
                self._img_load_job = None
        # Start after a short pause to let UI update
        self._img_load_job = self.after(120, _step)

    def _resolve_image_path(self, image_path):
        """Resolve an image path from saved data to an existing local file path."""
        raw = str(image_path or "").strip()
        if not raw:
            return None
        raw = raw.replace('\\', '/')
        if raw.startswith('./'):
            raw = raw[2:]

        candidates = []
        if os.path.isabs(raw):
            candidates.append(raw)
        else:
            candidates.append(get_absolute_path(raw))
            candidates.append(raw)

            # Backward compatibility: handle old saved values like "raon-vending-rpi4/images/x.jpg"
            project_name = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
            prefix = f"{project_name}/"
            if raw.startswith(prefix):
                trimmed = raw[len(prefix):]
                candidates.append(get_absolute_path(trimmed))

            if not raw.startswith('images/'):
                filename = os.path.basename(raw)
                candidates.append(get_absolute_path(f"images/{filename}"))

        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def _update_slot_selection_visual(self, idx):
        r, c = self._slot_to_position(idx)
        slot_ui = self.slot_frames[r][c]
        if idx in self.selected_slots:
            try:
                slot_ui['sel_marker'].config(text='●')
            except Exception:
                pass
        else:
            try:
                slot_ui['sel_marker'].config(text=' ')
            except Exception:
                pass

    def assign_selected_from_dropdown(self):
        name = self.item_var.get()
        if not name:
            tk.messagebox.showwarning('Assign', 'Select an item to assign', parent=self)
            return
        # If user selected "Customize...", open dialog to create a custom item
        if name == 'Customize...':
            # Use callback to receive result from CustomizeDialog
            try:
                if hasattr(self, '_last_custom_item'):
                    delattr(self, '_last_custom_item')
            except Exception:
                pass

            def _cb(data):
                setattr(self, '_last_custom_item', data)

            dlg = CustomizeDialog(self.master, parent_result_callback=_cb, category_options=self.get_category_options())
            self.master.wait_window(dlg)
            custom_item = getattr(self, '_last_custom_item', None)
            if not custom_item:
                return
            selected_item = custom_item
        else:
            items = getattr(self.controller, 'items', []) or []
            selected_item = None
            for it in items:
                if it.get('name') == name:
                    selected_item = it
                    break
            if not selected_item:
                tk.messagebox.showwarning('Assign', f'Item "{name}" not found', parent=self)
                return

        term_idx = self.current_term
        for idx in list(self.selected_slots):
            # ensure wrapper
            if not self.slots[idx]:
                self.slots[idx] = {'terms': [None] * self.TERM_COUNT}
            # shallow copy to avoid shared references
            item_copy = dict(selected_item)
            if item_copy.get('image'):
                item_copy['image'] = convert_image_path_to_relative(item_copy['image'])
            self.slots[idx]['terms'][term_idx] = item_copy
            self.refresh_slot(idx)
        # clear selection
        for idx in list(self.selected_slots):
            self.selected_slots.remove(idx)
            self._update_slot_selection_visual(idx)
        # Publish to controller and update kiosk
        self._publish_assignments()


    def clear_all(self):
        if tk.messagebox.askyesno("Confirm", "Clear all assigned slots?"):
            self.slots = [{'terms': [None] * self.TERM_COUNT} for _ in range(self.MAX_SLOTS)]
            # Fast refresh (no immediate image processing)
            self.refresh_all()
            self._publish_assignments()

    def load_slots(self):
        target_path = self._custom_save_path if self.custom_mode else self._save_path
        try:
            loaded = self._load_slots_from_path(target_path)
            if loaded is not None:
                self.slots = loaded
            else:
                self.slots = self._empty_slots_template()
        except Exception as e:
            print(f"Failed to load slots: {e}")
            self.slots = self._empty_slots_template()

        if self.custom_mode:
            try:
                self._custom_slots = copy.deepcopy(self.slots)
            except Exception:
                pass
        self.refresh_all()
        # Ensure controller sees current assignments
        self._publish_assignments()

    def get_category_options(self):
        """Return a sorted list of available categories gathered from keyword map and current slots."""
        cats = set()
        # Start with keyword map keys
        try:
            for k in (self._keyword_map or {}).keys():
                if k:
                    cats.add(k)
        except Exception:
            pass
        # Add categories found in slot assignments across all terms
        try:
            for s in self.slots:
                try:
                    for t in s.get('terms', []):
                        if t and isinstance(t, dict):
                            c = t.get('category')
                            if c:
                                cats.add(c)
                except Exception:
                    continue
        except Exception:
            pass
        return sorted(list(cats))

    def save_slots(self):
        try:
            target_path = self._custom_save_path if self.custom_mode else self._save_path
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(self.slots, f, indent=2)

            if self.custom_mode:
                try:
                    self._custom_slots = copy.deepcopy(self.slots)
                except Exception:
                    pass
            # Optionally surface assigned slots to controller for runtime use
            try:
                setattr(self.controller, 'assigned_slots', self.slots)
                # Also notify kiosk frame to refresh its display
                try:
                    kf = self.controller.frames.get('KioskFrame')
                    if kf:
                        kf.populate_items()
                except Exception:
                    pass
            except Exception:
                pass
            tk.messagebox.showinfo('Saved', f'Assigned slots saved to {target_path}', parent=self)
        except Exception as e:
            tk.messagebox.showerror('Save Error', f'Failed to save assigned slots: {e}', parent=self)

    def _publish_assignments(self):
        """Publish current assigned slots to the main controller and update kiosk view if present."""
        self._persist_current_term_to_config()
        try:
            setattr(self.controller, 'assigned_slots', self.slots)
            # Also publish which term index is currently selected so kiosk can display correct term
            try:
                setattr(self.controller, 'assigned_term', self.current_term)
            except Exception:
                pass
            
            # Update controller.items to reflect current term's items (for admin screen and kiosk)
            try:
                extracted_items = self._extract_items_from_current_term()
                setattr(self.controller, 'items', extracted_items)
            except Exception:
                pass
        except Exception:
            pass
        try:
            kf = self.controller.frames.get('KioskFrame')
            if kf:
                # Use reset_state to ensure categories and items refresh correctly
                try:
                    kf.reset_state()
                except Exception:
                    kf.populate_items()
        except Exception:
            pass
        try:
            af = self.controller.frames.get('AdminScreen')
            if af:
                # Update admin screen items display
                try:
                    af.populate_items()
                except Exception:
                    pass
        except Exception:
            pass
        # Also update controller.config categories from assigned slots so admin and kiosk configs stay in sync
        try:
            cfg = getattr(self.controller, 'config', {}) or {}
            cats = set()
            for slot in self.slots:
                try:
                    for term in (slot.get('terms') or []):
                        if term and isinstance(term, dict):
                            c = term.get('category')
                            if c:
                                cats.add(c)
                except Exception:
                    pass
            cfg['categories'] = sorted(cats)
            try:
                setattr(self.controller, 'config', cfg)
            except Exception:
                pass
        except Exception:
            pass

    def _extract_items_from_current_term(self):
        """Extract items from current term for display in admin/kiosk."""
        items = []
        try:
            for slot in self.slots:
                if isinstance(slot, dict) and 'terms' in slot:
                    terms = slot.get('terms', [])
                    if len(terms) > self.current_term and terms[self.current_term]:
                        items.append(terms[self.current_term])
        except Exception as e:
            print(f"Error extracting items: {e}")
        return items

    # Optional helper to return slot assignment list
    def get_assigned_slots(self):
        return self.slots
    
    def restore_slot_from_disk(self, slot_idx: int, term_idx: int = 0) -> bool:
        """Restore a specific slot's term from the saved assigned_items.json on disk.

        Returns True if restored, False otherwise.
        """
        try:
            # Try primary save path first
            paths = [self._save_path,
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), self.SAVE_FILENAME),
                     os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), self.SAVE_FILENAME),
                     os.path.join(os.path.expanduser('~'), 'Documents', self.SAVE_FILENAME)]
            for p in paths:
                if not p or not os.path.exists(p):
                    continue
                try:
                    with open(p, 'r', encoding='utf-8-sig') as f:
                        data = json.load(f)
                    if isinstance(data, list) and len(data) >= slot_idx+1:
                        entry = data[slot_idx]
                        if entry and isinstance(entry, dict) and 'terms' in entry and isinstance(entry['terms'], list):
                            # Ensure self.slots has wrapper
                            if slot_idx >= len(self.slots):
                                # expand
                                while len(self.slots) <= slot_idx:
                                    self.slots.append({'terms': [None] * self.TERM_COUNT})
                            # copy the term value
                            src_term = entry['terms']
                            if term_idx < len(src_term):
                                self.slots[slot_idx]['terms'][term_idx] = copy.deepcopy(src_term[term_idx])
                                # refresh and publish
                                self.refresh_slot(slot_idx)
                                self._publish_assignments()
                                return True
                except Exception:
                    continue
        except Exception:
            pass
        return False
