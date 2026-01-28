import tkinter as tk
from tkinter import ttk, filedialog
try:
    from PIL import Image, Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False
import json
import os


class EditSlotDialog(tk.Toplevel):
    def __init__(self, parent, slot_data=None):
        super().__init__(parent)
        self.title("Edit Slot")
        self.transient(parent)
        self.grab_set()
        self.slot_data = slot_data or {}
        self.result = None
        self._create_widgets()
        self._populate()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        lbl_font = ("Helvetica", 11)

        ttk.Label(frame, text="Name:").grid(row=0, column=0, sticky="w")
        self.name_entry = ttk.Entry(frame, width=40)
        self.name_entry.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Category:").grid(row=1, column=0, sticky="w")
        self.category_entry = ttk.Entry(frame, width=40)
        self.category_entry.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Price:").grid(row=2, column=0, sticky="w")
        self.price_entry = ttk.Entry(frame, width=20)
        self.price_entry.grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Quantity:").grid(row=3, column=0, sticky="w")
        self.qty_entry = ttk.Entry(frame, width=20)
        self.qty_entry.grid(row=3, column=1, sticky="w", pady=4)

        ttk.Label(frame, text="Image Path:").grid(row=4, column=0, sticky="w")
        img_frame = ttk.Frame(frame)
        img_frame.grid(row=4, column=1, sticky="ew", pady=4)
        self.image_entry = ttk.Entry(img_frame, width=34)
        self.image_entry.pack(side="left", fill="x", expand=True)
        browse = ttk.Button(img_frame, text="Browse", command=self._browse_image)
        browse.pack(side="left", padx=6)

        ttk.Label(frame, text="Description:").grid(row=5, column=0, sticky="nw")
        self.desc_text = tk.Text(frame, width=40, height=4)
        self.desc_text.grid(row=5, column=1, sticky="ew", pady=4)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8,0))
        save_btn = ttk.Button(btn_frame, text="Save", command=self._on_save)
        save_btn.pack(side="right", padx=4)
        cancel_btn = ttk.Button(btn_frame, text="Cancel", command=self._on_cancel)
        cancel_btn.pack(side="right")

        frame.columnconfigure(1, weight=1)

    def _populate(self):
        if not self.slot_data:
            return
        self.name_entry.insert(0, self.slot_data.get('name', ''))
        self.category_entry.insert(0, self.slot_data.get('category', ''))
        self.price_entry.insert(0, str(self.slot_data.get('price', '')))
        self.qty_entry.insert(0, str(self.slot_data.get('quantity', '')))
        self.image_entry.insert(0, self.slot_data.get('image', ''))
        self.desc_text.insert('1.0', self.slot_data.get('description', ''))

    def _browse_image(self):
        path = filedialog.askopenfilename(title='Select image', filetypes=[('Images','*.png;*.jpg;*.jpeg;*.gif;*.bmp')])
        if path:
            self.image_entry.delete(0, tk.END)
            self.image_entry.insert(0, path)

    def _on_save(self):
        # Basic validation
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

        data = {
            'name': name,
            'category': self.category_entry.get().strip(),
            'price': price,
            'quantity': qty,
            'image': self.image_entry.get().strip(),
            'description': self.desc_text.get('1.0', 'end-1c').strip(),
        }
        self.result = data
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()


