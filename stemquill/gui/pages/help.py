"""Help page: a scrolling quick guide plus links."""

import tkinter as tk
import webbrowser
from tkinter import ttk

from ...config import REPO_URL
from ..theme import THEME as T

HELP_TEXT = [
    ("h", "Quick start"),
    (
        "p",
        "1.  Drop your stems (or a folder of them) onto the window, or click Add stems... Each stem gets its "
        "own row; its type is read from the file name (Drums, Bass, Vocals, Other) and you can change it there.",
    ),
    (
        "p",
        "2.  Song: click Detect to measure the tempo from the selected stem, or type the BPM. Set your DAW "
        "project to the same tempo. Tempo and Snap to grid are shared by every stem.",
    ),
    (
        "p",
        "3.  Click a stem to see its own settings underneath: Sensitivity, Humanize and, for drum stems, "
        "which drums to write. Apply to all stems copies them to the rest.",
    ),
    (
        "p",
        "4.  Click Play on a stem's row to hear it before saving; it turns into Stop while it plays (Esc also "
        "stops). Tick Mix in the original stem to check the timing against the real audio.",
    ),
    (
        "p",
        "5.  Click Convert to MIDI. Each row shows when its file is saved as <name> - <type>.mid; if you change "
        "a setting afterwards it says 'changed · convert again'. Drag each file onto its track at bar 1.",
    ),
    ("h", "Stem settings"),
    ("p", "Sensitivity: slide right to catch quieter notes, left to cut junk notes. 0.80 is a good start."),
    (
        "p",
        "Snap to grid: Off keeps the original timing and is safest for AI-generated stems. "
        "1/16 note locks everything to the grid.",
    ),
    (
        "p",
        "Humanize: adds small timing and velocity changes so parts feel played. 20-40% is natural, "
        "and it works best with Snap to grid turned on.",
    ),
    ("h", "Drum maps"),
    (
        "p",
        "General MIDI: MT Power Drumkit 2, EZdrummer, Addictive Drums, Superior Drummer, "
        "Steven Slate Drums and most drum plugins.",
    ),
    (
        "p",
        "Pads in order: for pad samplers like FL Studio FPC, Ableton Drum Rack or MPC kits. Load "
        "your sounds from note 36 up: kick, snare, closed hat, open hat, low tom, mid tom, "
        "high tom, crash, ride.",
    ),
    ("p", "Custom: type any note into a drum's box. Your custom map is remembered for next time."),
    ("h", "Chords"),
    (
        "p",
        "Guitar, keys and synth stems use basic-pitch for chords when the Better chord detection option "
        "was ticked in the installer, and a simpler built-in mode otherwise. The History page shows which "
        "one was used. Run the installer again to add or remove it.",
    ),
    ("h", "Tips"),
    (
        "p",
        "Transcription is a starting point, not a finished part. Expect to fix some notes, "
        "especially toms, ghost notes and busy strumming.",
    ),
    ("p", "Cleaner stems give better results. Bleed from other instruments means extra notes."),
    (
        "p",
        "Crash and Ride start off because cymbals can bring back metallic sounds. "
        "If Hi-Hat op. is off, open hats are written as closed hats.",
    ),
    ("p", "The preview uses simple placeholder sounds. Your real instruments will sound much better."),
    ("h", "Keyboard shortcuts"),
    ("k", "Ctrl+O\tAdd stems"),
    ("k", "Ctrl+T\tDetect tempo"),
    ("k", "Ctrl+P\tPreview"),
    ("k", "Esc\tStop playback"),
    ("k", "Ctrl+Enter\tConvert to MIDI"),
    ("k", "Ctrl+1 to 4\tSwitch pages"),
    ("k", "F1\tHelp"),
]


class HelpPage(ttk.Frame):
    def __init__(self, parent, fonts, on_about):
        super().__init__(parent)
        F = fonts
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        box = ttk.Frame(self, style="Card.TFrame", padding=(6, 6))
        box.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)
        text = tk.Text(
            box,
            bg=T["card"],
            fg=T["text"],
            relief="flat",
            highlightthickness=0,
            wrap="word",
            font=F["body"],
            padx=14,
            pady=8,
            cursor="arrow",
            spacing1=2,
            spacing3=4,
            tabs=("130p",),
        )
        scroll = ttk.Scrollbar(box, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        text.tag_configure("h", font=F["h"], foreground=T["accent"], spacing1=12, spacing3=4)
        text.tag_configure("p", foreground=T["text"], lmargin1=4, lmargin2=4)
        text.tag_configure("k", foreground=T["muted"], lmargin1=4, font=F["body"])
        for tag, line in HELP_TEXT:
            text.insert("end", line + "\n", tag)
        text.configure(state="disabled")

        links = ttk.Frame(self)
        links.grid(row=1, column=0, sticky="w")
        ttk.Button(links, text="Stemquill on GitHub", command=lambda: webbrowser.open(REPO_URL)).pack(side="left")
        ttk.Button(links, text="Report a problem", command=lambda: webbrowser.open(REPO_URL + "/issues")).pack(
            side="left", padx=8
        )
        ttk.Button(links, text="About", command=on_about).pack(side="left")
