import tkinter as tk
from tkinter import font as tkfont

class SelectionScreen(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg='#f0f4f8') # Light background
        self.controller = controller
        primary_blue = '#2222a8'
        primary_blue_hover = '#2f3fc6'
        secondary_blue = '#4a63d9'
        secondary_blue_hover = '#5b73e2'

        def style_button(btn, hover_bg):
            base_bg = btn.cget('bg')
            btn.configure(
                relief='flat',
                borderwidth=0,
                highlightthickness=0,
                cursor='hand2',
                activebackground=hover_bg,
                activeforeground='#ffffff',
                padx=18,
                pady=12
            )
            btn.bind('<Enter>', lambda _e: btn.configure(bg=hover_bg))
            btn.bind('<Leave>', lambda _e: btn.configure(bg=base_bg))

        # Get screen dimensions for proportional sizing
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        # Cap title size using width so long text does not clip on narrow/portrait displays.
        title_size = max(16, min(int(screen_height * 0.04), int(screen_width * 0.045)))
        button_size = max(12, min(int(screen_height * 0.025), int(screen_width * 0.04)))
        title_font = tkfont.Font(family="Helvetica", size=title_size, weight="bold")
        button_font = tkfont.Font(family="Helvetica", size=button_size, weight="bold")

        label = tk.Label(
            self, 
            text="Select Operating Mode", 
            font=title_font,
            bg='#f0f4f8',
            fg='#2c3e50', # Dark text
            wraplength=int(screen_width * 0.92),
            justify='center'
        )
        # Keep spacing proportional so text is fully visible across display sizes.
        label.pack(side="top", fill="x", pady=(max(24, int(screen_height * 0.12)), max(24, int(screen_height * 0.06))))

        kiosk_button = tk.Button(
            self, 
            text="Kiosk",
            font=button_font,
            command=lambda: controller.show_start_order(),
            bg=primary_blue,
            fg='#ffffff',  # White text
            activebackground=primary_blue_hover,
            activeforeground='#ffffff',
            width=15,
            pady=15,
            relief='flat',
            borderwidth=0
        )
        kiosk_button.pack(pady=20)
        style_button(kiosk_button, primary_blue_hover)

        admin_button = tk.Button(
            self, 
            text="Admin",
            font=button_font,
            command=lambda: controller.show_admin(),
            bg=secondary_blue,
            fg='#ffffff',
            activebackground=secondary_blue_hover,
            activeforeground='#ffffff',
            width=15,
            pady=15,
            relief='flat',
            borderwidth=0
        )
        admin_button.pack(pady=20)
        style_button(admin_button, secondary_blue_hover)

        exit_label = tk.Label(
            self, 
            text="Press 'Esc' to exit", 
            font=("Helvetica", 12), 
            fg="#7f8c8d", # Gray text
            bg='#f0f4f8'
        )
        exit_label.pack(side='bottom', pady=20)
