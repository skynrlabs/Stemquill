"""Convert page: the stems list, conversion settings and the activity log."""

import os
import tkinter as tk
from tkinter import filedialog, ttk

from ...config import STEM_TYPES
from ...core import guess_type
from ..theme import THEME as T
from ..widgets import card, slider

GRID_CHOICES = {"Off (keep original timing)": 0, "1/8 note": 2, "1/8 triplet": 3,
                "1/16 note": 4, "1/32 note": 8}
DEFAULT_GRID = "Off (keep original timing)"
SENS_MIN, SENS_MAX, SENS_DEFAULT = 0.1, 1.5, 0.8
TEMPO_HINT = "click Detect to measure it from the selected stem"


class ConvertPage(ttk.Frame):
    def __init__(self, parent, fonts, on_stems_changed, on_reset):
        super().__init__(parent)
        self.on_reset = on_reset
        self.columnconfigure(0, weight=1)
        self.on_stems_changed = on_stems_changed
        self.files = []
        self.type_var = tk.StringVar(value="auto")
        self.bpm_var = tk.StringVar(value="120")
        self.grid_var = tk.StringVar(value=DEFAULT_GRID)
        self.sens_var = tk.DoubleVar(value=SENS_DEFAULT)
        self.sens_text = tk.StringVar(value=f"{SENS_DEFAULT:.2f}")
        self.human_var = tk.IntVar(value=0)
        self.human_text = tk.StringVar()
        self.tempo_hint = tk.StringVar(value=TEMPO_HINT)
        self._build_stems(fonts)
        self._build_settings()
        self._build_log(fonts)

    # ---- stems
    def _build_stems(self, F):
        c = card(self, 0, "Stems", "the type is read from the file name: Drums, Bass, Vocals, Other")
        self.listbox = tk.Listbox(c, height=4, bg=T["field"], fg=T["text"], selectbackground=T["accent"],
                                  selectforeground=T["accent_text"], highlightthickness=1,
                                  highlightbackground=T["line"], highlightcolor=T["accent"], relief="flat",
                                  font=F["body"], activestyle="none", selectmode="extended")
        self.listbox.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.listbox.bind("<Delete>", lambda e: self.remove_selected())
        btns = ttk.Frame(c, style="Card.TFrame")
        btns.grid(row=1, column=2, sticky="ns", padx=(10, 0))
        ttk.Button(btns, text="Add stems...", command=self.add_files).pack(fill="x")
        ttk.Button(btns, text="Remove", command=self.remove_selected).pack(fill="x", pady=6)
        ttk.Button(btns, text="Clear", command=self.clear_files).pack(fill="x")

    def refresh_list(self):
        lb = self.listbox
        lb.delete(0, "end")
        for f in self.files:
            kind = self.type_var.get() if self.type_var.get() != "auto" else guess_type(f)
            lb.insert("end", f"  {os.path.basename(f)}    ·    {kind}")
        if not self.files:
            lb.insert("end", "  No stems yet. Click Add stems... or press Ctrl+O")
            lb.itemconfig(0, fg=T["muted"])
        self.on_stems_changed()

    def add_files(self):
        chosen = filedialog.askopenfilenames(
            title="Choose stems",
            filetypes=[("Audio", "*.wav *.mp3 *.flac *.aif *.aiff *.ogg *.m4a"), ("All files", "*.*")])
        for f in chosen:
            if f not in self.files:
                self.files.append(f)
        self.refresh_list()

    def remove_selected(self):
        for i in sorted(self.listbox.curselection(), reverse=True):
            if i < len(self.files):
                self.files.pop(i)
        self.refresh_list()

    def clear_files(self):
        self.files.clear()
        self.refresh_list()

    def selected_stem(self):
        """The highlighted stem, or the first one. Used by Preview and Detect."""
        sel = [i for i in self.listbox.curselection() if i < len(self.files)]
        return self.files[sel[0]] if sel else self.files[0]

    # ---- settings
    def _build_settings(self):
        c = card(self, 1, "Settings", "match the tempo to your DAW project")
        ttk.Button(c.top, text="Reset to defaults", style="Small.TButton",
                   command=lambda: self.on_reset()).pack(side="right")

        def row_label(r, text, hint=None):
            ttk.Label(c, text=text, style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=4, padx=(0, 16))
            if hint:
                ttk.Label(c, text=hint, style="Muted.TLabel").grid(row=r, column=2, sticky="w", padx=(12, 0))

        row_label(1, "Stem type", "auto reads the file name")
        box = ttk.Combobox(c, textvariable=self.type_var, values=["auto"] + STEM_TYPES, state="readonly", width=26)
        box.grid(row=1, column=1, sticky="w")
        box.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        row_label(2, "Tempo (BPM)")
        tempo = ttk.Frame(c, style="Card.TFrame")
        tempo.grid(row=2, column=1, columnspan=2, sticky="w")
        ttk.Spinbox(tempo, from_=40, to=240, increment=0.1, textvariable=self.bpm_var, width=8).pack(side="left")
        self.detect_btn = ttk.Button(tempo, text="Detect", width=8)
        self.detect_btn.pack(side="left", padx=(8, 0))
        ttk.Label(tempo, textvariable=self.tempo_hint, style="Muted.TLabel").pack(side="left", padx=(12, 0))

        row_label(3, "Snap to grid", "Off is safest for AI-generated stems")
        ttk.Combobox(c, textvariable=self.grid_var, values=list(GRID_CHOICES), state="readonly", width=26)\
            .grid(row=3, column=1, sticky="w")

        row_label(4, "Sensitivity")
        sens = ttk.Frame(c, style="Card.TFrame")
        sens.grid(row=4, column=1, columnspan=2, sticky="w")
        ttk.Label(sens, text="fewer notes", style="Muted.TLabel").pack(side="left")
        slider(sens, self.sens_var, SENS_MIN, SENS_MAX, 0.01,
               lambda v: self.sens_text.set(f"{float(v):.2f}")).pack(side="left", padx=8)
        ttk.Label(sens, text="more notes", style="Muted.TLabel").pack(side="left")
        sbox = ttk.Spinbox(sens, from_=SENS_MIN, to=SENS_MAX, increment=0.05, width=6,
                           textvariable=self.sens_text, command=self.apply_typed_sensitivity, format="%.2f")
        sbox.pack(side="left", padx=(14, 0))
        sbox.bind("<Return>", self.apply_typed_sensitivity)
        sbox.bind("<FocusOut>", self.apply_typed_sensitivity)

        self.human_var.trace_add("write", self._show_humanize)
        self._show_humanize()
        row_label(5, "Humanize")
        hum = ttk.Frame(c, style="Card.TFrame")
        hum.grid(row=5, column=1, columnspan=2, sticky="w")
        ttk.Label(hum, text="tight", style="Muted.TLabel").pack(side="left")
        slider(hum, self.human_var, 0, 100, 5).pack(side="left", padx=8)
        ttk.Label(hum, text="loose", style="Muted.TLabel").pack(side="left")
        ttk.Label(hum, textvariable=self.human_text, style="Value.TLabel").pack(side="left", padx=(14, 0))

    def apply_typed_sensitivity(self, *_):
        try:
            v = max(SENS_MIN, min(SENS_MAX, float(self.sens_text.get())))
        except ValueError:
            v = self.sens_var.get()
        self.sens_var.set(v)
        self.sens_text.set(f"{v:.2f}")

    def _show_humanize(self, *_):
        v = self.human_var.get()
        word = "off" if v == 0 else "subtle" if v <= 30 else "natural" if v <= 65 else "loose"
        self.human_text.set(f"{v}%  ({word})")

    def read_settings(self):
        """Returns (settings dict, None) or (None, message explaining what's wrong)."""
        if not self.files:
            return None, "Add at least one stem first"
        self.apply_typed_sensitivity()
        try:
            bpm = float(self.bpm_var.get())
            if not 40 <= bpm <= 240:
                raise ValueError
        except ValueError:
            return None, "Enter a tempo between 40 and 240 BPM"
        return {"stem_type": self.type_var.get(), "bpm": bpm, "grid": GRID_CHOICES[self.grid_var.get()],
                "grid_label": self.grid_var.get(), "sensitivity": self.sens_var.get(),
                "humanize": self.human_var.get() / 100.0}, None

    def set_tempo(self, bpm, source):
        self.bpm_var.set(f"{bpm:g}")
        self.tempo_hint.set(f"measured from {os.path.basename(source)}; set your DAW project to {bpm:g} BPM too")

    def reset(self):
        self.type_var.set("auto")
        self.bpm_var.set("120")
        self.grid_var.set(DEFAULT_GRID)
        self.sens_var.set(SENS_DEFAULT)
        self.sens_text.set(f"{SENS_DEFAULT:.2f}")
        self.human_var.set(0)
        self.tempo_hint.set(TEMPO_HINT)
        self.refresh_list()

    # ---- activity log
    def _build_log(self, F):
        c = card(self, 2, "Activity", grow=True)
        c.rowconfigure(1, weight=1)
        self.logbox = tk.Text(c, height=4, bg=T["field"], fg=T["muted"], insertbackground=T["text"],
                              relief="flat", font=F["mono"], highlightthickness=0, padx=10, pady=8, wrap="word")
        self.logbox.grid(row=1, column=0, columnspan=3, sticky="nsew")
        self.logbox.tag_configure("ok", foreground=T["ok"])
        self.logbox.tag_configure("warn", foreground=T["warn"])
        self.logbox.tag_configure("head", foreground=T["text"])

    def write_log(self, msg):
        tag = "ok" if msg.strip().startswith(("saved", "Done")) else \
              "warn" if ("Error" in msg or "skipped" in msg or "failed" in msg or "Nothing" in msg) else \
              "head" if "->" in msg else ""
        self.logbox.insert("end", msg + "\n", tag)
        self.logbox.see("end")

    def clear_log(self):
        self.logbox.delete("1.0", "end")
