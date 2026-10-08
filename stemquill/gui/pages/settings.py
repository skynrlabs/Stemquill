"""Settings page: where MIDI files are saved, and which note each drum is written on."""

import tkinter as tk
from tkinter import filedialog, ttk

from ...config import DRUM_LABELS, DRUM_MAP_LABELS, DRUM_MAPS, DRUM_NOTES, load_settings, note_name
from ..widgets import card

SAME_FOLDER = "Same folder as each stem"
MAP_HELP = (
    "General MIDI works with MT Power Drumkit 2, EZdrummer, Addictive Drums, Superior Drummer and most "
    "drum plugins. Pads in order is for pad samplers (FL Studio FPC, Ableton Drum Rack, MPC): load your "
    "sounds from note 36 up in the order shown. Type any note into a box for a Custom map; it's remembered "
    "for next time. Names use 36 = C1; some DAWs label octaves differently, but the note is the same."
)


class SettingsPage(ttk.Frame):
    def __init__(self, parent, on_reset=None):
        super().__init__(parent)
        self.on_reset = on_reset
        self.columnconfigure(0, weight=1)
        self.out_dir = None
        self.out_text = tk.StringVar(value=SAME_FOLDER)
        self.open_when_done = tk.BooleanVar(value=False)
        self.label_to_key = {v: k for k, v in DRUM_MAP_LABELS.items()}
        self._applying = False
        self._build_output()
        self._build_map()
        c = card(self, 2, "Start over", "tempo, every stem's settings, save folder and drum notes")
        ttk.Button(c, text="Reset everything to defaults", command=lambda: self.on_reset and self.on_reset()).grid(
            row=1, column=0, sticky="w"
        )

    # ---- where files go
    def _build_output(self):
        c = card(self, 0, "Save MIDI files to")
        ttk.Label(c, textvariable=self.out_text, style="Card.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")
        btns = ttk.Frame(c, style="Card.TFrame")
        btns.grid(row=1, column=2, sticky="e")
        ttk.Button(btns, text="Change...", command=self.pick_folder).pack(side="left")
        ttk.Button(btns, text="Reset", command=self.reset_folder).pack(side="left", padx=(6, 0))
        ttk.Label(
            c, text="Each stem becomes  <stem name> - <type>.mid,  for example  Drums - drums.mid", style="Muted.TLabel"
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Checkbutton(c, text="Open the folder when converting finishes", variable=self.open_when_done).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(10, 0)
        )

    def pick_folder(self):
        d = filedialog.askdirectory(title="Save MIDI files to")
        if d:
            self.out_dir = d
            self.out_text.set(d)

    def reset_folder(self):
        self.out_dir = None
        self.out_text.set(SAME_FOLDER)

    # ---- drum notes
    def _build_map(self):
        c = card(self, 1, "Drum notes", "shared by all drum stems; match this to your drum plugin")
        mapf = ttk.Frame(c, style="Card.TFrame")
        mapf.grid(row=1, column=0, columnspan=3, sticky="ew")
        saved = load_settings()
        start_key = saved.get("drum_map", "General MIDI")
        if start_key not in DRUM_MAP_LABELS:
            start_key = "General MIDI"
        self.map_var = tk.StringVar(value=DRUM_MAP_LABELS[start_key])
        box = ttk.Combobox(
            mapf, textvariable=self.map_var, values=list(DRUM_MAP_LABELS.values()), state="readonly", width=52
        )
        box.grid(row=0, column=0, columnspan=9, sticky="w")
        box.bind("<<ComboboxSelected>>", lambda e: self.apply_map(self.map_key()))

        start_notes = DRUM_MAPS.get(start_key) or {**DRUM_NOTES, **saved.get("custom_map", {})}
        self.note_vars, self.name_vars = {}, {}
        for col, part in enumerate(DRUM_LABELS):
            ttk.Label(mapf, text=DRUM_LABELS[part], style="Muted.TLabel").grid(
                row=1, column=col, sticky="w", pady=(12, 2), padx=(0, 8)
            )
            self.note_vars[part] = tk.StringVar(value=str(start_notes[part]))
            self.name_vars[part] = tk.StringVar()
            ttk.Spinbox(mapf, from_=0, to=127, increment=1, width=4, textvariable=self.note_vars[part]).grid(
                row=2, column=col, sticky="w", padx=(0, 8)
            )
            ttk.Label(mapf, textvariable=self.name_vars[part], style="Muted.TLabel").grid(row=3, column=col, sticky="w")
            self._show_name(part)
            self.note_vars[part].trace_add("write", lambda *_, p=part: self._on_note_edit(p))
        ttk.Label(c, text=MAP_HELP, style="Muted.TLabel", justify="left", wraplength=700).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(12, 0)
        )

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

    def reset(self):
        self.reset_folder()
        self.open_when_done.set(False)
        self.map_var.set(DRUM_MAP_LABELS["General MIDI"])
        self.apply_map("General MIDI")
