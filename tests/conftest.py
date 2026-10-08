"""Shared fixtures: synthetic stems written once per test run, and a quiet transcribe helper."""

import os

import pytest

from stemquill.core import transcribe

from . import synth

ALL_PARTS = ["kick", "snare", "hihat", "openhat", "toms", "crash", "ride"]

BASS_LINE = [40, 43, 45, 47, 45, 43, 40, 38, 40, 40, 43, 45]  # note the repeated 40 40
VOCAL_LINE = [60, 62, 64, 65, 67, 65, 64, 62]
CHORDS = [(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)]  # C, Am, F, G


def pytest_addoption(parser):
    parser.addoption("--update-snapshots", action="store_true", help="rewrite tests/snapshots from current output")


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Never touch the real user's settings file."""
    import stemquill.config as config

    monkeypatch.setattr(config, "SETTINGS_PATH", str(tmp_path / "settings.json"))


@pytest.fixture(scope="session")
def stems(tmp_path_factory):
    """Synthetic stems with known content, as files (names follow Suno's stem names)."""
    d = tmp_path_factory.mktemp("stems")
    out = {}
    y, truth = synth.drum_loop(synth.full_kit())
    out["kit"] = (synth.write(d / "Kit Drums.wav", y), truth)
    y, truth = synth.drum_loop(synth.basic_beat())
    out["beat"] = (synth.write(d / "Drums.wav", y), truth)
    y, truth = synth.note_sequence(
        [(i * 1.0, 0.9, n) for i, n in enumerate(BASS_LINE)], harmonics=((1, 1.0), (2, 0.5), (3, 0.25)), decay=1.0
    )
    out["bass"] = (synth.write(d / "Bass.wav", y), truth)
    y, truth = synth.note_sequence(
        [(i * 1.0, 0.9, n) for i, n in enumerate(VOCAL_LINE)], harmonics=((1, 1.0), (2, 0.15)), decay=0.3
    )
    out["vocal"] = (synth.write(d / "Vocals.wav", y), truth)
    y, truth = synth.note_sequence([(i * 4.0, 3.8, c) for i, c in enumerate(CHORDS)], decay=0.6)
    out["chords"] = (synth.write(d / "Other.wav", y), truth)
    import numpy as np

    out["silent"] = (synth.write(d / "Silent Vocals.wav", np.zeros(synth.SR * 2)), [])
    return out


@pytest.fixture
def run():
    """transcribe() with sensible test defaults and no console output."""

    def _run(path, stem_type="auto", bpm=120.0, grid=0, sensitivity=0.8, parts=ALL_PARTS, **kw):
        return transcribe(os.fspath(path), stem_type, bpm, grid, sensitivity, parts, lambda m: None, **kw)

    return _run
