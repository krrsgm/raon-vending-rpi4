import tkinter as tk
from tkinter import font as tkfont


class StartOrderScreen(tk.Frame):
    """Simple kiosk landing screen with a Start Order action."""

    def __init__(self, parent, controller):
        super().__init__(parent, bg="#2222a8")
        self.controller = controller
        primary_blue = "#2222a8"

        screen_height = self.winfo_screenheight()
        title_font = tkfont.Font(family="Helvetica", size=max(24, int(screen_height * 0.045)), weight="bold")
        subtitle_font = tkfont.Font(family="Helvetica", size=max(12, int(screen_height * 0.02)))

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

        subtitle = tk.Label(
            center_panel,
            text="Click Anywhere to Start Order",
            font=subtitle_font,
            bg=primary_blue,
            fg="white",
            anchor="center",
            justify="center",
        )
        subtitle.pack()

        # Hidden button flow: allow touch/click anywhere on this screen to proceed.
        content.bind("<Button-1>", lambda _e: self.controller.start_order())
        center_panel.bind("<Button-1>", lambda _e: self.controller.start_order())
        title.bind("<Button-1>", lambda _e: self.controller.start_order())
        subtitle.bind("<Button-1>", lambda _e: self.controller.start_order())
