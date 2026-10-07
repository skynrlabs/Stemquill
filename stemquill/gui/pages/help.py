"""Help page: a scrolling quick guide plus links."""

import tkinter as tk
import webbrowser
from tkinter import ttk

from ...config import REPO_URL
from ..theme import THEME as T

HELP_TEXT = [
    ("h", "Quick start"),
    ("p", "1.  Click Add stems... and pick your audio files. The stem type is read from the file name "
          "(Drums, Bass, Vocals, Other), or set it yourself under Stem type."),
    ("p", "2.  Click Detect to measure the tempo, or type the BPM if you know it. Set your DAW project "
          "to the same tempo."),
    ("p", "3.  Click Play to hear the result before saving. Tick Mix in the original stem to check "
          "the timing against the real audio."),
    ("p", "4.  Adjust Sensitivity, Humanize or the Drum Kit page, and play again until it sounds right."),
    ("p", "5.  Click Convert to MIDI. Each stem becomes <name> - <type>.mid. Drag it onto your "
          "instrument track at bar 1."),
    ("h", "Settings"),
    ("p", "Sensitivity: slide right to catch quieter notes, left to cut junk notes. 0.80 is a good start."),
    ("p", "Snap to grid: Off keeps the original timing and is safest for AI-generated stems. "
          "1/16 note locks everything to the grid."),
    ("p", "Humanize: adds small timing and velocity changes so parts feel played. 20-40% is natural, "
          "and it works best with Snap to grid turned on."),
    ("h", "Drum maps"),
    ("p", "General MIDI: MT Power Drumkit 2, EZdrummer, Addictive Drums, Superior Drummer, "
          "Steven Slate Drums and most drum plugins."),
    ("p", "Pads in order: for pad samplers like FL Studio FPC, Ableton Drum Rack or MPC kits. Load "
          "your sounds from note 36 up: kick, snare, closed hat, open hat, low tom, mid tom, "
          "high tom, crash, ride."),
    ("p", "Custom: type any note into a drum's box. Your custom map is remembered for next time."),
    ("h", "Tips"),
    ("p", "Transcription is a starting point, not a finished part. Expect to fix some notes, "
          "especially toms, ghost notes and busy strumming."),
    ("p", "Cleaner stems give better results. Bleed from other instruments means extra notes."),
    ("p", "Crash and Ride start off because cymbals can bring back metallic sounds."),
    ("p", "The preview uses simple placeholder sounds. Your real instruments will sound much better."),
    ("h", "Keyboard shortcuts"),
    ("k", "Ctrl+O\tAdd stems"),
    ("k", "Ctrl+T\tDetect tempo"),
    ("k", "Ctrl+P\tPreview"),
    ("k", "Esc\tStop preview"),
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
        text = tk.Text(box, bg=T["card"], fg=T["text"], relief="flat", highlightthickness=0, wrap="word",
                       font=F["body"], padx=14, pady=8, cursor="arrow", spacing1=2, spacing3=4, tabs=("130p",))
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
        ttk.Button(links, text="Report a problem",
                   command=lambda: webbrowser.open(REPO_URL + "/issues")).pack(side="left", padx=8)
        ttk.Button(links, text="About", command=on_about).pack(side="left")
