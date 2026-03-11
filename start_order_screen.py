import tkinter as tk
from tkinter import font as tkfont


class StartOrderScreen(tk.Frame):
    """Simple kiosk landing screen with a Start Order action."""

    def __init__(self, parent, controller):
        super().__init__(parent, bg="#000000")
        self.controller = controller
        primary_blue = "#2222a8"

        screen_height = self.winfo_screenheight()
        screen_width = self.winfo_screenwidth()
        touch_dead_zone_top = 100
        touch_dead_zone_bottom_start = 1700
        touch_dead_zone_bottom = max(0, screen_height - touch_dead_zone_bottom_start)
        title_font = tkfont.Font(family="Helvetica", size=max(20, int(screen_height * 0.036)), weight="bold")
        instructions_font = tkfont.Font(family="Helvetica", size=max(8, int(screen_height * 0.014)))

        # Non-touch top area visualized as black.
        top_dead_zone = tk.Frame(self, bg="#000000", height=touch_dead_zone_top)
        top_dead_zone.pack(side="top", fill="x")
        top_dead_zone.pack_propagate(False)

        # Main touch-active content area.
        content = tk.Frame(self, bg=primary_blue)
        content.pack(expand=True, fill="both")

        # Non-touch bottom area visualized as black.
        if touch_dead_zone_bottom > 0:
            bottom_dead_zone = tk.Frame(self, bg="#000000", height=touch_dead_zone_bottom)
            bottom_dead_zone.pack(side="bottom", fill="x")
            bottom_dead_zone.pack_propagate(False)

        center_panel = tk.Frame(content, bg=primary_blue)
        center_panel.place(relx=0.5, rely=0.47, anchor="center")

        title = tk.Label(
            center_panel,
            text="Welcome",
            font=title_font,
            bg=primary_blue,
            fg="white",
            anchor="center",
            justify="center",
        )
        title.pack(pady=(0, 10))

        instructions_text = (
            "INSTRUCTIONS:\n\n"
            "1. Click or Tap anywhere to start order.\n\n"
            "2. Choose desired items, its quantity, then add to cart.\n\n"
            "3. Go to cart, and pay.\n\n"
            "4. Insert payment; wait for the display to count each bill/coin before inserting another.\n\n"
            "5. Wait for the change.\n\n"
            "6. Wait for the item.\n\n"
            "7. Transaction done.\n\n"
            "8. Dont forget to scan the given QR code."
        )

        instructions = tk.Label(
            center_panel,
            text=instructions_text,
            font=instructions_font,
            bg=primary_blue,
            fg="white",
            anchor="w",
            justify="left",
            wraplength=max(520, int(screen_width * 0.74)),
        )
        instructions.pack(pady=(10, 0), padx=max(14, int(screen_width * 0.035)))

        # Hidden button flow: allow touch/click anywhere on this screen to proceed.
        content.bind("<Button-1>", lambda _e: self.controller.start_order())
        center_panel.bind("<Button-1>", lambda _e: self.controller.start_order())
        title.bind("<Button-1>", lambda _e: self.controller.start_order())
        instructions.bind("<Button-1>", lambda _e: self.controller.start_order())

