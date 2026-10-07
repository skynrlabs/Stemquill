"""Output page: where MIDI files are saved and what happens when converting finishes."""

import tkinter as tk
from tkinter import filedialog, ttk

from ..widgets import card

SAME_FOLDER = "Same folder as each stem"


class OutputPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.out_dir = None
        self.out_text = tk.StringVar(value=SAME_FOLDER)
        self.open_when_done = tk.BooleanVar(value=False)

        c = card(self, 0, "Save MIDI files to")
        ttk.Label(c, textvariable=self.out_text, style="Card.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")
        btns = ttk.Frame(c, style="Card.TFrame")
        btns.grid(row=1, column=2, sticky="e")
        ttk.Button(btns, text="Change...", command=self.pick_folder).pack(side="left")
        ttk.Button(btns, text="Reset", command=self.reset_folder).pack(side="left", padx=(6, 0))
        ttk.Label(c, text="Each stem becomes  <stem name> - <type>.mid,  for example  Drums - drums.mid",
                  style="Muted.TLabel").grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

        c2 = card(self, 1, "When converting finishes")
        ttk.Checkbutton(c2, text="Open the folder automatically", variable=self.open_when_done)\
            .grid(row=1, column=0, columnspan=3, sticky="w")
        ttk.Label(c2, text="Then set your DAW project to the same tempo and drag each .mid onto its instrument "
                           "track at bar 1.", style="Muted.TLabel")\
            .grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def pick_folder(self):
        d = filedialog.askdirectory(title="Save MIDI files to")
        if d:
            self.out_dir = d
            self.out_text.set(d)

    def reset_folder(self):
        self.out_dir = None
        self.out_text.set(SAME_FOLDER)

    def reset(self):
        self.reset_folder()
        self.open_when_done.set(False)
