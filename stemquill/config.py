"""Shared constants: drum notes and maps, stem types, pitch ranges and saved settings."""

import json
import os
import sys

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(PACKAGE_DIR, "assets")
REPO_URL = "https://github.com/skynrlabs/Stemquill"

SR = 44100
HOP = 256
TPB = 480  # MIDI ticks per beat

STEM_TYPES = ["drums", "bass", "vocal", "melodic", "synth"]

# General MIDI drum map (MT Power Drumkit 2 follows this)
DRUM_NOTES = {
    "kick": 36, "snare": 38, "hihat": 42, "openhat": 46,
    "tom_hi": 48, "tom_mid": 45, "tom_low": 43,
    "crash": 49, "ride": 51,
}
# Note layouts for different drum plugins. Every drum gets its own note.
DRUM_MAPS = {
    "General MIDI": dict(DRUM_NOTES),
    # For pad samplers (FL Studio FPC, Ableton Drum Rack, MPC-style kits): one pad per drum,
    # in this order, starting on the lowest pad (note 36). Load your sounds onto pads in this order.
    "Pads in order": {"kick": 36, "snare": 37, "hihat": 38, "openhat": 39, "tom_low": 40,
                      "tom_mid": 41, "tom_hi": 42, "crash": 43, "ride": 44},
}
DRUM_MAP_LABELS = {
    "General MIDI": "General MIDI (MT Power Drumkit, EZdrummer, most kits)",
    "Pads in order": "Pads in order (FPC, Drum Rack, MPC-style pads)",
    "Custom": "Custom: type your own notes",
}
DRUM_LABELS = {"kick": "Kick", "snare": "Snare", "hihat": "Hat cl.", "openhat": "Hat op.",
               "tom_hi": "Tom hi", "tom_mid": "Tom mid", "tom_low": "Tom low", "crash": "Crash", "ride": "Ride"}


def note_name(n):
    """Note name with note 36 = C1 (Waveform and many DAWs; some label octaves differently)."""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[n % 12]}{n // 12 - 2}"



def _settings_dir():
    """Your own app-data folder, so settings survive updates and work in an installed copy."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "Stemquill")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Stemquill")
    return os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "stemquill")


SETTINGS_PATH = os.path.join(_settings_dir(), "settings.json")


def load_settings():
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_settings(data):
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


# What each checkbox / --drum-parts name covers
DRUM_PARTS = {
    "kick": ["kick"], "snare": ["snare"], "hihat": ["hihat"], "openhat": ["openhat"],
    "toms": ["tom_hi", "tom_mid", "tom_low"], "crash": ["crash"], "ride": ["ride"],
}
DEFAULT_DRUM_PARTS = ("kick", "snare", "hihat", "openhat", "toms")  # cymbals off by default

# General MIDI program numbers so the file opens with a sensible sound
PROGRAMS = {"bass": 33, "vocal": 52, "melodic": 25, "synth": 89}

PITCH_RANGES = {  # (low note, high note) for each stem type
    "bass": ("E1", "G3"),
    "vocal": ("E2", "C6"),
    "melodic": ("E2", "C7"),
    "synth": ("C2", "C7"),
}


def log_default(msg):
    print(msg, flush=True)
