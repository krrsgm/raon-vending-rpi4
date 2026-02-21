import tkinter as tk
from tkinter import ttk, filedialog, messagebox
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False
import json
import os
import io
from esp32_client import pulse_slot, send_command
from fix_paths import get_absolute_path
import copy

def pil_to_photoimage(pil_image):
    """Convert PIL Image to Tkinter PhotoImage using PPM format (no ImageTk needed)"""
    with io.BytesIO() as output:
        pil_image.save(output, format="PPM")
        data = output.getvalue()
    return tk.PhotoImage(data=data)


class PriceStockDialog(tk.Toplevel):
    """Modal dialog to edit price, stock, image, and other item fields.

    If `read_only` is True the fields are disabled and the dialog acts as a viewer.
    """
    def __init__(self, parent, item_data=None, read_only=False):
        """
        Args:
            parent: parent window
            item_data: dict with item details
        """
        super().__init__(parent)
        self.item_data = item_data or {}
        self.result = None
        self.read_only = bool(read_only)
        
        self.title("Edit Item Details")
        self.transient(parent)
        self.grab_set()
        self._create_widgets()
    
    def _create_widgets(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        
        # Title
        ttk.Label(frame, text="Edit Item Details", font=("Helvetica", 12, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0,12))
        
        # Item name (display only)
        item_name = self.item_data.get('name', 'Unknown')
        ttk.Label(frame, text=f"Item: {item_name}", font=("Helvetica", 10)).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0,8))
        
        # Price
        ttk.Label(frame, text="Price ($):").grid(row=2, column=0, sticky="w", pady=4)
        self.price_entry = ttk.Entry(frame, width=20)
        self.price_entry.grid(row=2, column=1, columnspan=2, sticky="ew", pady=4)
        self.price_entry.insert(0, str(self.item_data.get('price', 0.0)))
        
        # Quantity/Stock
        ttk.Label(frame, text="Stock Quantity:").grid(row=3, column=0, sticky="w", pady=4)
        self.qty_entry = ttk.Entry(frame, width=20)
        self.qty_entry.grid(row=3, column=1, columnspan=2, sticky="ew", pady=4)
        self.qty_entry.insert(0, str(self.item_data.get('quantity', 0)))
        
        # Category
        ttk.Label(frame, text="Category:").grid(row=4, column=0, sticky="w", pady=4)
        self.category_entry = ttk.Entry(frame, width=20)
        self.category_entry.grid(row=4, column=1, columnspan=2, sticky="ew", pady=4)
        self.category_entry.insert(0, self.item_data.get('category', ''))
        
        # Description
        ttk.Label(frame, text="Description:").grid(row=5, column=0, sticky="nw", pady=4)
        self.desc_text = tk.Text(frame, width=40, height=3)
        self.desc_text.grid(row=5, column=1, columnspan=2, sticky="ew", pady=4)
        self.desc_text.insert('1.0', self.item_data.get('description', ''))
        
        # Image path
        ttk.Label(frame, text="Image:").grid(row=6, column=0, sticky="w", pady=4)
        self.image_entry = ttk.Entry(frame, width=25)
        self.image_entry.grid(row=6, column=1, sticky="ew", pady=4)
        self.image_entry.insert(0, self.item_data.get('image', ''))
        
        browse_btn = ttk.Button(frame, text="Browse", command=self._browse_image)
        browse_btn.grid(row=6, column=2, padx=(4, 0), pady=4)
        # Keep a reference so we can disable it when showing the dialog in restricted modes
        self.browse_btn = browse_btn
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=3, sticky="e", pady=(12,0))
        
        if self.read_only:
            close_btn = ttk.Button(btn_frame, text="Close", command=self._on_cancel)
            close_btn.pack(side="right")
        else:
            save_btn = ttk.Button(btn_frame, text="Save", command=self._on_save)
            save_btn.pack(side="right", padx=4)
            
            cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._on_cancel)
            cancel_btn.pack(side="right")
        
        frame.columnconfigure(1, weight=1)
    
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
            self.category_entry.state(['disabled'])
        except Exception:
            try:
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
        
        # Return updated item data
        self.result = dict(self.item_data)
        self.result['price'] = price
        self.result['quantity'] = qty
        self.result['category'] = self.category_entry.get().strip()
        self.result['description'] = self.desc_text.get('1.0', 'end-1c').strip()
        self.result['image'] = self.image_entry.get().strip()
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
    
    # If it's already a relative path, return as-is
    if not os.path.isabs(absolute_path):
        return absolute_path
    
    try:
        # Get project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Try to make it relative to project root
        try:
            rel_path = os.path.relpath(absolute_path, project_root)
            # If it doesn't go up too many directories, use it
            if not rel_path.startswith('..'):
                return rel_path
        except ValueError:
            # Different drives on Windows
            pass
        
        # Try to extract just the filename and put it in images directory
        filename = os.path.basename(absolute_path)
        return f"./images/{filename}"
    except Exception as e:
        print(f"Error converting path {absolute_path}: {e}")
        return absolute_path


