"""A small "Starting Stemquill..." window, shown before the heavy audio libraries load.

The first start after installing can take a minute (Windows scans every new file, and the audio
library prepares its code), so without this it looks as if the app never opened. Only tkinter is
imported here, so the splash appears within a second or two.
"""

import contextlib
import os
import sys
import tkinter as tk

from .config import ASSETS_DIR

BG, TEXT, MUTED, ACCENT = "#252a30", "#e8eaed", "#9aa3ad", "#18c6cc"  # the app's theme colours


def set_app_id():
    """Show Stemquill's own icon on the Windows taskbar instead of Python's (before any window)."""
    if sys.platform.startswith("win"):
        with contextlib.suppress(Exception):
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SkynrLabs.Stemquill")


def show():
    """Create the app's (hidden) main window and a splash over it. Returns the main window."""
    set_app_id()
    root = tk.Tk()
    root.withdraw()
    splash = tk.Toplevel(root, bg=BG, highlightthickness=1, highlightbackground=ACCENT)
    splash.overrideredirect(True)  # no title bar
    splash.attributes("-topmost", True)
    with contextlib.suppress(tk.TclError):
        splash.icon = tk.PhotoImage(file=os.path.join(ASSETS_DIR, "icon-64.png"))
        tk.Label(splash, image=splash.icon, bg=BG).pack(pady=(26, 8))
    tk.Label(splash, text="Stemquill", bg=BG, fg=TEXT, font=("Segoe UI", 18, "bold")).pack(padx=60)
    tk.Label(splash, text="Starting...", bg=BG, fg=ACCENT, font=("Segoe UI", 11)).pack(pady=(4, 2))
    tk.Label(
        splash,
        text="The first start after installing can take a minute",
        bg=BG,
        fg=MUTED,
        font=("Segoe UI", 9),
    ).pack(padx=30, pady=(0, 24))
    splash.update_idletasks()
    w, h = splash.winfo_reqwidth(), splash.winfo_reqheight()
    x = (splash.winfo_screenwidth() - w) // 2
    y = (splash.winfo_screenheight() - h) // 3
    splash.geometry(f"{w}x{h}+{x}+{y}")
    splash.update()
    root.splash = splash
    return root


def close(root):
    """Remove the splash and show the main window."""
    splash = getattr(root, "splash", None)
    if splash is not None:
        with contextlib.suppress(tk.TclError):
            splash.destroy()
        root.splash = None
    root.deiconify()
    root.lift()
    with contextlib.suppress(tk.TclError):
        root.focus_force()
