import tkinter as tk
from tkinter import font as tkfont


class StartOrderScreen(tk.Frame):
    """Simple kiosk landing screen with a Start Order action."""

    def __init__(self, parent, controller):
        super().__init__(parent, bg="#2222a8")
        self.controller = controller
        primary_blue = "#2222a8"

        screen_height = self.winfo_screenheight()
        screen_width = self.winfo_screenwidth()
        title_font = tkfont.Font(family="Helvetica", size=max(24, int(screen_height * 0.045)), weight="bold")
        subtitle_font = tkfont.Font(family="Helvetica", size=max(12, int(screen_height * 0.02)))
        instructions_font = tkfont.Font(family="Helvetica", size=max(10, int(screen_height * 0.017)))

        content = tk.Frame(self, bg=primary_blue)
        content.pack(expand=True, fill="both")

        center_panel = tk.Frame(content, bg=primary_blue)
        center_panel.place(relx=0.5, rely=0.5, anchor="center")

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
            "1. Click anywhere to start order.\n"
            "2. Choose desired items, its quantity, then add to cart.\n"
            "3. Go to cart, and pay.\n"
            "4. Insert closest amount of payment. (Note: wait for the display to show that it has counted the bill you inserted before inserting another. This is to avoid errors when computing.)\n"
            "5. Wait for the change.\n"
            "6. Wait for the item.\n"
            "7. Transaction done.\n"
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
            wraplength=max(640, int(screen_width * 0.85)),
        )
        instructions.pack(pady=(20, 0))

        # Hidden button flow: allow touch/click anywhere on this screen to proceed.
        content.bind("<Button-1>", lambda _e: self.controller.start_order())
        center_panel.bind("<Button-1>", lambda _e: self.controller.start_order())
        title.bind("<Button-1>", lambda _e: self.controller.start_order())
        instructions.bind("<Button-1>", lambda _e: self.controller.start_order())
