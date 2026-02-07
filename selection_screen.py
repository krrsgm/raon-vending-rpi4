import tkinter as tk
from tkinter import font as tkfont

class SelectionScreen(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg='#f0f4f8') # Light background
        self.controller = controller

        # Get screen dimensions for proportional sizing
        screen_height = self.winfo_screenheight()
        title_size = int(screen_height * 0.04)  # 4% of screen height
        button_size = int(screen_height * 0.025)  # 2.5% of screen height
        title_font = tkfont.Font(family="Helvetica", size=title_size, weight="bold")
        button_font = tkfont.Font(family="Helvetica", size=button_size, weight="bold")

        label = tk.Label(
            self, 
            text="Select Operating Mode", 
            font=title_font,
            bg='#f0f4f8',
            fg='#2c3e50' # Dark text
        )
        # Header at 1.5 inches (assuming ~96 DPI, so ~144 pixels)
        label.pack(side="top", fill="x", pady=(144, 50))

        kiosk_button = tk.Button(
            self, 
            text="Kiosk",
            font=button_font,
            command=lambda: controller.show_kiosk(),
            bg='#27ae60',  # Green
            fg='#ffffff',  # White text
            activebackground='#2ecc71', # Lighter green on click
            activeforeground='#ffffff',
            width=15,
            pady=15,
            relief='flat',
            borderwidth=0
        )
        kiosk_button.pack(pady=20)

        admin_button = tk.Button(
            self, 
            text="Admin",
            font=button_font,
            command=lambda: controller.show_admin(),
            bg='#bdc3c7', # Light gray
            fg='#2c3e50', # Dark text
            activebackground='#95a5a6', # Darker gray on click
            activeforeground='#2c3e50',
            width=15,
            pady=15,
            relief='flat',
            borderwidth=0
        )
        admin_button.pack(pady=20)

        exit_label = tk.Label(
            self, 
            text="Press 'Esc' to exit", 
            font=("Helvetica", 12), 
            fg="#7f8c8d", # Gray text
            bg='#f0f4f8'
        )
        exit_label.pack(side='bottom', pady=20)