class AssignItemsScreen(tk.Frame):
    """Admin screen presenting a 6x10 grid (60 slots) of assignable items."""

    GRID_ROWS = 6
    GRID_COLS = 10
    MAX_SLOTS = GRID_ROWS * GRID_COLS
    SAVE_FILENAME = 'assigned_items.json'

    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f0f4f8")
        self.controller = controller
        self.slots = [None] * self.MAX_SLOTS
        self.slot_frames = []
        self.selected_slots = set()
        self._thumb_cache = {}

        self._data_path = os.path.dirname(getattr(controller, 'config_path', os.path.abspath('.')))
        self._save_path = os.path.join(self._data_path, self.SAVE_FILENAME)

        self._create_widgets()
        self.load_slots()

    def _create_widgets(self):
        header = ttk.Frame(self, padding=12)
        header.pack(fill='x')
        ttk.Label(header, text="Assign Items to Slots", font=("Helvetica", 18, 'bold')).pack(side='left')

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
                edit_btn = ttk.Button(btns, text="Edit", width=6, command=lambda i=idx: self.edit_slot(i))
                edit_btn.pack(side='left', padx=(0,2))
                clear_btn = ttk.Button(btns, text="Clear", width=6, command=lambda i=idx: self.clear_slot(i))
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

    def edit_slot(self, idx):
        current = self.slots[idx] or {}
        dlg = EditSlotDialog(self.master, slot_data=current)
        self.master.wait_window(dlg)
        if getattr(dlg, 'result', None):
            self.slots[idx] = dlg.result
            self.refresh_slot(idx)
            self._publish_assignments()

    def clear_slot(self, idx):
        self.slots[idx] = None
        self.refresh_slot(idx)
        self._publish_assignments()

    def refresh_slot(self, idx):
        r, c = self._slot_to_position(idx)
        slot_ui = self.slot_frames[r][c]
        data = self.slots[idx]
        if data:
            slot_ui['name'].config(text=data.get('name','')[:18])
            slot_ui['details'].config(text=f"{data.get('category','')} | {data.get('quantity',0)} pcs | ${data.get('price',0):.2f}")
        else:
            slot_ui['name'].config(text='Empty')
            slot_ui['details'].config(text='')
        # handle thumbnail if available
        try:
            img_path = data.get('image','') if data else ''
        except Exception:
            img_path = ''
        if img_path and PIL_AVAILABLE and os.path.exists(img_path):
            try:
                img = self._thumb_cache.get(idx)
                if img is None:
                    pil = Image.open(img_path)
                    pil.thumbnail((80,80))
                    img = ImageTk.PhotoImage(pil)
                    self._thumb_cache[idx] = img
                slot_ui['thumb'].config(image=img, text='')
                slot_ui['thumb'].image = img
            except Exception:
                slot_ui['thumb'].config(text='No Image', image='')
        else:
            slot_ui['thumb'].config(text='No Image', image='')

    def refresh_all(self):
        for idx in range(self.MAX_SLOTS):
            self.refresh_slot(idx)

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
        items = getattr(self.controller, 'items', []) or []
        selected_item = None
        for it in items:
            if it.get('name') == name:
                selected_item = it
                break
        if not selected_item:
            tk.messagebox.showwarning('Assign', f'Item "{name}" not found', parent=self)
            return
        for idx in list(self.selected_slots):
            # shallow copy to avoid shared references
            self.slots[idx] = dict(selected_item)
            self.refresh_slot(idx)
        # clear selection
        for idx in list(self.selected_slots):
            self.selected_slots.remove(idx)
            self._update_slot_selection_visual(idx)
        # Publish to controller and update kiosk
        self._publish_assignments()


    def clear_all(self):
        if tk.messagebox.askyesno("Confirm", "Clear all assigned slots?"):
            self.slots = [None] * self.MAX_SLOTS
            self.refresh_all()
            self._publish_assignments()

    def load_slots(self):
        try:
            if os.path.exists(self._save_path):
                with open(self._save_path, 'r') as f:
                    data = json.load(f)
                if isinstance(data, list) and len(data) == self.MAX_SLOTS:
                    self.slots = data
                else:
                    # Migrate older formats or partial data
                    self.slots = (data + [None]*self.MAX_SLOTS)[:self.MAX_SLOTS]
            else:
                # Initialize placeholders
                self.slots = [None] * self.MAX_SLOTS
        except Exception as e:
            print(f"Failed to load slots: {e}")
            self.slots = [None] * self.MAX_SLOTS
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

    # Optional helper to return slot assignment list
    def get_assigned_slots(self):
        return self.slots
