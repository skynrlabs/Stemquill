"""Small building blocks shared by the pages."""

import tkinter as tk
from tkinter import ttk

from .theme import THEME as T


def card(parent, row, title, hint=None, grow=False):
    """A rounded-look panel with a bold title and an optional grey hint."""
    c = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
    c.grid(row=row, column=0, sticky="nsew", pady=(0, 12))
    if grow:
        parent.rowconfigure(row, weight=1)
    c.columnconfigure(1, weight=1)
    top = ttk.Frame(c, style="Card.TFrame")
    top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
    ttk.Label(top, text=title, style="Head.TLabel").pack(side="left")
    if hint:
        ttk.Label(top, text=hint, style="Muted.TLabel").pack(side="left", padx=(10, 0))
    c.top = top  # the title row, so a page can add a small button on the right
    return c


def slider(parent, var, lo, hi, step, command=None):
    return tk.Scale(
        parent,
        from_=lo,
        to=hi,
        resolution=step,
        variable=var,
        orient="horizontal",
        length=260,
        showvalue=False,
        command=command,
        bg=T["accent"],
        activebackground=T["accent_hover"],
        troughcolor=T["field"],
        highlightthickness=0,
        bd=0,
        sliderrelief="flat",
        sliderlength=18,
        width=10,
    )


class ScrollArea(ttk.Frame):
    """A page that scrolls when it's taller than the window, so nothing is ever hidden.

    Put the content in .inner. The content keeps its natural height (so it can grow as stems are
    added); when that's taller than the area, a scrollbar appears and the mouse wheel scrolls it
    from anywhere over the page.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, bg=T["bg"], highlightthickness=0, bd=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.inner = ttk.Frame(self.canvas)
        self.inner.columnconfigure(0, weight=1)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        # the canvas changes size with the window; the inner frame changes size with its content
        self.canvas.bind("<Configure>", lambda e: self._fit())
        self.inner.bind("<Configure>", lambda e: self._fit())
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._wheel, add="+")

    def needs_scroll(self):
        return self.inner.winfo_reqheight() > self.canvas.winfo_height() + 1

    def _fit(self):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width <= 1:
            return
        self.canvas.itemconfigure(self._win, width=width)  # height stays the content's own
        need = self.inner.winfo_reqheight()
        self.canvas.configure(scrollregion=(0, 0, width, max(height, need)))
        if need > height + 1:
            self.bar.grid(row=0, column=1, sticky="ns")
        else:
            self.bar.grid_remove()
            self.canvas.yview_moveto(0)

    def _under_pointer(self, event):
        """True when the wheel turned over this area (or anything inside it) and it's showing."""
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):  # e.g. over a combobox's drop-down list
            return False
        while w is not None:
            if w is self:
                return self.winfo_viewable()
            w = w.master
        return False

    def _wheel(self, event):
        if not self.needs_scroll() or not self._under_pointer(event):
            return
        step = -1 if (getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0) else 1
        self.canvas.yview_scroll(step, "units")
