"""The bar along the bottom of every page: Stop, the preview option, Open folder and Convert all.

Play lives on each stem's row, so it's always clear which stem you're hearing.
"""

import tkinter as tk
from tkinter import ttk


class ActionBar(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame", padding=(16, 12))
        self.columnconfigure(2, weight=1)
        self.stop_btn = ttk.Button(self, text="Stop preview")
        self.stop_btn.grid(row=0, column=0, sticky="w")
        self.with_original = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Mix in the original stem when previewing", variable=self.with_original).grid(
            row=0, column=1, sticky="w", padx=(14, 0)
        )
        self.open_btn = ttk.Button(self, text="Open folder")
        self.open_btn.grid(row=0, column=3, sticky="e", padx=(0, 10))
        self.open_btn.state(["disabled"])
        self.convert_btn = ttk.Button(self, text="Convert all to MIDI", style="Accent.TButton")
        self.convert_btn.grid(row=0, column=4, sticky="e")
