"""Drum Kit page: which drums to write, and which MIDI note each one goes on."""

import tkinter as tk
from tkinter import ttk

from ...config import DRUM_LABELS, DRUM_MAP_LABELS, DRUM_MAPS, DRUM_NOTES, load_settings, note_name
from ..widgets import card

KIT_BOXES = [  # (label shown, part name, default on) - named like MT Power Drumkit's channels
    ("Kick", "kick", True), ("Snare", "snare", True), ("Hi-Hat cl.", "hihat", True),
    ("Hi-Hat op.", "openhat", True), ("Toms", "toms", True), ("Crash", "crash", False),
    ("Ride", "ride", False),
]
MAP_HELP = (
    "General MIDI works with MT Power Drumkit 2, EZdrummer, Addictive Drums, Superior Drummer and most "
    "drum plugins.\n\nPads in order is for pad samplers (FL Studio FPC, Ableton Drum Rack, MPC): load "
    "your sounds from note 36 up in the order shown.\n\nCustom: type any note into a box; it's remembered "
    "for next time.\n\nNames use 36 = C1. Some DAWs label octaves differently, but the note is the same.")


class DrumKitPage(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.kit_vars = {part: tk.BooleanVar(value=on) for _, part, on in KIT_BOXES}
        self.label_to_key = {v: k for k, v in DRUM_MAP_LABELS.items()}
        self._applying = False
        self._build_kit()
        self._build_map()

    def _build_kit(self):
        c = card(self, 0, "Drums to write", "drum stems only")
        kit = ttk.Frame(c, style="Card.TFrame")
        kit.grid(row=1, column=0, columnspan=3, sticky="w")
        self.kit_checks = []
        for i, (label, part, _) in enumerate(KIT_BOXES):
            cb = ttk.Checkbutton(kit, text=label, variable=self.kit_vars[part])
            cb.grid(row=0, column=i, sticky="w", padx=(0, 20), pady=2)
            self.kit_checks.append(cb)
        self.kit_note = tk.StringVar()
        ttk.Label(c, textvariable=self.kit_note, style="Muted.TLabel", wraplength=680, justify="left")\
            .grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def _build_map(self):
        c = card(self, 1, "Drum map", "match this to your drum plugin")
        mapf = ttk.Frame(c, style="Card.TFrame")
        mapf.grid(row=1, column=0, columnspan=3, sticky="ew")
        saved = load_settings()
        start_key = saved.get("drum_map", "General MIDI")
        if start_key not in DRUM_MAP_LABELS:
            start_key = "General MIDI"
        self.map_var = tk.StringVar(value=DRUM_MAP_LABELS[start_key])
        self.map_box = ttk.Combobox(mapf, textvariable=self.map_var, values=list(DRUM_MAP_LABELS.values()),
                                    state="readonly", width=52)
        self.map_box.grid(row=0, column=0, columnspan=9, sticky="w")
        self.map_box.bind("<<ComboboxSelected>>", lambda e: self.apply_map(self.map_key()))

        start_notes = DRUM_MAPS.get(start_key) or {**DRUM_NOTES, **saved.get("custom_map", {})}
        self.note_vars, self.name_vars = {}, {}
        for col, part in enumerate(DRUM_LABELS):
            ttk.Label(mapf, text=DRUM_LABELS[part], style="Muted.TLabel")\
                .grid(row=1, column=col, sticky="w", pady=(12, 2), padx=(0, 8))
            self.note_vars[part] = tk.StringVar(value=str(start_notes[part]))
            self.name_vars[part] = tk.StringVar()
            ttk.Spinbox(mapf, from_=0, to=127, increment=1, width=4, textvariable=self.note_vars[part])\
                .grid(row=2, column=col, sticky="w", padx=(0, 8))
            ttk.Label(mapf, textvariable=self.name_vars[part], style="Muted.TLabel")\
                .grid(row=3, column=col, sticky="w")
            self._show_name(part)
            self.note_vars[part].trace_add("write", lambda *_, p=part: self._on_note_edit(p))
        ttk.Label(c, text=MAP_HELP, style="Muted.TLabel", justify="left", wraplength=680)\
            .grid(row=2, column=0, columnspan=3, sticky="w", pady=(12, 0))

    def _show_name(self, part):
        try:
            self.name_vars[part].set(note_name(int(self.note_vars[part].get())))
        except (ValueError, TypeError):
            self.name_vars[part].set("?")

    def _on_note_edit(self, part):
        self._show_name(part)
        if not self._applying:
            self.map_var.set(DRUM_MAP_LABELS["Custom"])  # typing a note makes it a custom map

    def map_key(self):
        return self.label_to_key[self.map_var.get()]

    def apply_map(self, key):
        notes = DRUM_MAPS.get(key) or {**DRUM_NOTES, **load_settings().get("custom_map", {})}
        self._applying = True
        for part, var in self.note_vars.items():
            var.set(str(notes[part]))
        self._applying = False

    def current_map(self):
        """Read the note boxes; returns (map, None) or (None, error message)."""
        out = {}
        for part, var in self.note_vars.items():
            try:
                n = int(var.get())
                if not 0 <= n <= 127:
                    raise ValueError
            except ValueError:
                return None, f"{DRUM_LABELS[part]} needs a note number from 0 to 127"
            out[part] = n
        return out, None

    def selected_parts(self):
        return [p for p, v in self.kit_vars.items() if v.get()]

    def update_state(self, stem_type):
        """Grey the page out when the chosen stem type can't be drums."""
        drums = stem_type in ("auto", "drums")
        for cb in self.kit_checks:
            cb.state(["!disabled"] if drums else ["disabled"])
        self.map_box.state(["!disabled", "readonly"] if drums else ["disabled"])
        self.kit_note.set("Crash and Ride start off: cymbals can bring back metallic sounds. If you untick "
                          "Hi-Hat op., open hats are written as closed hats." if drums else
                          f"Stem type is set to {stem_type}, so these settings are not used right now.")

    def reset(self):
        for _, part, on in KIT_BOXES:
            self.kit_vars[part].set(on)
        self.map_var.set(DRUM_MAP_LABELS["General MIDI"])
        self.apply_map("General MIDI")
