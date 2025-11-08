import tkinter as tk
from tkinter import ttk, filedialog
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

        # Scrollable area for grid
        canvas_container = ttk.Frame(self)
        canvas_container.pack(fill='both', expand=True, padx=10, pady=8)

        self.canvas = tk.Canvas(canvas_container, bg="#f0f4f8", highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_container, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.grid_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0,0), window=self.grid_frame, anchor='nw')
        self.grid_frame.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.pack(fill='both', expand=True, side='left')

        # Build grid placeholders
        for r in range(self.GRID_ROWS):
            row_frames = []
            for c in range(self.GRID_COLS):
                idx = r * self.GRID_COLS + c
                frm = ttk.Frame(self.grid_frame, relief='ridge', padding=6)
                frm.grid(row=r, column=c, padx=6, pady=6, sticky='nsew')
                # Slot label
                slot_lbl = ttk.Label(frm, text=f"Slot {idx+1}", font=("Helvetica", 10, 'bold'))
                slot_lbl.pack(anchor='w')
                name_lbl = ttk.Label(frm, text="Empty", width=18)
                name_lbl.pack(anchor='w', pady=(4,0))
                details_lbl = ttk.Label(frm, text="", font=("Helvetica", 9))
                details_lbl.pack(anchor='w')
                btns = ttk.Frame(frm)
                btns.pack(anchor='e', pady=(6,0))
                edit_btn = ttk.Button(btns, text="Edit", command=lambda i=idx: self.edit_slot(i))
                edit_btn.pack(side='left')
                clear_btn = ttk.Button(btns, text="Clear", command=lambda i=idx: self.clear_slot(i))
                clear_btn.pack(side='left', padx=(6,0))

                row_frames.append({'frame':frm, 'name':name_lbl, 'details':details_lbl})
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

    def clear_slot(self, idx):
        self.slots[idx] = None
        self.refresh_slot(idx)

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

    def refresh_all(self):
        for idx in range(self.MAX_SLOTS):
            self.refresh_slot(idx)


    def clear_all(self):
        if tk.messagebox.askyesno("Confirm", "Clear all assigned slots?"):
            self.slots = [None] * self.MAX_SLOTS
            self.refresh_all()

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

    def save_slots(self):
        try:
            with open(self._save_path, 'w') as f:
                json.dump(self.slots, f, indent=2)
            # Optionally surface assigned slots to controller for runtime use
            try:
                setattr(self.controller, 'assigned_slots', self.slots)
            except Exception:
                pass
            tk.messagebox.showinfo('Saved', f'Assigned slots saved to {self._save_path}', parent=self)
        except Exception as e:
            tk.messagebox.showerror('Save Error', f'Failed to save assigned slots: {e}', parent=self)

    # Optional helper to return slot assignment list
    def get_assigned_slots(self):
        return self.slots
