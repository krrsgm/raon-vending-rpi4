import tkinter as tk
from tkinter import font as tkfont


class StartOrderScreen(tk.Frame):
    """Simple kiosk landing screen with a Start Order action."""

    def __init__(self, parent, controller):
        super().__init__(parent, bg="#f0f4f8")
        self.controller = controller

        screen_height = self.winfo_screenheight()
        title_font = tkfont.Font(family="Helvetica", size=max(24, int(screen_height * 0.045)), weight="bold")
        subtitle_font = tkfont.Font(family="Helvetica", size=max(12, int(screen_height * 0.02)))
        button_font = tkfont.Font(family="Helvetica", size=max(16, int(screen_height * 0.03)), weight="bold")

        content = tk.Frame(self, bg="#f0f4f8")
        content.pack(expand=True, fill="both")

        title = tk.Label(
            content,
            text="Welcome",
            font=title_font,
            bg="#f0f4f8",
            fg="#2c3e50",
        )
        title.pack(pady=(60, 10))

        subtitle = tk.Label(
            content,
            text="Tap Start Order to begin",
            font=subtitle_font,
            bg="#f0f4f8",
            fg="#7f8c8d",
        )
        subtitle.pack(pady=(0, 40))

        start_btn = tk.Button(
            content,
            text="Start Order",
            font=button_font,
            command=self.controller.start_order,
            bg="#27ae60",
            fg="white",
            activebackground="#2ecc71",
            activeforeground="white",
            width=16,
            pady=14,
            relief="flat",
            borderwidth=0,
        )
        start_btn.pack()
