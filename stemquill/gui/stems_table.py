"""The stems list: one row per stem with its own Play button, type, status and remove button."""

import tkinter as tk
from tkinter import ttk

from ..config import STEM_TYPES
from .theme import THEME as T

ROW_HEIGHT = 38
VISIBLE_ROWS = 5
STATUS_COLORS = {"muted": "muted", "busy": "accent", "ok": "ok", "warn": "warn"}
# Pixel widths shared by the heading and every row so the columns line up: Play, Stem, Type, Status, Remove
COLUMNS = [("", 72), ("Stem", 260), ("Type", 130), ("Status", 0), ("", 96)]
NAME_CHARS = 32


def _columns(frame):
    for i, (_, width) in enumerate(COLUMNS):
        frame.columnconfigure(i, minsize=width, weight=1 if width == 0 else 0)


def short_name(name):
    return name if len(name) <= NAME_CHARS else name[: NAME_CHARS - 3] + "..."


class StemsTable(ttk.Frame):
    """Rows are rebuilt when stems are added or removed; selection and status update in place."""

    def __init__(self, parent, fonts, on_select, on_play, on_remove, on_type):
        super().__init__(parent, style="Card.TFrame")
        self.F = fonts
        self.on_select, self.on_play, self.on_remove, self.on_type = on_select, on_play, on_remove, on_type
        self.rows = []
        self.selected = None
        self.enabled = True
        self.columnconfigure(0, weight=1)

        head = tk.Frame(self, bg=T["card"])
        head.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        _columns(head)
        for i, (text, _) in enumerate(COLUMNS):
            tk.Label(head, text=text, bg=T["card"], fg=T["muted"], font=fonts["small"], anchor="w").grid(
                row=0, column=i, sticky="w"
            )

        self.canvas = tk.Canvas(self, bg=T["field"], highlightthickness=0, height=ROW_HEIGHT * 2)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.body = tk.Frame(self.canvas, bg=T["field"])
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        for w in (self.canvas, self.body):
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", self._wheel)
            w.bind("<Button-5>", self._wheel)

        self.playing = None
        self.empty = tk.Label(
            self.canvas,
            text="Drop stems here, or click Add stems... (Ctrl+O).\nThe type is read from the file name: "
            "Drums, Bass, Vocals, Other.",
            justify="center",
            bg=T["field"],
            fg=T["muted"],
            font=fonts["body"],
        )

    # ---- building rows
    def set_stems(self, stems, selected):
        for row in self.rows:
            row["frame"].destroy()
        self.rows = []
        for i, stem in enumerate(stems):
            self.rows.append(self._make_row(i, stem))
        n = len(stems)
        visible = min(max(n, 2), VISIBLE_ROWS)
        self.canvas.configure(height=ROW_HEIGHT * visible)
        if n > VISIBLE_ROWS:
            self.scroll.grid(row=1, column=1, sticky="ns")
        else:
            self.scroll.grid_remove()
            self.canvas.yview_moveto(0)
        if n:
            self.empty.place_forget()
        else:
            self.empty.place(relx=0.5, rely=0.5, anchor="center")
        self.select(selected)
        self.set_enabled(self.enabled)
        self.set_playing(self.playing if self.playing is not None and self.playing < n else None)

    def _make_row(self, i, stem):
        F = self.F
        frame = tk.Frame(self.body, bg=T["field"], height=ROW_HEIGHT)
        frame.pack(fill="x")
        frame.grid_propagate(False)
        frame.rowconfigure(0, weight=1)
        _columns(frame)
        play = ttk.Button(frame, text="Play", style="Small.TButton", width=5, command=lambda: self.on_play(i))
        play.grid(row=0, column=0, sticky="w", padx=(6, 0))
        name = tk.Label(frame, text=short_name(stem.name), bg=T["field"], fg=T["text"], font=F["btn"], anchor="w")
        name.grid(row=0, column=1, sticky="ew")
        type_var = tk.StringVar(value=stem.stem_type)
        box = ttk.Combobox(frame, textvariable=type_var, values=STEM_TYPES, state="readonly", width=9)
        box.grid(row=0, column=2, sticky="w")
        box.bind("<<ComboboxSelected>>", lambda e: self.on_type(i, type_var.get()))
        status = tk.Label(frame, text=stem.status, bg=T["field"], font=F["body"], anchor="w")
        status.grid(row=0, column=3, sticky="ew")
        remove = ttk.Button(frame, text="Remove", style="Small.TButton", command=lambda: self.on_remove(i))
        remove.grid(row=0, column=4, sticky="e", padx=(0, 8))
        row = {"frame": frame, "name": name, "status": status, "play": play, "remove": remove, "box": box}
        for w in (frame, name, status):
            w.bind("<Button-1>", lambda e: self.on_select(i))
            w.bind("<MouseWheel>", self._wheel)
            w.bind("<Button-4>", self._wheel)
            w.bind("<Button-5>", self._wheel)
        self._paint_status(row, stem)
        return row

    # ---- updating in place
    def select(self, index):
        self.selected = index
        for i, row in enumerate(self.rows):
            bg = T["sel"] if i == index else T["field"]
            for key in ("frame", "name", "status"):
                row[key].configure(bg=bg)
        if index is not None and index < len(self.rows):
            self._scroll_into_view(index)

    def update_status(self, index, stem):
        if 0 <= index < len(self.rows):
            self._paint_status(self.rows[index], stem)

    def _paint_status(self, row, stem):
        row["status"].configure(text=stem.status, fg=T[STATUS_COLORS.get(stem.status_kind, "muted")])

    def set_enabled(self, on):
        self.enabled = on
        for row in self.rows:
            for key in ("play", "remove"):
                row[key].state(["!disabled"] if on else ["disabled"])
            row["box"].state(["!disabled", "readonly"] if on else ["disabled"])

    def set_playing(self, index):
        """The row being previewed shows Stop instead of Play."""
        self.playing = index
        for i, row in enumerate(self.rows):
            row["play"].configure(text="Stop" if i == index else "Play")

    def set_drop_highlight(self, on):
        """Light up the list while files are dragged over the window."""
        self.canvas.configure(bg=T["sel"] if on else T["field"])
        self.empty.configure(bg=T["sel"] if on else T["field"])

    # ---- scrolling
    def _wheel(self, event):
        if len(self.rows) <= VISIBLE_ROWS:
            return
        step = -1 if (getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0) else 1
        self.canvas.yview_scroll(step, "units")

    def _scroll_into_view(self, index):
        n = len(self.rows)
        if n <= VISIBLE_ROWS:
            return
        top, bottom = self.canvas.yview()
        row_top, row_bottom = index / n, (index + 1) / n
        if row_top < top:
            self.canvas.yview_moveto(row_top)
        elif row_bottom > bottom:
            self.canvas.yview_moveto(row_bottom - (bottom - top))
