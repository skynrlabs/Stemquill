"""Keyboard shortcuts. (Navigation lives in the sidebar, so there's no separate menu bar.)"""

from .pages import PAGES


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
