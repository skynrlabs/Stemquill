"""Stemquill's audio engine: no GUI code in here, so it can be used from scripts too."""

from .pipeline import convert, guess_type, save_result, transcribe
from .preview import Player, render_preview
from .tempo import detect_tempo

__all__ = ["convert", "detect_tempo", "guess_type", "Player", "render_preview", "save_result", "transcribe"]
