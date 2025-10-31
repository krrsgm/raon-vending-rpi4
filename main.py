import tkinter as tk
from kiosk_app import KioskFrame
from selection_screen import SelectionScreen
import json
from admin_screen import AdminScreen
from item_screen import ItemScreen
from cart_screen import CartScreen
from fix_paths import get_absolute_path
import subprocess
import platform
import os


class MainApp(tk.Tk):
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.cart = []

        # Start in windowed mode for SelectionScreen
        self.is_fullscreen = False
        # Set window title
        self.title("RAON Vending Machine")
        
        # Bind Escape globally so it works in all frames
        self.bind_all("<Escape>", self.handle_escape)
        
        # Special handling for Raspberry Pi
        if platform.system() == "Linux":
            # Ensure window can go fullscreen on Raspberry Pi
            self.attributes('-zoomed', '1')
            # Remove window decorations on Pi
            self.attributes('-type', 'splash')
        self.items_file_path = get_absolute_path("item_list.json")
        self.config_path = get_absolute_path("config.json")
        self.items = self.load_items_from_json(self.items_file_path)
        self.config = self.load_config_from_json(self.config_path)
        self.currency_symbol = self.config.get("currency_symbol", "$")
        self.title("Vending Machine UI")
        # Apply fullscreen and rotation according to config
        always_fs = bool(self.config.get('always_fullscreen', True))
        allow_admin_deco = bool(self.config.get('allow_decorations_for_admin', False))
        rotate_disp = str(self.config.get('rotate_display', 'right'))

        self._kiosk_config = {
            'always_fullscreen': always_fs,
            'allow_admin_decorations': allow_admin_deco,
            'rotate_display': rotate_disp
        }

        # Do not force fullscreen here; per-page logic in show_frame will
        # apply fullscreen/decoration behavior so the SelectionScreen can
        # show window controls (minimize/maximize) on startup.

        # Attempt display rotation if configured
        def apply_rotation(direction):
            valid = {'normal': 'normal', 'right': 'right', 'left': 'left', 'inverted': 'inverted'}
            d = valid.get(direction, None)
            if not d:
                return
            try:
                if platform.system() == "Linux" and os.getenv("DISPLAY"):
                    # Use xrandr to rotate screen (non-persistent)
                    subprocess.run(["xrandr", "-o", d], check=False)
            except Exception as e:
                print(f"Rotation failed: {e}")

        if rotate_disp:
            # schedule shortly after startup so X is ready
            self.after(300, lambda: apply_rotation(rotate_disp))

        # Bind keys on the root window so they work regardless of focus.
        # F11 is kept as a no-op toggle that re-applies fullscreen state.
        try:
            self.bind("<F11>", self.toggle_fullscreen)
        except Exception:
            pass

        # Bind Escape globally so it works even when the window is undecorated
        # or when focus shifts to child widgets or modal dialogs.
        try:
            self.bind_all("<Escape>", self.handle_escape)
        except Exception:
            pass
        # Attempt to rotate the display 90 degrees to the right (if running under X on Linux).
        # This uses `xrandr -o right` and will only run when a DISPLAY is available.
        try:
            if platform.system() == "Linux" and os.getenv("DISPLAY"):
                # Run after a short delay so X is ready
                self.after(200, lambda: subprocess.run(["xrandr", "-o", "right"]))
        except Exception as e:
            print(f"Display rotation request failed: {e}")

        # The container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (SelectionScreen, KioskFrame, AdminScreen, ItemScreen, CartScreen):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            # put all of the pages in the same location;
            # the one on the top of the stacking order
            # will be the one that is visible.
            frame.grid(row=0, column=0, sticky="nsew")

        self.active_frame_name = None
        self.show_frame("SelectionScreen")

    def load_items_from_json(self, file_path):
        """Loads item data from a JSON file."""
        try:
            with open(file_path, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            print(
                f"Warning: {file_path} not found. Generating a new one with default items."
            )
            default_items = []
            with open(file_path, "w") as file:
                json.dump(default_items, file, indent=4)
            return default_items
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}.")
            return []

    def load_config_from_json(self, file_path):
        """Loads item data from a JSON file."""
        try:
            with open(file_path, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            print(
                f"Warning: {file_path} not found. Generating a new one with default items."
            )
            default_config = {"currency_symbol": "$"}
            with open(file_path, "w") as file:
                json.dump(default_config, file, indent=4)
            return default_config
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}.")
            return []

    def save_items_to_json(self):
        """Saves the current item list to the JSON file."""
        with open(self.items_file_path, "w") as file:
            json.dump(self.items, file, indent=4)

    def toggle_fullscreen(self, event=None):
        """Toggles fullscreen mode for the SelectionScreen."""
        if self.active_frame_name == "SelectionScreen":
            self.is_fullscreen = not self.is_fullscreen
            if self.is_fullscreen:
                self.attributes("-fullscreen", True)
                self.overrideredirect(True)
            else:
                self.attributes("-fullscreen", False)
                self.overrideredirect(False)
                self.state('normal')
                # Set a reasonable default size
                width = min(1024, self.winfo_screenwidth() - 100)
                height = min(768, self.winfo_screenheight() - 100)
                x = (self.winfo_screenwidth() - width) // 2
                y = (self.winfo_screenheight() - height) // 2
                self.geometry(f"{width}x{height}+{x}+{y}")

    def show_frame(self, page_name):
        """Show a frame for the given page name"""
        frame = self.frames[page_name]
        self.active_frame_name = page_name

        # Handle window state differently for Linux/Raspberry Pi
        is_linux = platform.system() == "Linux"

        if page_name == "SelectionScreen":
            try:
                if is_linux:
                    # On Pi: use normal window with decorations
                    self.attributes('-type', 'normal')
                    self.attributes('-zoomed', '0')
                    self.state('normal')
                else:
                    # On Windows: standard window control
                    self.overrideredirect(False)
                    self.attributes("-fullscreen", False)
                
                # Set a reasonable default size
                width = min(1024, self.winfo_screenwidth() - 100)
                height = min(768, self.winfo_screenheight() - 100)
                x = (self.winfo_screenwidth() - width) // 2
                y = (self.winfo_screenheight() - height) // 2
                self.geometry(f"{width}x{height}+{x}+{y}")
            except Exception as e:
                print(f"Error setting window state: {e}")
        else:
            try:
                if is_linux:
                    # On Pi: use splash window type and zoomed state
                    self.attributes('-type', 'splash')
                    self.attributes('-zoomed', '1')
                    # Force fullscreen size
                    self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
                else:
                    # On Windows: use standard fullscreen
                    self.attributes("-fullscreen", True)
                    self.overrideredirect(True)
                    self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
            except Exception as e:
                print(f"Error setting fullscreen: {e}")

        # Raise the frame and ensure it has focus
        frame.tkraise()
        self.update_idletasks()  # Process any pending window manager tasks
        
        # Multiple focus attempts for reliable key handling
        for focus_method in [self.focus_force, self.focus_set, frame.focus_set]:
            try:
                focus_method()
                break
            except Exception:
                continue

        frame.event_generate("<<ShowFrame>>")
        frame.tkraise()
        # Force focus back to the main window so global bindings (Escape) are received
        try:
            self.focus_force()
        except Exception:
            try:
                self.focus_set()
            except Exception:
                pass

    def set_kiosk_mode(self, enable: bool):
        """Enable or disable kiosk mode: fullscreen and no window decorations.

        When enabled the window becomes fullscreen and window manager
        decorations (title bar) are removed. When disabled, decorations
        are restored and fullscreen is disabled.
        """
        if enable:
            self.is_fullscreen = True
            # Try to remove window decorations first, then set fullscreen
            try:
                self.overrideredirect(True)
            except Exception:
                pass
            try:
                self.attributes("-fullscreen", True)
            except Exception:
                pass
            # Ensure geometry covers the entire screen
            try:
                self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
            except Exception:
                pass
        else:
            # Restore decorations and exit fullscreen
            try:
                self.attributes("-fullscreen", False)
            except Exception:
                pass
            try:
                self.overrideredirect(False)
            except Exception:
                pass
            # Optionally set a sensible windowed geometry
            try:
                screen_width = self.winfo_screenwidth()
                screen_height = self.winfo_screenheight()
                width = screen_width // 2
                height = screen_height
                x = screen_width // 2
                self.geometry(f"{width}x{height}+{x}+0")
            except Exception:
                pass

    def show_kiosk(self):
        """Show the kiosk interface and reset its state."""
        self.frames["KioskFrame"].reset_state()
        # First update the frame name
        self.active_frame_name = "KioskFrame"
        # Then show the frame (which will make it fullscreen)
        self.show_frame("KioskFrame")
        # Force focus back to main window for key bindings
        self.focus_force()

    def show_item(self, item_data):
        """Passes item data to the ItemScreen and displays it."""
        self.frames["ItemScreen"].set_item(item_data)
        self.show_frame("ItemScreen")

    def show_cart(self):
        """Passes cart data to the CartScreen and displays it."""
        self.frames["CartScreen"].update_cart(self.cart)
        self.show_frame("CartScreen")

    def add_to_cart(self, added_item, quantity):
        """Adds an item and its quantity to the cart."""
        # Check if item is already in cart
        for item_info in self.cart:
            if item_info["item"]["name"] == added_item["name"]:
                item_info["quantity"] += quantity
                return  # Exit after updating

        # If not in cart, add as a new entry
        self.cart.append({"item": added_item, "quantity": quantity})

    def remove_from_cart(self, item_to_remove):
        """Removes an item entirely from the cart and restores its quantity."""
        item_found = None
        for item_info in self.cart:
            if item_info["item"]["name"] == item_to_remove["name"]:
                item_found = item_info
                break

        if item_found:
            self.increase_item_quantity(item_found["item"], item_found["quantity"])
            self.cart.remove(item_found)
            self.show_cart()  # Refresh cart screen

    def increase_cart_item_quantity(self, item_to_increase):
        """Increases an item's quantity in the cart by 1."""
        # First, check if there is available stock
        for master_item in self.items:
            if master_item["name"] == item_to_increase["name"]:
                if master_item["quantity"] > 0:
                    master_item["quantity"] -= 1  # Reduce from master list
                    # Now, increase in cart
                    for cart_item_info in self.cart:
                        if cart_item_info["item"]["name"] == item_to_increase["name"]:
                            cart_item_info["quantity"] += 1
                            self.show_cart()  # Refresh cart screen
                            return

    def decrease_cart_item_quantity(self, item_to_decrease):
        """Decreases an item's quantity in the cart by 1."""
        for item_info in self.cart:
            if item_info["item"]["name"] == item_to_decrease["name"]:
                if item_info["quantity"] > 1:
                    item_info["quantity"] -= 1
                    self.increase_item_quantity(item_to_decrease, 1)
                    self.show_cart()  # Refresh cart screen
                else:  # If quantity is 1, remove it completely
                    self.remove_from_cart(item_to_decrease)
                return

    def clear_cart(self):
        """Empties the cart."""
        self.cart.clear()

    def handle_checkout(self, checked_out_items):
        """
        Processes items at checkout. In a real app, this would handle payment.
        Here, we simulate a potential failure.
        Returns True on success, False on failure.
        """

        # TODO: Replace this simulation with real payment processing logic.
        import random

        # Simulate a 50% chance of checkout failure
        if random.random() < 0.5:
            print("Checkout failed. (Simulated)")
            return False

        print("Checkout successful. Items processed:", checked_out_items)
        self.save_items_to_json()  # Persist the new quantities
        return True

    def reduce_item_quantity(self, item, quantity):
        """Reduces the quantity of the item in the KioskFrame."""
        kiosk_frame = self.frames["KioskFrame"]
        for index in range(len(kiosk_frame.items)):
            kiosk_item = kiosk_frame.items[index]
            if kiosk_item["name"] == item["name"]:
                print(f"Reducing {item['name']} quantity by {quantity}")
                self.items[index]["quantity"] -= quantity

    def increase_item_quantity(self, item, quantity):
        """Increases the quantity of an item in the master item list."""
        for master_item in self.items:
            if master_item["name"] == item["name"]:
                master_item["quantity"] += quantity
                return

    def add_item(self, new_item_data):
        """
        Adds a new item to the master list if the name doesn't already exist.
        Saves to JSON on success. Returns True on success, False on failure.
        """
        new_item_name = new_item_data.get("name", "").strip()
        # Check for existing item with the same name (case-insensitive)
        if any(item.get("name", "").strip().lower() == new_item_name.lower() for item in self.items):
            return False  # Item with this name already exists

        self.items.append(new_item_data)
        self.save_items_to_json()
        # Refresh screens that show items
        self.frames["AdminScreen"].populate_items()
        self.frames["KioskFrame"].populate_items()
        return True

    def update_item(self, original_item_name, updated_item_data):
        """Updates an existing item in the master list and saves to JSON."""
        for i, item in enumerate(self.items):
            if item["name"] == original_item_name:
                self.items[i] = updated_item_data
                break
        self.save_items_to_json()
        self.frames["AdminScreen"].populate_items()
        self.frames["KioskFrame"].populate_items()

    def remove_item(self, item_to_remove):
        """Removes an item from the master list and saves to JSON."""
        self.items.remove(item_to_remove)
        self.save_items_to_json()
        self.frames["AdminScreen"].populate_items()

    def show_admin(self):
        self.show_frame("AdminScreen")

    def handle_escape(self, event=None):
        """Handle Escape key press for navigation."""
        print(f"Escape pressed in frame: {self.active_frame_name}")  # Debug print
        
        if self.grab_current():
            return

        # From Item/Cart screens, go back to Kiosk
        if self.active_frame_name in ["ItemScreen", "CartScreen"]:
            self.show_kiosk()  # Use show_kiosk instead of show_frame
        # From Kiosk/Admin go back to Selection
        elif self.active_frame_name in ["KioskFrame", "AdminScreen"]:
            # Handle window state in show_frame
            self.show_frame("SelectionScreen")
        else:
            self.destroy()


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()