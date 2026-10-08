"""The '<stem> settings' card: settings for the stem selected in the list.

Sensitivity and humanize belong to each stem. Drum stems also get the drums to write and the
drum map (the map is shared by all drum stems because it depends on your drum plugin).
"""

import tkinter as tk
from tkinter import ttk

from ..config import DEFAULT_DRUM_PARTS, DRUM_MAP_LABELS
from .widgets import slider

SENS_MIN, SENS_MAX = 0.1, 1.5
KIT_BOXES = [  # (label shown, part name) - named like MT Power Drumkit's channels
    ("Kick", "kick"),
    ("Snare", "snare"),
    ("Hi-Hat cl.", "hihat"),
    ("Hi-Hat op.", "openhat"),
    ("Toms", "toms"),
    ("Crash", "crash"),
    ("Ride", "ride"),
]


def humanize_word(v):
    return "off" if v == 0 else "subtle" if v <= 30 else "natural" if v <= 65 else "loose"


class StemSettingsCard(ttk.Frame):
    def __init__(self, parent, fonts, map_var, on_map_pick, on_apply_all, on_open_settings, on_change=None):
        super().__init__(parent, style="Card.TFrame", padding=(16, 12))
        self.stem = None
        self.on_change = on_change
        self._loading = False
        self.columnconfigure(1, weight=1)

        top = ttk.Frame(self, style="Card.TFrame")
        top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.title = tk.StringVar(value="Stem settings")
        ttk.Label(top, textvariable=self.title, style="Head.TLabel").pack(side="left")
        self.hint = tk.StringVar()
        ttk.Label(top, textvariable=self.hint, style="Muted.TLabel").pack(side="left", padx=(10, 0))
        self.apply_btn = ttk.Button(top, text="Apply to all stems", style="Small.TButton", command=on_apply_all)
        self.apply_btn.pack(side="right")

        self.body = ttk.Frame(self, style="Card.TFrame")
        self.body.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.body.columnconfigure(1, weight=1)
        self.empty = ttk.Label(self, text="Add a stem to see its settings here.", style="Muted.TLabel")

        def row_label(r, text):
            ttk.Label(self.body, text=text, style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=4, padx=(0, 16))

        # sensitivity: slider plus a box you can type in
        self.sens_var = tk.DoubleVar(value=0.8)
        self.sens_text = tk.StringVar(value="0.80")
        row_label(0, "Sensitivity")
        sens = ttk.Frame(self.body, style="Card.TFrame")
        sens.grid(row=0, column=1, sticky="w")
        ttk.Label(sens, text="fewer notes", style="Muted.TLabel").pack(side="left")
        slider(sens, self.sens_var, SENS_MIN, SENS_MAX, 0.01, self._on_slide).pack(side="left", padx=8)
        ttk.Label(sens, text="more notes", style="Muted.TLabel").pack(side="left")
        box = ttk.Spinbox(
            sens,
            from_=SENS_MIN,
            to=SENS_MAX,
            increment=0.05,
            width=6,
            textvariable=self.sens_text,
            command=self.apply_typed_sensitivity,
            format="%.2f",
        )
        box.pack(side="left", padx=(14, 0))
        box.bind("<Return>", self.apply_typed_sensitivity)
        box.bind("<FocusOut>", self.apply_typed_sensitivity)

        # humanize
        self.human_var = tk.IntVar(value=0)
        self.human_text = tk.StringVar(value="0%  (off)")
        row_label(1, "Humanize")
        hum = ttk.Frame(self.body, style="Card.TFrame")
        hum.grid(row=1, column=1, sticky="w")
        ttk.Label(hum, text="tight", style="Muted.TLabel").pack(side="left")
        slider(hum, self.human_var, 0, 100, 5, self._on_humanize).pack(side="left", padx=8)
        ttk.Label(hum, text="loose", style="Muted.TLabel").pack(side="left")
        ttk.Label(hum, textvariable=self.human_text, style="Value.TLabel").pack(side="left", padx=(14, 0))

        # drums only
        self.drums = ttk.Frame(self.body, style="Card.TFrame")
        self.drums.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.drums.columnconfigure(1, weight=1)
        ttk.Label(self.drums, text="Drums", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 16))
        kit = ttk.Frame(self.drums, style="Card.TFrame")
        kit.grid(row=0, column=1, sticky="w")
        self.kit_vars = {}
        for i, (label, part) in enumerate(KIT_BOXES):
            var = tk.BooleanVar(value=part in DEFAULT_DRUM_PARTS)
            var.trace_add("write", lambda *_: self._store())
            ttk.Checkbutton(kit, text=label, variable=var).grid(row=0, column=i, sticky="w", padx=(0, 16), pady=2)
            self.kit_vars[part] = var
        ttk.Label(self.drums, text="Drum map", style="Card.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 16), pady=(8, 0)
        )
        mapf = ttk.Frame(self.drums, style="Card.TFrame")
        mapf.grid(row=1, column=1, sticky="w", pady=(8, 0))
        self.map_box = ttk.Combobox(
            mapf, textvariable=map_var, values=list(DRUM_MAP_LABELS.values()), state="readonly", width=48
        )
        self.map_box.pack(side="left")
        self.map_box.bind("<<ComboboxSelected>>", lambda e: on_map_pick())
        link = ttk.Label(mapf, text="shared by all drum stems · note numbers in Settings", style="Muted.TLabel")
        link.pack(side="left", padx=(12, 0))
        link.configure(cursor="hand2")
        link.bind("<Button-1>", lambda e: on_open_settings())
        self.show(None)

    # ---- showing a stem
    def show(self, stem, count=0):
        """Load a stem's settings into the card (or show the empty message when there's none)."""
        self.stem = stem
        if stem is None:
            self.title.set("Stem settings")
            self.hint.set("")
            self.body.grid_remove()
            self.apply_btn.pack_forget()
            self.empty.grid(row=1, column=0, columnspan=3, sticky="w")
            return
        self.empty.grid_remove()
        self.body.grid()
        self.title.set(f"{stem.name} settings")
        self.hint.set(f"{stem.stem_type} stem" + (" · click another stem to change its settings" if count > 1 else ""))
        if count > 1:
            self.apply_btn.pack(side="right")
        else:
            self.apply_btn.pack_forget()
        self._loading = True
        self.sens_var.set(stem.sensitivity)
        self.sens_text.set(f"{stem.sensitivity:.2f}")
        self.human_var.set(stem.humanize)
        self.human_text.set(f"{stem.humanize}%  ({humanize_word(stem.humanize)})")
        for part, var in self.kit_vars.items():
            var.set(part in stem.parts)
        self._loading = False
        if stem.stem_type == "drums":
            self.drums.grid()
        else:
            self.drums.grid_remove()

    # ---- writing changes back to the stem
    def _store(self):
        if self._loading or self.stem is None:
            return
        self.stem.sensitivity = round(float(self.sens_var.get()), 2)
        self.stem.humanize = int(self.human_var.get())
        self.stem.parts = [p for _, p in KIT_BOXES if self.kit_vars[p].get()]
        if self.on_change:
            self.on_change()

    def _on_slide(self, value):
        self.sens_text.set(f"{float(value):.2f}")
        self._store()

    def apply_typed_sensitivity(self, *_):
        try:
            v = max(SENS_MIN, min(SENS_MAX, float(self.sens_text.get())))
        except ValueError:
            v = self.sens_var.get()
        self.sens_var.set(v)
        self.sens_text.set(f"{v:.2f}")
        self._store()

    def _on_humanize(self, value):
        v = int(float(value))
        self.human_text.set(f"{v}%  ({humanize_word(v)})")
        self._store()

    def set_enabled(self, on):
        self.apply_btn.state(["!disabled"] if on else ["disabled"])