class EditSlotDialog(tk.Toplevel):
    """Modal dialog to select from 3 term options or customize a slot item."""
    def __init__(self, parent, slot_idx=0, term_options=None, current_term_idx=0):
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
        
        self.title(f"Assign Item to Slot {slot_idx+1}")
        self.transient(parent)
        self.grab_set()
        self._create_widgets()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        # Title
        ttk.Label(frame, text=f"Slot {self.slot_idx+1} - Choose an item:", 
                  font=("Helvetica", 12, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,12))

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
        ttk.Label(frame, text="Select:").grid(row=1, column=0, sticky="w", pady=4)
        # Guard default selection index
        default_value = options_list[self.current_term_idx] if 0 <= self.current_term_idx < len(options_list) else options_list[0]
        self.select_var = tk.StringVar(value=default_value)
        self.select_combo = ttk.Combobox(frame, values=options_list, width=50, textvariable=self.select_var, state='readonly')
        self.select_combo.grid(row=1, column=1, sticky="ew", pady=4)
        
        # Preview frame (shows item details when term selected)
        preview_frame = ttk.LabelFrame(frame, text="Preview", padding=8)
        preview_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=8)
        
        self.preview_text = tk.Text(preview_frame, width=60, height=6, state='disabled')
        self.preview_text.pack(fill='both', expand=True)
        
        # Update preview when selection changes
        self.select_combo.bind('<<ComboboxSelected>>', self._update_preview)
        self._update_preview()
        
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8,0))
        
        select_btn = ttk.Button(btn_frame, text="Select", command=self._on_select)
        select_btn.pack(side="right", padx=4)
        
        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._on_cancel)
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
Price: ${item.get('price', 0):.2f}
Quantity: {item.get('quantity', 1)}
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
        CustomizeDialog(self, parent_result_callback=self._on_customize_done)

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
    def __init__(self, parent, parent_result_callback=None):
        super().__init__(parent)
        self.title("Customize Item")
        self.transient(parent)
        self.grab_set()
        self.result = None
        self.parent_result_callback = parent_result_callback
        self._create_widgets()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        lbl_font = ("Helvetica", 10)

        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky="w", pady=4)
        self.name_entry = ttk.Entry(frame, width=40)
        self.name_entry.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Category:").grid(row=1, column=0, sticky="w", pady=4)
        self.category_entry = ttk.Entry(frame, width=40)
        self.category_entry.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Price:").grid(row=2, column=0, sticky="w", pady=4)
        self.price_entry = ttk.Entry(frame, width=20)
        self.price_entry.grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Quantity:").grid(row=3, column=0, sticky="w", pady=4)
        self.qty_entry = ttk.Entry(frame, width=20)
        self.qty_entry.grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Image Path:").grid(row=4, column=0, sticky="w", pady=4)
        img_frame = ttk.Frame(frame)
        img_frame.grid(row=4, column=1, sticky="ew", pady=4)
        self.image_entry = ttk.Entry(img_frame, width=34)
        self.image_entry.pack(side="left", fill="x", expand=True)
        browse = ttk.Button(img_frame, text="Browse", command=self._browse_image)
        browse.pack(side="left", padx=6)

        ttk.Label(frame, text="Description:").grid(row=5, column=0, sticky="nw", pady=4)
        self.desc_text = tk.Text(frame, width=40, height=4)
        self.desc_text.grid(row=5, column=1, sticky="ew", pady=4)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8,0))
        save_btn = ttk.Button(btn_frame, text="Save", command=self._on_save)
        save_btn.pack(side="right", padx=4)
        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._on_cancel)
        cancel_btn.pack(side="right")

        frame.columnconfigure(1, weight=1)

    def _browse_image(self):
        path = filedialog.askopenfilename(title='Select image', filetypes=[('Images','*.png;*.jpg;*.jpeg;*.gif;*.bmp')])
        if path:
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

        image_path = self.image_entry.get().strip()
        if image_path:
            image_path = convert_image_path_to_relative(image_path)

        data = {
            'code': '',
            'name': name,
            'category': self.category_entry.get().strip(),
            'price': price,
            'quantity': qty,
            'image': image_path,
            'description': self.desc_text.get('1.0', 'end-1c').strip(),
        }
        if self.parent_result_callback:
            self.parent_result_callback(data)
        self.destroy()

    def _on_cancel(self):
        if self.parent_result_callback:
            self.parent_result_callback(None)
        self.destroy()


