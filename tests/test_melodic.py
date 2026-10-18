"""Bass, vocal and chord transcription."""

import librosa
import pytest

from stemquill.config import PROGRAMS
from stemquill.core.melodic import pitch_frame_length, transcribe_poly_simple

from . import synth
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


LOW_RUN = [28, 31, 43, 43, 31, 38, 38, 45, 28, 31]  # open low E and low G among 16th notes, at 100 BPM


@pytest.fixture(scope="module")
def low_bass(tmp_path_factory):
    beats = [0.25, 0.5, 0.75, 1.5, 1.75, 2.0, 2.75, 3.5, 4.0, 4.25]
    lengths = [0.25, 0.25, 0.5, 0.25, 0.25, 0.5, 0.25, 0.5, 0.25, 0.5]
    y, truth = synth.note_sequence(
        list(zip(beats, lengths, LOW_RUN, strict=True)),
        bpm=100.0,
        harmonics=((1, 1.0), (2, 0.5), (3, 0.25), (4, 0.12)),
        decay=2.5,
    )
    return synth.write(tmp_path_factory.mktemp("low") / "Bass.wav", y), truth


def test_low_bass_notes_are_found(low_bass, run):
    """The open low E (41 Hz) and low G were missed when the pitch window was too short for them."""
    path, truth = low_bass
    result = run(path, "bass", bpm=100.0)
    check_line(result, truth)


def test_sensitivity_changes_a_bass_line(low_bass, run):
    path, _ = low_bass
    counts = [len(run(path, "bass", bpm=100.0, sensitivity=s)["notes"]) for s in (0.2, 0.8, 1.5)]
    assert counts[0] < counts[1] <= counts[2]


def test_vocals_keep_the_short_pitch_window():
    sr = 44100
    assert pitch_frame_length(librosa.note_to_hz("E2"), sr) == 2048  # vocal range
    assert pitch_frame_length(librosa.note_to_hz("E1"), sr) == 4096  # bass range


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
