"""One module per sidebar page."""

from .convert import ConvertPage
from .drum_kit import DrumKitPage
from .help import HelpPage
from .output import OutputPage

# (key, sidebar label, page title, page subtitle)
PAGES = [
    ("convert", "Convert", "Convert", "Add stems, check the settings, preview, then convert"),
    ("drums", "Drum Kit", "Drum Kit", "Which drums to write, and which note each one goes on"),
    ("output", "Output", "Output", "Where your MIDI files are saved"),
    ("help", "Help", "Help", "How to get the best results from Stemquill"),
]

__all__ = ["PAGES", "ConvertPage", "DrumKitPage", "HelpPage", "OutputPage"]
