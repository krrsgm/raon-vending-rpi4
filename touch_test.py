#!/usr/bin/env python3
"""
Touchscreen test utility for Raspberry Pi kiosk setups.

Features:
- Fullscreen touch test view (or windowed with --windowed)
- Live X/Y coordinate display
- Touch trail drawing
- 9 target points (corners, edges, center) to verify orientation mapping
"""

import argparse
import math
import tkinter as tk


class TouchTestApp:
    def __init__(self, windowed=False):
        self.root = tk.Tk()
        self.root.title("RAON Touchscreen Test")

        self.fullscreen = not windowed
        if self.fullscreen:
            self.root.attributes("-fullscreen", True)
        else:
            self.root.geometry("1200x800")

        self.root.configure(bg="#121417")

        self.last_point = None
        self.target_radius = 26
        self.targets = []

        self.coord_var = tk.StringVar(value="Touch: - , -")
        self.status_var = tk.StringVar(value="Tap each target. ESC to exit.")
        self.coverage_var = tk.StringVar(value="Coverage: X -..- | Y -..-")
        self.hit_var = tk.StringVar(value="Targets Hit: 0/9")

        self.cover_min_x = None
        self.cover_max_x = None
        self.cover_min_y = None
        self.cover_max_y = None

        self._build_ui()
        self._bind_keys()

    def _build_ui(self):
        top = tk.Frame(self.root, bg="#1a1f26")
        top.pack(fill="x", side="top")

        tk.Label(
            top,
            text="Touchscreen Orientation Test",
            bg="#1a1f26",
            fg="#f2f4f8",
            font=("Helvetica", 18, "bold"),
            pady=8,
        ).pack(side="left", padx=12)

        controls = tk.Frame(top, bg="#1a1f26")
        controls.pack(side="right", padx=8)

        tk.Button(
            controls,
            text="Clear Trail (C)",
            command=self.clear_trail,
            bg="#2f7fd1",
            fg="white",
            relief="flat",
            padx=10,
            pady=6,
        ).pack(side="left", padx=4)

        tk.Button(
            controls,
            text="Reset Targets (R)",
            command=self.reset_targets,
            bg="#3b8f4d",
            fg="white",
            relief="flat",
            padx=10,
            pady=6,
        ).pack(side="left", padx=4)

        tk.Button(
            controls,
            text="Exit (ESC)",
            command=self.root.destroy,
            bg="#b83e3e",
            fg="white",
            relief="flat",
            padx=10,
            pady=6,
        ).pack(side="left", padx=4)

        info = tk.Frame(self.root, bg="#121417")
        info.pack(fill="x", side="top", padx=12, pady=(8, 6))

        tk.Label(
            info,
            textvariable=self.coord_var,
            bg="#121417",
            fg="#d8dee9",
            font=("Helvetica", 13, "bold"),
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            info,
            textvariable=self.coverage_var,
            bg="#121417",
            fg="#d8dee9",
            font=("Helvetica", 11),
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            info,
            textvariable=self.hit_var,
            bg="#121417",
            fg="#a4e284",
            font=("Helvetica", 11, "bold"),
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            info,
            textvariable=self.status_var,
            bg="#121417",
            fg="#f7d17a",
            font=("Helvetica", 11),
            anchor="w",
        ).pack(fill="x")

        self.canvas = tk.Canvas(
            self.root,
            bg="#0f1115",
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_touch_press)
        self.canvas.bind("<B1-Motion>", self._on_touch_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_touch_release)

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda _e: self.root.destroy())
        self.root.bind("<q>", lambda _e: self.root.destroy())
        self.root.bind("<c>", lambda _e: self.clear_trail())
        self.root.bind("<r>", lambda _e: self.reset_targets())
        self.root.bind("<F11>", lambda _e: self.toggle_fullscreen())

    def _on_resize(self, _event):
        self._draw_overlay()

    def _draw_overlay(self):
        self.canvas.delete("overlay")

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 80 or h < 80:
            return

        grid_color = "#20252d"
        for i in range(1, 10):
            x = int((w / 10) * i)
            y = int((h / 10) * i)
            self.canvas.create_line(x, 0, x, h, fill=grid_color, tags="overlay")
            self.canvas.create_line(0, y, w, y, fill=grid_color, tags="overlay")

        self.targets = self._target_layout(w, h)
        hit_count = 0
        for t in self.targets:
            hit = bool(t.get("hit", False))
            if hit:
                hit_count += 1
            fill = "#3fb950" if hit else "#cfa74a"
            self.canvas.create_oval(
                t["x"] - self.target_radius,
                t["y"] - self.target_radius,
                t["x"] + self.target_radius,
                t["y"] + self.target_radius,
                outline=fill,
                width=3,
                tags="overlay",
            )
            self.canvas.create_text(
                t["x"],
                t["y"],
                text=t["name"],
                fill="#f4f7fb",
                font=("Helvetica", 10, "bold"),
                tags="overlay",
            )

        self.hit_var.set(f"Targets Hit: {hit_count}/9")

    def _target_layout(self, width, height):
        margin_x = max(50, int(width * 0.08))
        margin_y = max(50, int(height * 0.08))
        cx = width // 2
        cy = height // 2

        positions = [
            ("TL", margin_x, margin_y),
            ("TC", cx, margin_y),
            ("TR", width - margin_x, margin_y),
            ("ML", margin_x, cy),
            ("C", cx, cy),
            ("MR", width - margin_x, cy),
            ("BL", margin_x, height - margin_y),
            ("BC", cx, height - margin_y),
            ("BR", width - margin_x, height - margin_y),
        ]

        prev_hits = {t["name"]: t.get("hit", False) for t in self.targets}
        return [
            {"name": name, "x": x, "y": y, "hit": prev_hits.get(name, False)}
            for name, x, y in positions
        ]

    def _on_touch_press(self, event):
        self.last_point = (event.x, event.y)
        self._mark_touch(event.x, event.y)
        self._mark_target_hit(event.x, event.y)
        self._update_stats(event.x, event.y)

    def _on_touch_move(self, event):
        if self.last_point is not None:
            self.canvas.create_line(
                self.last_point[0],
                self.last_point[1],
                event.x,
                event.y,
                fill="#7fb5ff",
                width=3,
                capstyle=tk.ROUND,
                smooth=True,
                tags="trail",
            )
        self.last_point = (event.x, event.y)
        self._mark_touch(event.x, event.y)
        self._mark_target_hit(event.x, event.y)
        self._update_stats(event.x, event.y)

    def _on_touch_release(self, event):
        self.last_point = None
        self._mark_touch(event.x, event.y, release=True)
        self._update_stats(event.x, event.y)

    def _mark_touch(self, x, y, release=False):
        color = "#e67e22" if release else "#ff6b6b"
        r = 8 if release else 6
        self.canvas.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            fill=color,
            outline="",
            tags="trail",
        )

    def _mark_target_hit(self, x, y):
        changed = False
        for target in self.targets:
            if target.get("hit"):
                continue
            dx = x - target["x"]
            dy = y - target["y"]
            if math.hypot(dx, dy) <= self.target_radius + 12:
                target["hit"] = True
                changed = True
        if changed:
            self._draw_overlay()
            hits = sum(1 for t in self.targets if t.get("hit"))
            if hits == len(self.targets):
                self.status_var.set("All targets hit. Touch orientation looks aligned.")
            else:
                self.status_var.set("Good. Continue tapping all targets.")

    def _update_stats(self, x, y):
        self.coord_var.set(f"Touch: X={x}  Y={y}")

        self.cover_min_x = x if self.cover_min_x is None else min(self.cover_min_x, x)
        self.cover_max_x = x if self.cover_max_x is None else max(self.cover_max_x, x)
        self.cover_min_y = y if self.cover_min_y is None else min(self.cover_min_y, y)
        self.cover_max_y = y if self.cover_max_y is None else max(self.cover_max_y, y)
        self.coverage_var.set(
            f"Coverage: X {self.cover_min_x}..{self.cover_max_x} | "
            f"Y {self.cover_min_y}..{self.cover_max_y}"
        )

    def clear_trail(self):
        self.canvas.delete("trail")
        self.status_var.set("Trail cleared.")

    def reset_targets(self):
        for target in self.targets:
            target["hit"] = False
        self.cover_min_x = None
        self.cover_max_x = None
        self.cover_min_y = None
        self.cover_max_y = None
        self.coord_var.set("Touch: - , -")
        self.coverage_var.set("Coverage: X -..- | Y -..-")
        self.status_var.set("Targets reset. Tap each marker to test orientation.")
        self.canvas.delete("trail")
        self._draw_overlay()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)

    def run(self):
        self.root.mainloop()


def parse_args():
    parser = argparse.ArgumentParser(description="Touchscreen orientation test utility.")
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Run in windowed mode instead of fullscreen.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    app = TouchTestApp(windowed=args.windowed)
    app.run()
