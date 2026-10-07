"""The main window: sidebar, page area and action bar, plus the shared plumbing the journeys use."""

import os
import queue
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from ..config import ASSETS_DIR, load_settings, save_settings
from .action_bar import ActionBar
from .dialogs import show_about
from .journeys import ConvertJourney, PreviewJourney, TempoJourney
from .menus import bind_shortcuts, build_menu_bar
from .pages import PAGES, ConvertPage, DrumKitPage, HelpPage, OutputPage
from .sidebar import Sidebar
from .theme import THEME, apply_styles, make_fonts

IS_WINDOWS = sys.platform.startswith("win")


class StemquillApp:
    def __init__(self, root):
        self.root = root
        self.busy = False
        self.updates = queue.Queue()  # background threads -> window
        self._setup_window()
        self.fonts = make_fonts()
        apply_styles(root, self.fonts)
        self.images = self._load_images()

        self.converter = ConvertJourney(self)
        self.preview = PreviewJourney(self)
        self.tempo = TempoJourney(self)

        self._build_layout()
        build_menu_bar(self)
        bind_shortcuts(self)
        self._wire_buttons()
        root.protocol("WM_DELETE_WINDOW", self.quit)

        self.convert_page.refresh_list()
        self.show_page("convert")
        self._poll()

    # ---- window setup
    def _setup_window(self):
        root = self.root
        root.title("Stemquill")
        root.configure(bg=THEME["bg"])
        root.minsize(900, 660)
        root.geometry("1000x740")
        ico = os.path.join(ASSETS_DIR, "stemquill.ico")
        if IS_WINDOWS and os.path.exists(ico):
            try:
                root.iconbitmap(default=ico)
            except tk.TclError:
                pass

    def _load_images(self):
        images = {}
        try:
            images["app"] = tk.PhotoImage(file=os.path.join(ASSETS_DIR, "icon.png"))
            images["small"] = tk.PhotoImage(file=os.path.join(ASSETS_DIR, "icon-32.png"))
            images["about"] = tk.PhotoImage(file=os.path.join(ASSETS_DIR, "icon-64.png"))
            self.root.iconphoto(True, images["app"])
        except tk.TclError:
            pass
        return images

    def _build_layout(self):
        root = self.root
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        self.sidebar = Sidebar(root, [(k, label) for k, label, _, _ in PAGES], self.show_page, self.fonts,
                               self.images.get("small"))
        self.sidebar.grid(row=0, column=0, sticky="ns")

        main = ttk.Frame(root, padding=(22, 16, 22, 12))
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.page_title = tk.StringVar()
        self.page_sub = tk.StringVar()
        ttk.Label(header, textvariable=self.page_title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, textvariable=self.page_sub, style="Sub.TLabel").pack(anchor="w")

        box = ttk.Frame(main)
        box.grid(row=1, column=0, sticky="nsew")
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        self.convert_page = ConvertPage(box, self.fonts, self._on_stems_changed)
        self.drum_page = DrumKitPage(box)
        self.output_page = OutputPage(box)
        self.help_page = HelpPage(box, self.fonts, self.about)
        self.pages = {"convert": self.convert_page, "drums": self.drum_page,
                      "output": self.output_page, "help": self.help_page}
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        self.action = ActionBar(main)
        self.action.grid(row=2, column=0, sticky="ew", pady=(4, 0))

    def _wire_buttons(self):
        self.action.play_btn.configure(command=self.preview.start)
        self.action.stop_btn.configure(command=self.preview.stop)
        self.action.convert_btn.configure(command=self.converter.start)
        self.action.open_btn.configure(command=self.open_folder)
        self.convert_page.detect_btn.configure(command=self.tempo.start)

    # ---- navigation
    def show_page(self, key):
        self.pages[key].tkraise()
        for k, _, title, sub in PAGES:
            if k == key:
                self.page_title.set(title)
                self.page_sub.set(sub)
        self.sidebar.set_active(key)

    def _on_stems_changed(self):
        n = len(self.convert_page.files)
        self.sidebar.set_label("convert", f"Convert  ({n})" if n else "Convert")
        self.drum_page.update_state(self.convert_page.type_var.get())

    # ---- plumbing shared by the journeys
    def post(self, fn):
        """Run fn on the window's thread (safe to call from a background thread)."""
        self.updates.put(fn)

    def log(self, msg):
        self.post(lambda: self.convert_page.write_log(msg))

    def say(self, msg, color="muted"):
        self.action.say(msg, color)

    def set_busy(self, on):
        self.busy = on
        for b in self.action.busy_buttons() + [self.convert_page.detect_btn]:
            b.state(["disabled"] if on else ["!disabled"])

    def _poll(self):
        try:
            while True:
                self.updates.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def collect(self):
        """Gather and check every setting from all pages. Returns a dict, or None after saying what's wrong."""
        c, err = self.convert_page.read_settings()
        if err:
            self.say(err, "warn")
            self.show_page("convert")
            return None
        drum_map, err = self.drum_page.current_map()
        if err:
            self.say(err, "warn")
            self.show_page("drums")
            return None
        map_key = self.drum_page.map_key()
        settings = load_settings()
        settings["drum_map"] = map_key
        if map_key == "Custom":
            settings["custom_map"] = drum_map
        save_settings(settings)
        c.update(parts=self.drum_page.selected_parts(), drum_map=drum_map, map_key=map_key)
        return c

    # ---- commands
    def open_folder(self):
        d = self.converter.last_out_dir or self.output_page.out_dir
        if not d:
            self.say("Convert something first, then Open folder", "warn")
            return
        if IS_WINDOWS:
            os.startfile(d)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", d])
        else:
            subprocess.Popen(["xdg-open", d])

    def reset_settings(self):
        self.convert_page.reset()
        self.drum_page.reset()
        self.output_page.reset()
        self.action.with_original.set(True)
        self.say("Settings reset to defaults", "ok")

    def about(self):
        show_about(self.root, self.fonts, self.images.get("about"))

    def quit(self):
        self.preview.player.stop()
        self.root.destroy()


def run_gui():
    if IS_WINDOWS:
        try:  # show Stemquill's own icon on the taskbar instead of Python's
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SkynrLabs.Stemquill")
        except Exception:
            pass
    root = tk.Tk()
    StemquillApp(root)
    root.mainloop()
