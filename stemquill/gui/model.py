"""What the window knows about each stem: its type, its own settings, and how converting it went."""

import os
from dataclasses import dataclass, field

from ..config import DEFAULT_DRUM_PARTS
from ..core import guess_type

DEFAULT_SENSITIVITY = 0.8
DEFAULT_HUMANIZE = 0  # percent


@dataclass
class Stem:
    path: str
    stem_type: str = ""
    sensitivity: float = DEFAULT_SENSITIVITY
    humanize: int = DEFAULT_HUMANIZE
    parts: list = field(default_factory=lambda: list(DEFAULT_DRUM_PARTS))
    status: str = "not converted yet"
    status_kind: str = "muted"  # muted, busy, ok or warn
    saved: str = None

    def __post_init__(self):
        if not self.stem_type:
            self.stem_type = guess_type(self.path)  # read from the file name: Drums, Bass, Vocals, Other

    @property
    def name(self):
        return os.path.basename(self.path)

    def reset(self):
        self.sensitivity = DEFAULT_SENSITIVITY
        self.humanize = DEFAULT_HUMANIZE
        self.parts = list(DEFAULT_DRUM_PARTS)

    def copy_settings_from(self, other):
        self.sensitivity = other.sensitivity
        self.humanize = other.humanize
        self.parts = list(other.parts)
