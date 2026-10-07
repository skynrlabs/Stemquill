"""The bar along the bottom of every page: preview controls, Convert, status and progress."""

import tkinter as tk
from tkinter import ttk

from .theme import THEME as T


class ActionBar(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame", padding=(16, 12))
        self.columnconfigure(4, weight=1)
        ttk.Label(self, text="Preview", style="Head.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.play_btn = ttk.Button(self, text="Play", width=7)
        self.play_btn.grid(row=0, column=1)
        self.stop_btn = ttk.Button(self, text="Stop", width=7)
        self.stop_btn.grid(row=0, column=2, padx=(6, 14))
        self.with_original = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Mix in the original stem", variable=self.with_original)\
            .grid(row=0, column=3, sticky="w")
        self.open_btn = ttk.Button(self, text="Open folder")
        self.open_btn.grid(row=0, column=5, sticky="e", padx=(0, 10))
        self.open_btn.state(["disabled"])
        self.convert_btn = ttk.Button(self, text="Convert to MIDI", style="Accent.TButton")
        self.convert_btn.grid(row=0, column=6, sticky="e")
        self.status = tk.StringVar(value="Ready")
        self.status_lbl = ttk.Label(self, textvariable=self.status, style="Card.TLabel", foreground=T["muted"])
        self.status_lbl.grid(row=1, column=0, columnspan=5, sticky="w", pady=(10, 0))
        self.progress = ttk.Progressbar(self, mode="determinate", style="Horizontal.TProgressbar", length=200)
        self.progress.grid(row=1, column=5, columnspan=2, sticky="ew", pady=(10, 0))

    def say(self, msg, color="muted"):
        self.status.set(msg)
        self.status_lbl.configure(foreground=T[color])

    def busy_buttons(self):
        return [self.convert_btn, self.play_btn]
