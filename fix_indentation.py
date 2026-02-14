#!/usr/bin/env python3
with open('assign_items_screen.py', 'r') as f:
    lines = f.readlines()

# Line 248 (index 247) - fix the thumb_lbl line
lines[247] = '                thumb_lbl = tk.Label(content, text=\'\', width=10, height=4, anchor=\'center\', background=\'#e8e8e8\', relief=\'sunken\', font=("Helvetica", 8))\n'

with open('assign_items_screen.py', 'w') as f:
    f.writelines(lines)

print("Fixed!")
