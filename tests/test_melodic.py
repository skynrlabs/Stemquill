"""Bass, vocal and chord transcription."""

import librosa
import pytest

from stemquill.config import PROGRAMS
from stemquill.core.melodic import transcribe_poly_simple

from .conftest import BASS_LINE, CHORDS, VOCAL_LINE

ONSET_TOLERANCE = 0.015


def check_line(result, truth):
    got = sorted((s, n) for s, _, n, _ in result["notes"])
    assert [n for _, n in got] == [n for _, n in truth]
    for (s, _), (t, _) in zip(got, truth, strict=True):
        assert s == pytest.approx(t, abs=ONSET_TOLERANCE)


def test_bass_line(stems, run):
    path, truth = stems["bass"]
    result = run(path, "bass")
    check_line(result, truth)
    assert [n for _, _, n, _ in sorted(result["notes"])] == BASS_LINE


def test_repeated_bass_note_is_split(stems, run):
    result = run(stems["bass"][0], "bass")
    starts = sorted(s for s, _, n, _ in result["notes"] if n == 40)
    assert len(starts) == 4  # 40 appears four times, including two in a row


def test_vocal_melody(stems, run):
    path, truth = stems["vocal"]
    result = run(path, "vocal")
    check_line(result, truth)
    assert [n for _, _, n, _ in sorted(result["notes"])] == VOCAL_LINE


def test_built_in_chord_mode(stems):
    path, _ = stems["chords"]
    y, sr = librosa.load(path, sr=44100, mono=True)
    notes = transcribe_poly_simple(y, sr, 120, None, "melodic", 0.8, lambda m: None)
    for i, chord in enumerate(CHORDS):
        start = i * 2.0
        got = sorted(n for s, _, n, _ in notes if abs(s - start) < ONSET_TOLERANCE)
        assert got == sorted(chord), f"chord {i + 1}"


def test_auto_type_from_file_name(stems, run):
    assert run(stems["bass"][0])["stem_type"] == "bass"
    assert run(stems["vocal"][0])["stem_type"] == "vocal"
    assert run(stems["beat"][0])["stem_type"] == "drums"
    assert run(stems["chords"][0])["stem_type"] == "melodic"


def test_pitched_stems_get_a_sensible_instrument(stems, run):
    result = run(stems["bass"][0], "bass")
    assert result["channel"] == 0
    assert result["program"] == PROGRAMS["bass"]


def test_chord_engine_is_reported(stems, run):
    assert run(stems["chords"][0], "melodic")["engine"] in ("basic-pitch", "built-in")
    assert run(stems["bass"][0], "bass")["engine"] is None
