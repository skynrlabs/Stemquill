"""Tempo detection must land within a fraction of a BPM, at slow and fast tempos."""

import pytest

from stemquill.core import detect_tempo

from . import synth


@pytest.mark.parametrize("bpm", [92, 104, 116, 121.5, 140, 168])
def test_detects_tempo(tmp_path, bpm):
    y, _ = synth.drum_loop(synth.basic_beat(8), bpm=bpm)
    path = synth.write(tmp_path / f"loop {bpm}.wav", y)
    assert detect_tempo(path, log=lambda m: None) == pytest.approx(bpm, abs=0.2)


def test_missing_bpm_is_detected_during_conversion(stems, run):
    result = run(stems["beat"][0], "drums", bpm=None)
    assert result["bpm"] == pytest.approx(120, abs=0.2)
