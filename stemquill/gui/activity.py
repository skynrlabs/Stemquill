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

DRUM_NAMES = {
    "kick": "Kick",
    "snare": "Snare",
    "hihat": "Hi-hat",
    "openhat": "Open hat",
    "tom_hi": "High tom",
    "tom_mid": "Mid tom",
    "tom_low": "Low tom",
    "crash": "Crash",
    "ride": "Ride",
}


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
    """A scrollable table: one expandable row per action, with a row per stem underneath.

    The newest action is at the top and opened; older ones fold away so the table stays tidy.
    Double-click a converted stem to open the folder its MIDI file was saved in.
    """

    COLUMNS = ("time", "result", "details", "saved")
    PLACEHOLDER = "Results from Detect, Play and Convert show up here."

    def __init__(self, parent, fonts, on_open=None):
        self.on_open = on_open
        self.frame = tk.Frame(parent, bg=T["field"])
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(self.frame, columns=self.COLUMNS, style="Activity.Treeview", selectmode="browse")
        self.tree = tree
        tree.heading("#0", text="Action / stem", anchor="w")
        tree.heading("time", text="Time", anchor="w")
        tree.heading("result", text="Result", anchor="w")
        tree.heading("details", text="Details", anchor="w")
        tree.heading("saved", text="Saved as", anchor="w")
        # Narrow fixed columns on the left; Details and Saved as share whatever room is left
        tree.column("#0", width=180, minwidth=140, stretch=False)
        tree.column("time", width=52, minwidth=48, stretch=False)
        tree.column("result", width=140, minwidth=110, stretch=False)
        tree.column("details", width=220, minwidth=120, stretch=True)
        tree.column("saved", width=160, minwidth=110, stretch=True)
        scroll = ttk.Scrollbar(self.frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        tree.tag_configure("action", font=fonts["btn"], foreground=T["text"])
        tree.tag_configure("stem", foreground=T["text"])
        tree.tag_configure("problem", foreground=T["warn"])
        tree.tag_configure("summary", foreground=T["ok"])
        tree.tag_configure("summary_warn", foreground=T["warn"])
        tree.tag_configure("muted", foreground=T["muted"])
        tree.bind("<Double-1>", self._on_double_click)

        self._saved = {}  # row id -> full path of the saved MIDI file
        self._current = None  # the action rows are being added under
        self._placeholder()

    def grid(self, **kw):
        self.frame.grid(**kw)

    def _placeholder(self):
        self.tree.delete(*self.tree.get_children())
        self._saved.clear()
        self._current = None
        self.tree.insert("", "end", iid="placeholder", text=self.PLACEHOLDER, tags=("muted",))

    def _drop_placeholder(self):
        if self.tree.exists("placeholder"):
            self.tree.delete("placeholder")

    def clear(self):
        self._placeholder()

    # ---- entries
    def action(self, title, detail=""):
        """Start a new action at the top of the table, e.g. 'Convert 3 stems' with its settings."""
        self._drop_placeholder()
        for item in self.tree.get_children():
            self.tree.item(item, open=False)  # fold older actions away
        self._current = self.tree.insert(
            "", 0, text=title, values=(time.strftime("%H:%M"), "", detail, ""), open=True, tags=("action",)
        )
        self.tree.see(self._current)
        return self._current

    def _child(self, text, values, tags):
        if self._current is None:
            self.action("Activity")
        row = self.tree.insert(self._current, "end", text=text, values=values, tags=tags)
        self.tree.see(row)
        self.tree.see(self._current)  # keep the newest action's title in view at the top
        return row

    def stem(self, name, result, details="", saved=None):
        """A stem that worked: what it is, what was found, and the file it was saved to (if any)."""
        row = self._child(name, ("", result, details, os.path.basename(saved) if saved else ""), ("stem",))
        if saved:
            self._saved[row] = saved
        return row

    def problem(self, name, reason):
        """A stem that was skipped or failed."""
        return self._child(name, ("", reason, "", ""), ("problem",))

    def summary(self, label, result="", details="", good=True):
        """The closing row of an action, e.g. 'Done | 3 of 4 saved | in ...\\Stems'."""
        return self._child(label, ("", result, details, ""), ("summary" if good else "summary_warn",))

    # ---- double-click opens the folder of a saved file
    def _on_double_click(self, event):
        row = self.tree.identify_row(event.y)
        if row in self._saved and self.on_open:
            self.on_open(os.path.dirname(self._saved[row]))

    # ---- for tests and copying: the table as plain text, top to bottom
    def as_text(self):
        lines = []

        def walk(item, depth):
            values = [v for v in self.tree.item(item, "values") if v]
            lines.append("  " * depth + " | ".join([self.tree.item(item, "text"), *map(str, values)]))
            for child in self.tree.get_children(item):
                walk(child, depth + 1)

        for item in self.tree.get_children():
            walk(item, 0)
        return "\n".join(lines)


def short_path(path, keep=2):
    """Last couple of folders of a path, so the feed doesn't wrap on long paths."""
    parts = os.path.normpath(path).split(os.sep)
    return path if len(parts) <= keep + 1 else os.sep.join(["..."] + parts[-keep:])
