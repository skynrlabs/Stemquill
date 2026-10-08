"""The Activity feed on the Convert page: a short, readable history of what happened.

The journeys report results here (one entry per action, one line per stem) instead of
showing the engine's step-by-step output, which is meant for the command line.
"""

import os
import time
import tkinter as tk
from tkinter import ttk

from ..config import DRUM_NOTES, note_name
from .theme import THEME as T

DRUM_NAMES = {"kick": "Kick", "snare": "Snare", "hihat": "Hi-hat", "openhat": "Open hat",
              "tom_hi": "High tom", "tom_mid": "Mid tom", "tom_low": "Low tom", "crash": "Crash", "ride": "Ride"}


def describe(result):
    """One plain-English line about a transcribed stem, e.g. 'Kick 307 · Snare 268 · Hi-hat 9'."""
    notes = result["notes"]
    if result["stem_type"] == "drums":
        part_for_note = {}
        for part, n in result["drum_map"].items():
            part_for_note.setdefault(n, part)
        counts = {}
        for _, _, n, _ in notes:
            part = part_for_note.get(n)
            counts[part] = counts.get(part, 0) + 1
        found = [f"{DRUM_NAMES[p]} {counts[p]}" for p in DRUM_NOTES if counts.get(p)]
        return " · ".join(found) or "no drum hits found"
    if not notes:
        return "no notes found"
    pitches = [n for _, _, n, _ in notes]
    line = f"range {note_name(min(pitches))} to {note_name(max(pitches))}"
    if result.get("engine") == "basic-pitch":
        line += " · chords by basic-pitch"
    elif result.get("engine") == "built-in":
        line += " · built-in chord detection"
    return line


class ActivityLog:
    def __init__(self, parent, fonts):
        F = fonts
        self.frame = tk.Frame(parent, bg=T["field"])
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)
        self.text = tk.Text(self.frame, height=4, bg=T["field"], fg=T["text"], relief="flat", font=F["body"],
                            highlightthickness=0, padx=12, pady=10, wrap="word", cursor="arrow",
                            spacing1=1, spacing3=1)
        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        t = self.text
        t.tag_configure("time", foreground=T["muted"], font=F["small"])
        t.tag_configure("title", foreground=T["text"], font=F["h"], spacing1=8)
        t.tag_configure("name", foreground=T["text"], font=F["btn"])
        t.tag_configure("settings", foreground=T["muted"], lmargin1=44, lmargin2=44, spacing3=4)
        t.tag_configure("stem", lmargin1=12, lmargin2=34)
        t.tag_configure("detail", foreground=T["muted"], lmargin1=34, lmargin2=34)
        t.tag_configure("ok", foreground=T["ok"], font=F["btn"])
        t.tag_configure("warn", foreground=T["warn"], font=F["btn"])
        t.tag_configure("muted", foreground=T["muted"])
        t.tag_configure("summary", foreground=T["ok"], spacing1=4)
        t.tag_configure("summary_warn", foreground=T["warn"], spacing1=4)
        t.configure(state="disabled")
        self._empty = True
        self._placeholder()

    def grid(self, **kw):
        self.frame.grid(**kw)

    # ---- low-level writing (the widget is read-only for the user)
    def _write(self, *parts):
        t = self.text
        t.configure(state="normal")
        if self._empty:
            t.delete("1.0", "end")
            self._empty = False
        for text, tag in parts:
            t.insert("end", text, tag)
        t.configure(state="disabled")
        t.see("end")

    def _placeholder(self):
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", "Results from Detect, Play and Convert show up here.", "muted")
        t.configure(state="disabled")
        self._empty = True

    def clear(self):
        self._placeholder()

    # ---- entries
    def action(self, title, detail=None):
        """Start a new entry, e.g. 'Convert 3 stems' with the settings underneath."""
        lead = "" if self._empty else "\n"
        parts = [(lead + time.strftime("%H:%M") + "   ", "time"), (title + "\n", "title")]
        if detail:
            parts.append((detail + "\n", "settings"))
        self._write(*parts)

    def stem_ok(self, name, line, extra=None):
        self._write(("•  ", ("ok", "stem")), (name, ("name", "stem")), ("   " + line + "\n", ("muted", "stem")))
        if extra:
            self._write((extra + "\n", "detail"))

    def stem_problem(self, name, reason):
        self._write(("!  ", ("warn", "stem")), (name, ("name", "stem")), ("   " + reason + "\n", ("muted", "stem")))

    def summary(self, text, good=True):
        self._write((text + "\n", "summary" if good else "summary_warn"))


def short_path(path, keep=2):
    """Last couple of folders of a path, so the feed doesn't wrap on long paths."""
    parts = os.path.normpath(path).split(os.sep)
    return path if len(parts) <= keep + 1 else os.sep.join(["..."] + parts[-keep:])
