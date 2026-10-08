"""The bar along the bottom of every page: the preview option, Open folder and Convert.

Play lives on each stem's row (and turns into Stop while that stem plays), so it's always clear
which stem you're hearing. Esc also stops playback.
"""

import tkinter as tk
from tkinter import ttk


class ActionBar(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, style="Card.TFrame", padding=(16, 12))
        self.columnconfigure(2, weight=1)
        self.with_original = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Mix in the original stem when previewing", variable=self.with_original).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        self.open_btn = ttk.Button(self, text="Open folder")
        self.open_btn.grid(row=0, column=3, sticky="e", padx=(0, 10))
        self.open_btn.state(["disabled"])
        self.convert_btn = ttk.Button(self, text="Convert to MIDI", style="Accent.TButton")
        self.convert_btn.grid(row=0, column=4, sticky="e")

    def set_convert_label(self, stems):
        """Say what Convert will do: 'Convert 4 stems to MIDI' or 'Convert Drums.wav to MIDI'."""
        if len(stems) == 1:
            name = stems[0].name
            name = name if len(name) <= 24 else name[:21] + "..."
            text = f"Convert {name} to MIDI"
        elif stems:
            text = f"Convert {len(stems)} stems to MIDI"
        else:
            text = "Convert to MIDI"
        self.convert_btn.configure(text=text)
