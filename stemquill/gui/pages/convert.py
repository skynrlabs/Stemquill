"""Convert page: the song's tempo, the stems (one row each), and the selected stem's settings."""

import os
import tkinter as tk
from tkinter import filedialog, ttk

from ..model import Stem
from ..stem_settings import StemSettingsCard
from ..stems_table import StemsTable
from ..widgets import card

GRID_CHOICES = {"Off (keep original timing)": 0, "1/8 note": 2, "1/8 triplet": 3, "1/16 note": 4, "1/32 note": 8}
DEFAULT_GRID = "Off (keep original timing)"
TEMPO_HINT = "Detect measures it from the selected stem"


class ConvertPage(ttk.Frame):
    def __init__(self, parent, fonts, settings_page, on_change, on_play, on_open_settings):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.settings_page = settings_page
        self.on_change = on_change
        self.on_play = on_play
        self.stems = []
        self.selected = None
        self.bpm_var = tk.StringVar(value="120")
        self.grid_var = tk.StringVar(value=DEFAULT_GRID)
        self.tempo_hint = tk.StringVar(value=TEMPO_HINT)
        self._build_song()
        self._build_stems(fonts)
        self.card = StemSettingsCard(
            self,
            fonts,
            settings_page.map_var,
            on_map_pick=lambda: settings_page.apply_map(settings_page.map_key()),
            on_apply_all=self.apply_to_all,
            on_open_settings=on_open_settings,
        )
        self.card.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        self.rowconfigure(3, weight=1)

    # ---- song: one tempo and grid for every stem
    def _build_song(self):
        c = card(self, 0, "Song", "shared by every stem; set your DAW project to the same tempo")
        ttk.Label(c, text="Tempo (BPM)", style="Card.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 16), pady=4)
        tempo = ttk.Frame(c, style="Card.TFrame")
        tempo.grid(row=1, column=1, columnspan=2, sticky="w")
        ttk.Spinbox(tempo, from_=40, to=240, increment=0.1, textvariable=self.bpm_var, width=8).pack(side="left")
        self.detect_btn = ttk.Button(tempo, text="Detect", width=8)
        self.detect_btn.pack(side="left", padx=(8, 0))
        ttk.Label(tempo, textvariable=self.tempo_hint, style="Muted.TLabel").pack(side="left", padx=(12, 0))
        ttk.Label(c, text="Snap to grid", style="Card.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 16), pady=4)
        snap = ttk.Frame(c, style="Card.TFrame")
        snap.grid(row=2, column=1, columnspan=2, sticky="w")
        ttk.Combobox(snap, textvariable=self.grid_var, values=list(GRID_CHOICES), state="readonly", width=26).pack(
            side="left"
        )
        ttk.Label(snap, text="Off is safest for AI-generated stems", style="Muted.TLabel").pack(
            side="left", padx=(12, 0)
        )

    # ---- stems
    def _build_stems(self, fonts):
        c = card(self, 1, "Stems")
        self.count_hint = tk.StringVar()
        ttk.Label(c.top, textvariable=self.count_hint, style="Muted.TLabel").pack(side="left", padx=(10, 0))
        self.clear_btn = ttk.Button(c.top, text="Clear all", style="Small.TButton", command=self.clear_stems)
        self.clear_btn.pack(side="right")
        self.add_btn = ttk.Button(c.top, text="Add stems...", style="Small.TButton", command=self.add_files)
        self.add_btn.pack(side="right", padx=(0, 6))
        self.table = StemsTable(
            c,
            fonts,
            on_select=self.select,
            on_play=self._play,
            on_remove=self.remove,
            on_type=self.set_type,
        )
        self.table.grid(row=1, column=0, columnspan=3, sticky="ew")

    def add_files(self):
        chosen = filedialog.askopenfilenames(
            title="Choose stems",
            filetypes=[("Audio", "*.wav *.mp3 *.flac *.aif *.aiff *.ogg *.m4a"), ("All files", "*.*")],
        )
        known = {s.path for s in self.stems}
        new = [Stem(f) for f in chosen if f not in known]
        if not new:
            return
        self.stems.extend(new)
        self.refresh(select=len(self.stems) - len(new))

    def remove(self, index):
        if not 0 <= index < len(self.stems):
            return
        self.stems.pop(index)
        sel = self.selected or 0
        if index < sel:
            sel -= 1  # the selected stem moved up one row
        self.refresh(select=min(sel, len(self.stems) - 1) if self.stems else None)

    def clear_stems(self):
        self.stems.clear()
        self.refresh(select=None)

    def set_type(self, index, stem_type):
        self.stems[index].stem_type = stem_type
        if index == self.selected:
            self.card.show(self.stems[index], len(self.stems))
        self.on_change()

    def select(self, index):
        if index is None or not self.stems:
            self.selected = None
            self.card.show(None)
        else:
            self.selected = index
            self.card.show(self.stems[index], len(self.stems))
        self.table.select(self.selected)
        self.on_change()

    def _play(self, index):
        self.select(index)
        self.on_play()

    def refresh(self, select=None):
        """Rebuild the rows after stems were added or removed."""
        if select is None and self.stems:
            select = 0
        self.table.set_stems(self.stems, select)
        n = len(self.stems)
        self.count_hint.set(f"{n} stem{'s' if n != 1 else ''} · each with its own settings" if n else "")
        self.select(select if n else None)

    def selected_stem(self):
        if self.selected is None or not self.stems:
            return None
        return self.stems[self.selected]

    def apply_to_all(self):
        src = self.selected_stem()
        if src is None:
            return
        for stem in self.stems:
            if stem is not src:
                stem.copy_settings_from(src)
        self.on_change(f"Applied {src.name}'s settings to all {len(self.stems)} stems")

    def show_status(self, stem):
        if stem in self.stems:
            self.table.update_status(self.stems.index(stem), stem)

    # ---- reading the song settings
    def read_song(self):
        """Returns (dict, None) or (None, message explaining what's wrong)."""
        if not self.stems:
            return None, "Add at least one stem first"
        self.card.apply_typed_sensitivity()
        try:
            bpm = float(self.bpm_var.get())
            if not 40 <= bpm <= 240:
                raise ValueError
        except ValueError:
            return None, "Enter a tempo between 40 and 240 BPM"
        return {"bpm": bpm, "grid": GRID_CHOICES[self.grid_var.get()], "grid_label": self.grid_var.get()}, None

    def set_tempo(self, bpm, source):
        self.bpm_var.set(f"{bpm:g}")
        self.tempo_hint.set(f"measured from {os.path.basename(source)}")

    def set_enabled(self, on):
        self.table.set_enabled(on)
        self.card.set_enabled(on)
        for b in (self.add_btn, self.clear_btn, self.detect_btn):
            b.state(["!disabled"] if on else ["disabled"])

    def reset(self):
        self.bpm_var.set("120")
        self.grid_var.set(DEFAULT_GRID)
        self.tempo_hint.set(TEMPO_HINT)
        for stem in self.stems:
            stem.reset()
        self.select(self.selected)
