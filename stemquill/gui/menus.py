"""Menu bar and keyboard shortcuts."""

import tkinter as tk
import webbrowser

from ..config import REPO_URL
from .pages import PAGES
from .theme import THEME as T


def _menu(parent):
    return tk.Menu(parent, tearoff=0, bg=T["card"], fg=T["text"], activebackground=T["accent"],
                   activeforeground=T["accent_text"], disabledforeground=T["muted"], bd=0)


def build_menu_bar(app):
    bar = _menu(app.root)

    m = _menu(bar)
    m.add_command(label="Add stems...", accelerator="Ctrl+O", command=app.convert_page.add_files)
    m.add_command(label="Remove selected", accelerator="Del", command=app.convert_page.remove_selected)
    m.add_command(label="Clear stems", command=app.convert_page.clear_files)
    m.add_separator()
    m.add_command(label="Save MIDI to folder...", command=app.output_page.pick_folder)
    m.add_command(label="Open output folder", command=app.open_folder)
    m.add_separator()
    m.add_command(label="Exit", accelerator="Ctrl+Q", command=app.quit)
    bar.add_cascade(label="File", menu=m)

    m = _menu(bar)
    m.add_command(label="Detect tempo", accelerator="Ctrl+T", command=app.tempo.start)
    m.add_command(label="Preview", accelerator="Ctrl+P", command=app.preview.start)
    m.add_command(label="Stop preview", accelerator="Esc", command=app.preview.stop)
    m.add_command(label="Convert to MIDI", accelerator="Ctrl+Enter", command=app.converter.start)
    m.add_separator()
    m.add_command(label="Reset settings to defaults", command=app.reset_settings)
    bar.add_cascade(label="Tools", menu=m)

    m = _menu(bar)
    for i, (key, text, _, _) in enumerate(PAGES, start=1):
        m.add_command(label=text, accelerator=f"Ctrl+{i}", command=lambda k=key: app.show_page(k))
    bar.add_cascade(label="View", menu=m)

    m = _menu(bar)
    m.add_command(label="How to use", accelerator="F1", command=lambda: app.show_page("help"))
    m.add_separator()
    m.add_command(label="Stemquill on GitHub", command=lambda: webbrowser.open(REPO_URL))
    m.add_command(label="Report a problem", command=lambda: webbrowser.open(REPO_URL + "/issues"))
    m.add_separator()
    m.add_command(label="About Stemquill", command=app.about)
    bar.add_cascade(label="Help", menu=m)

    app.root.configure(menu=bar)


def bind_shortcuts(app):
    root = app.root
    root.bind_all("<Control-o>", lambda e: app.convert_page.add_files())
    root.bind_all("<Control-t>", lambda e: app.tempo.start())
    root.bind_all("<Control-p>", lambda e: app.preview.start())
    root.bind_all("<Control-Return>", lambda e: app.converter.start())
    root.bind_all("<Control-q>", lambda e: app.quit())
    root.bind_all("<Escape>", lambda e: app.preview.stop())
    root.bind_all("<F1>", lambda e: app.show_page("help"))
    for i, (key, *_) in enumerate(PAGES, start=1):
        root.bind_all(f"<Control-Key-{i}>", lambda e, k=key: app.show_page(k))
