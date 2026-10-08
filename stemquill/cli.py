"""Command line: python -m stemquill "Drums.wav" --bpm 121"""

import argparse
import os

from . import __version__
from .config import DEFAULT_DRUM_PARTS, DRUM_MAPS, DRUM_NOTES, STEM_TYPES
from .core import convert


def main():
    ap = argparse.ArgumentParser(description="Convert audio stems to MIDI.")
    ap.add_argument("--version", action="version", version=f"Stemquill {__version__}")
    ap.add_argument("stems", nargs="+", help="audio files (wav, mp3, flac...)")
    ap.add_argument("--type", default="auto", choices=["auto"] + STEM_TYPES)
    ap.add_argument("--bpm", type=float, help="song tempo (detected if left out)")
    ap.add_argument(
        "--grid", type=int, default=4, help="snap steps per beat: 4 = 1/16 notes, 2 = 1/8, 3 = triplets, 0 = off"
    )
    ap.add_argument("--sensitivity", type=float, default=0.8, help="0.1 (fewer notes) to 1.5 (more notes)")
    ap.add_argument(
        "--drum-parts",
        default=",".join(DEFAULT_DRUM_PARTS),
        help="any of kick,snare,hihat,openhat,toms,crash,ride (default: all but crash and ride)",
    )
    ap.add_argument(
        "--drum-map",
        default="gm",
        choices=["gm", "pads"],
        help="gm = General MIDI (MT Power Drumkit etc.), pads = one pad per drum from note 36",
    )
    ap.add_argument("--map", help="custom notes, e.g. kick=36,snare=40,hihat=42 (overrides --drum-map)")
    ap.add_argument("--humanize", type=int, default=0, help="0 (exact) to 100 (loose) timing and velocity feel")
    ap.add_argument("--out", help="folder for the .mid files")
    a = ap.parse_args()
    drum_map = dict(DRUM_MAPS["General MIDI" if a.drum_map == "gm" else "Pads in order"])
    if a.map:
        for pair in a.map.split(","):
            name, _, num = pair.partition("=")
            name = name.strip()
            if name not in DRUM_NOTES or not num.strip().isdigit() or not 0 <= int(num) <= 127:
                ap.error(f"bad --map entry '{pair}'. Use names like {', '.join(DRUM_NOTES)} with notes 0-127")
            drum_map[name] = int(num)
    log_file = os.environ.get("STEMQUILL_LOG")  # optional: also write the log to a file (used by the build tests)

    def log(msg):
        print(msg, flush=True)
        if log_file:
            with open(log_file, "a", encoding="utf-8") as fh:
                fh.write(msg + "\n")

    for stem in a.stems:
        convert(
            stem,
            a.type,
            a.bpm,
            a.grid,
            a.sensitivity,
            a.drum_parts.split(","),
            a.out,
            log=log,
            drum_map=drum_map,
            humanize_amount=max(0, min(100, a.humanize)) / 100,
        )
