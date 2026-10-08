"""One module per sidebar page."""

from .convert import ConvertPage
from .help import HelpPage
from .history import HistoryPage
from .settings import SettingsPage

# (key, sidebar label, page title, page subtitle)
PAGES = [
    ("convert", "Convert", "Convert", "Set the song tempo, check each stem, preview, then convert"),
    ("history", "History", "History", "What Detect, Play and Convert did, newest first"),
    ("settings", "Settings", "Settings", "Where files are saved, and which note each drum goes on"),
    ("help", "Help", "Help", "How to get the best results from Stemquill"),
]

__all__ = ["PAGES", "ConvertPage", "HelpPage", "HistoryPage", "SettingsPage"]