class AssignItemsScreen(tk.Frame):
    """Admin screen presenting an 8x8 grid (64 slots) of assignable items."""

    GRID_ROWS = 8
    GRID_COLS = 8
    MAX_SLOTS = GRID_ROWS * GRID_COLS
    SAVE_FILENAME = 'assigned_items.json'
    TERM_COUNT = 3

    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f0f4f8")
        self.controller = controller
        # Each slot contains a dict with key 'terms' -> list of term-specific assignments
        # e.g. {'terms': [term1_dict_or_none, term2_dict_or_none, term3_dict_or_none]}
        self.slots = [{'terms': [None] * self.TERM_COUNT} for _ in range(self.MAX_SLOTS)]
        self.slot_frames = []
        self.selected_slots = set()
        self._thumb_cache = {}
        self.current_term = 0  # 0-based term index
        self.custom_mode = False  # Toggle between Preset and Custom modes
        # Snapshot of presets taken when entering custom mode; used to restore originals
        self._presets_snapshot = None
        
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

        self._create_widgets()
        self.load_slots()

    def _create_widgets(self):
        header = ttk.Frame(self, padding=12)
        header.pack(fill='x')
        
        left_section = ttk.Frame(header)
        left_section.pack(side='left')
        ttk.Label(left_section, text="Assign Items to Slots", font=("Helvetica", 18, 'bold')).pack(side='left')
        
        # Term selector dropdown
        ttk.Label(left_section, text="Term:", font=("Helvetica", 11)).pack(side='left', padx=(20, 4))
        self.term_var = tk.StringVar(value='Term 1')
        term_combo = ttk.Combobox(left_section, textvariable=self.term_var, values=[f'Term {i+1}' for i in range(self.TERM_COUNT)], state='readonly', width=10)
        term_combo.pack(side='left', padx=(0, 12))
        term_combo.bind('<<ComboboxSelected>>', lambda e: self._on_term_change())
        
        # Mode indicator and Custom toggle
        ttk.Label(left_section, text="Mode:", font=("Helvetica", 11)).pack(side='left', padx=(20, 4))
        self.mode_var = tk.StringVar(value='Preset')
        self.mode_label = ttk.Label(left_section, text='Preset', font=("Helvetica", 11, 'bold'), foreground='green')
        self.mode_label.pack(side='left', padx=(0, 8))
        
        custom_btn = ttk.Button(left_section, text='Switch to Custom', command=self._toggle_custom_mode, width=18)
        custom_btn.pack(side='left', padx=(0, 12))

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side='right')
        ttk.Button(btn_frame, text="Load", command=self.load_slots).pack(side='left', padx=4)
        ttk.Button(btn_frame, text="Save", command=self.save_slots).pack(side='left', padx=4)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_all).pack(side='left', padx=4)

        # Scrollable area for grid (vertical + horizontal support)
        canvas_container = ttk.Frame(self)
        canvas_container.pack(fill='both', expand=True, padx=10, pady=8)

        self.canvas = tk.Canvas(canvas_container, bg="#f0f4f8", highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_container, orient='vertical', command=self.canvas.yview)
        hsb = ttk.Scrollbar(canvas_container, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')

        # Add a small slider control (0..100) for horizontal panning as requested
        self.hslider = tk.Scale(canvas_container, from_=0, to=100, orient='horizontal', showvalue=0,
                                length=300, command=lambda v: self.canvas.xview_moveto(float(v)/100.0))
        # Place slider under the canvas and above the horizontal scrollbar
        self.hslider.pack(side='bottom', fill='x', pady=(4,0))

        self.grid_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0,0), window=self.grid_frame, anchor='nw')

        # Update scrollregion and synchronize slider whenever the grid changes size
        def _on_grid_config(e):
            try:
                self.canvas.configure(scrollregion=self.canvas.bbox('all'))
                # If grid wider than canvas, enable slider range and update its position
                canvas_width = self.canvas.winfo_width() or 1
                grid_width = self.grid_frame.winfo_reqwidth() or 1
                max_offset = max(0, grid_width - canvas_width)
                if max_offset > 0:
                    # update slider position based on current view
                    left, right = self.canvas.xview()
                    self.hslider.set(int(left * 100))
                    self.hslider.configure(state='normal')
                else:
                    self.hslider.set(0)
                    self.hslider.configure(state='disabled')
            except Exception:
                pass

        self.grid_frame.bind('<Configure>', _on_grid_config)

        # Ensure canvas window expands/shrinks with container
        def _on_canvas_config(e):
            try:
                # keep window width at least canvas width so grid packs correctly
                self.canvas.itemconfig(self.canvas_window, width=self.canvas.winfo_width())
                # Sync slider position when user scrolls via scrollbar or programatically
                left, right = self.canvas.xview()
                self.hslider.set(int(left * 100))
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
                frm = ttk.Frame(self.grid_frame, relief='ridge', padding=4, width=150, height=140)
                frm.grid(row=r, column=c, padx=4, pady=4, sticky='nsew')
                frm.grid_propagate(False)  # Fix size to allow proper layout
                
                # Slot header with selection marker
                slot_hdr = ttk.Frame(frm)
                slot_hdr.pack(fill='x', pady=(0,2))
                slot_lbl = ttk.Label(slot_hdr, text=f"Slot {idx+1}", font=("Helvetica", 9, 'bold'))
                slot_lbl.pack(side='left', fill='x', expand=True)
                sel_marker = ttk.Label(slot_hdr, text=" ", width=2, anchor='center')
                sel_marker.pack(side='right')

                # Content area (compact layout)
                content = ttk.Frame(frm)
                content.pack(fill='both', expand=True, pady=(2,2))

                # Thumbnail (small)
                thumb_lbl = tk.Label(content, text='', width=10, height=4, anchor='center', background='#e8e8e8', relief='sunken', font=("Helvetica", 8))
                thumb_lbl.pack(fill='both', expand=False, pady=(0,2))

                # Item info (name and details)
                info = ttk.Frame(content)
                info.pack(fill='both', expand=True, pady=(0,2))
                name_lbl = ttk.Label(info, text="Empty", font=("Helvetica", 8, 'bold'), wraplength=120, justify='left')
                name_lbl.pack(anchor='nw', fill='x')
                details_lbl = ttk.Label(info, text="", font=("Helvetica", 7), wraplength=120, justify='left')
                details_lbl.pack(anchor='nw', fill='both', expand=True)

                # Buttons (compact)
                btns = ttk.Frame(frm)
                btns.pack(fill='x', pady=(2,0))
                edit_btn = ttk.Button(btns, text="Edit", width=5, command=lambda i=idx: self.edit_slot(i))
                edit_btn.pack(side='left', padx=(0,2))
                test_btn = ttk.Button(btns, text="Test", width=5, command=lambda i=idx: self.test_motor(i))
                test_btn.pack(side='left', padx=(0,2))
                clear_btn = ttk.Button(btns, text="Clear", width=5, command=lambda i=idx: self.clear_slot(i))
                clear_btn.pack(side='left')

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

    def _on_term_change(self):
        txt = self.term_var.get() or 'Term 1'
        try:
            # Expect format 'Term N'
            n = int(txt.split()[-1])
            self.current_term = max(0, min(self.TERM_COUNT-1, n-1))
        except Exception:
            self.current_term = 0
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

    def _toggle_custom_mode(self):
        """Toggle between Preset and Custom mode."""
        # Toggle mode
        entering = not self.custom_mode
        self.custom_mode = entering
        if self.custom_mode:
            # Take a deep snapshot of the original presets so they can be restored later.
            # Prefer the last-saved assigned_items.json on disk (so accidental in-memory
            # edits/clears made while in Preset mode can be reverted). Fall back to the
            # current in-memory `self.slots` if no save file exists or migration fails.
            try:
                if os.path.exists(self._save_path):
                    try:
                        with open(self._save_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        # Migrate various persisted formats into per-slot 'terms' wrapper
                        if isinstance(data, list) and len(data) == self.MAX_SLOTS:
                            migrated = []
                            for entry in data:
                                if entry is None:
                                    migrated.append({'terms': [None] * self.TERM_COUNT})
                                    continue
                                if isinstance(entry, dict) and 'terms' in entry and isinstance(entry['terms'], list):
                                    terms = (entry['terms'] + [None]*self.TERM_COUNT)[:self.TERM_COUNT]
                                    migrated.append({'terms': terms})
                                    continue
                                if isinstance(entry, dict):
                                    migrated.append({'terms': [entry] + [None]*(self.TERM_COUNT-1)})
                                    continue
                                migrated.append({'terms': [None] * self.TERM_COUNT})
                            self._presets_snapshot = copy.deepcopy(migrated)
                        else:
                            # Unexpected on-disk format; fallback to current memory
                            self._presets_snapshot = copy.deepcopy(self.slots)
                    except Exception:
                        self._presets_snapshot = copy.deepcopy(self.slots)
                else:
                    self._presets_snapshot = copy.deepcopy(self.slots)
            except Exception:
                self._presets_snapshot = None
            self.mode_label.config(text='Custom', foreground='red')
        else:
            # Leaving custom mode: restore original presets (discard temporary edits)
            try:
                if self._presets_snapshot is not None:
                    self.slots = copy.deepcopy(self._presets_snapshot)
                    self._presets_snapshot = None
                    self.refresh_all()
            except Exception:
                pass
            self.mode_label.config(text='Preset', foreground='green')

    def auto_assign_current_term(self):
        """Auto-populate all 64 slots with products from current term in assigned_items.json."""
        term_idx = self.current_term
        
        # Confirm action
        if not tk.messagebox.askyesno("Auto-assign Term", 
            f"This will populate all 64 slots with products from Term {term_idx+1}.\nContinue?", parent=self):
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
            f"All 64 slots populated with Term {term_idx+1} products!", parent=self)

    def edit_slot(self, idx):
        # If this slot appears empty in-memory, try reloading from disk to get latest persisted assignments
        slot_entry = self.slots[idx] if idx < len(self.slots) else None
        if (not slot_entry) or (isinstance(slot_entry, dict) and all(t is None for t in slot_entry.get('terms', []))):
            try:
                print(f"[DEBUG] edit_slot({idx+1}) _save_path={self._save_path} exists={os.path.exists(self._save_path)}")
                if os.path.exists(self._save_path):
                    try:
                        with open(self._save_path, 'r', encoding='utf-8') as _f:
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
                        with open(p, 'r', encoding='utf-8') as _f:
                            _data = json.load(_f)
                        if isinstance(_data, list) and len(_data) == self.MAX_SLOTS:
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
        
        # Get the item for the current term
        current_item = None
        try:
            slot = self.slots[idx]
            if slot and 'terms' in slot and len(slot['terms']) > self.current_term:
                current_item = slot['terms'][self.current_term]
        except Exception:
            pass
        
        # In custom mode, open full editor; in preset, open price/stock editor
        if self.custom_mode:
            # Custom mode: open full EditSlotDialog for item selection/creation
            term_options = self.slots[idx].get('terms') or [None]*self.TERM_COUNT
            dlg = EditSlotDialog(self.master, slot_idx=idx, term_options=term_options, current_term_idx=self.current_term)
            self.master.wait_window(dlg)
            if getattr(dlg, 'result', None):
                self.slots[idx]['terms'][self.current_term] = dlg.result
                self.refresh_slot(idx)
                self._publish_assignments()
            return
        
        # Preset mode: only allow price/stock/image editing
        if not current_item:
            tk.messagebox.showwarning("Empty Slot", f"Slot {idx+1} is empty for Term {self.current_term+1}.\nUse Custom mode to assign an item.", parent=self)
            return

        # Auto-fill description if it's just a price or empty
        item_to_edit = dict(current_item)
        current_desc = item_to_edit.get('description', '').strip()
        if not current_desc or current_desc.startswith('P') and current_desc[1:].isdigit():
            # Description is empty or just a price, auto-generate one
            auto_desc = self._generate_description_for_item(
                item_to_edit.get('name', ''),
                item_to_edit.get('price', 0)
            )
            item_to_edit['description'] = auto_desc

        # Open Price/Stock viewer but allow editing of price, quantity and description
        dlg = PriceStockDialog(self.master, item_data=item_to_edit, read_only=False)
        # Restrict some fields (keep price/qty/description editable; disable category/image)
        try:
            dlg._set_readonly()
        except Exception:
            pass
        self.master.wait_window(dlg)
        # If user saved changes, merge editable fields back into the slot and publish
        try:
            if getattr(dlg, 'result', None):
                updated = dlg.result
                # update only editable fields to avoid changing name/code unintentionally
                cur = self.slots[idx]['terms'][self.current_term] or {}
                cur = dict(cur)
                for k in ('price', 'quantity', 'category', 'description', 'image'):
                    if k in updated:
                        cur[k] = updated[k]
                self.slots[idx]['terms'][self.current_term] = cur
                self.refresh_slot(idx)
                self._publish_assignments()
        except Exception:
            pass

    def _check_esp32_connection(self, esp32_host):
        """Check if ESP32 is reachable by sending a STATUS command."""
        try:
            result = send_command(esp32_host, "STATUS", timeout=1.0)
            return True, result
        except Exception as e:
            return False, str(e)

    def test_motor(self, idx):
        """Test the motor for the given slot by pulsing it."""
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
            
            # Pulse the motor for 800ms with longer timeout for serial
            print(f"[TEST MOTOR] Pulsing slot {slot_num}...")
            # Ensure machine supports only slots 1-48
            if slot_num < 1 or slot_num > 48:
                messagebox.showerror(
                    "Motor Test - Unsupported Slot",
                    f"Slot {slot_num} is out of range. This machine supports slots 1-48 only.",
                    parent=self
                )
                print(f"[TEST MOTOR] ERROR: Slot {slot_num} out of supported range (1-48)")
                return

            # For supported slots (1-48) use ESP32
            result = pulse_slot(esp32_host, slot_num, 800, timeout=3.0)
            
            # Validate response - should contain "OK"
            if result and "OK" in result.upper():
                messagebox.showinfo(
                    "✓ Motor Test Success", 
                    f"Slot {slot_num} motor pulsed for 800ms\n\nESP32 Response: {result}",
                    parent=self
                )
                print(f"[TEST MOTOR] SUCCESS: Slot {slot_num} pulsed, response: {result}")
            else:
                messagebox.showerror(
                    "✗ Motor Test Failed", 
                    f"Slot {slot_num} did not receive proper confirmation from ESP32\n\nResponse: {result if result else 'No response'}\n\nMake sure:\n- RXTX cable is connected between ESP32 and Raspberry Pi\n- ESP32 firmware is loaded and running\n- Slot number is valid (1-64)",
                    parent=self
                )
                print(f"[TEST MOTOR] FAILED: No valid response from ESP32 for slot {slot_num}. Got: {result}")
                
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
            return f"Price: ₱{item_price:.2f}"
        
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
        return f"{base_desc} - ₱{item_price:.2f}"

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
            slot_ui['details'].config(text=f"{category_text} | {data.get('quantity',0)} pcs | ${data.get('price',0):.2f}")
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
        if img_path and PIL_AVAILABLE and os.path.exists(img_path):
            img = self._thumb_cache.get(idx)
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
                    if img_path and PIL_AVAILABLE and os.path.exists(img_path):
                        if not self._thumb_cache.get(i):
                            try:
                                pil = Image.open(img_path)
                                pil.thumbnail((80,80))
                                img = pil_to_photoimage(pil)
                                self._thumb_cache[i] = img
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

            dlg = CustomizeDialog(self.master, parent_result_callback=_cb)
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
        try:
            if os.path.exists(self._save_path):
                with open(self._save_path, 'r') as f:
                    data = json.load(f)
                # Support multiple persisted formats and migrate to per-slot 'terms' wrapper
                if isinstance(data, list) and len(data) == self.MAX_SLOTS:
                    migrated = []
                    for entry in data:
                        if entry is None:
                            migrated.append({'terms': [None] * self.TERM_COUNT})
                            continue
                        # If entry already has 'terms' key assume new format
                        if isinstance(entry, dict) and 'terms' in entry and isinstance(entry['terms'], list):
                            terms = (entry['terms'] + [None]*self.TERM_COUNT)[:self.TERM_COUNT]
                            migrated.append({'terms': terms})
                            continue
                        # If entry is a plain dict for old single-term format, put it into term0
                        if isinstance(entry, dict):
                            migrated.append({'terms': [entry] + [None]*(self.TERM_COUNT-1)})
                            continue
                        # Fallback
                        migrated.append({'terms': [None] * self.TERM_COUNT})
                    self.slots = migrated
                else:
                    # Migrate or initialize default
                    self.slots = [{'terms': [None] * self.TERM_COUNT} for _ in range(self.MAX_SLOTS)]
            else:
                # Initialize placeholders
                self.slots = [{'terms': [None] * self.TERM_COUNT} for _ in range(self.MAX_SLOTS)]
        except Exception as e:
            print(f"Failed to load slots: {e}")
            self.slots = [{'terms': [None] * self.TERM_COUNT} for _ in range(self.MAX_SLOTS)]
        self.refresh_all()
        # Ensure controller sees current assignments
        self._publish_assignments()

    def save_slots(self):
        try:
            with open(self._save_path, 'w') as f:
                json.dump(self.slots, f, indent=2)
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
            tk.messagebox.showinfo('Saved', f'Assigned slots saved to {self._save_path}', parent=self)
        except Exception as e:
            tk.messagebox.showerror('Save Error', f'Failed to save assigned slots: {e}', parent=self)

    def _publish_assignments(self):
        """Publish current assigned slots to the main controller and update kiosk view if present."""
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
                    with open(p, 'r', encoding='utf-8') as f:
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
