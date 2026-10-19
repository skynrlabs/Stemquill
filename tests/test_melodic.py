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


def sung(midi, seconds, cents_off=-40, vibrato=0.35):
    """A held note sung a little flat with a 5.5 Hz vibrato, like most real (and AI) vocals."""
    import numpy as np

    t = np.arange(int(seconds * synth.SR)) / synth.SR
    f = 440.0 * 2 ** ((midi + cents_off / 100 - 69) / 12) * 2 ** (vibrato / 12 * np.sin(2 * np.pi * 5.5 * t))
    phase = 2 * np.pi * np.cumsum(f) / synth.SR
    env = np.minimum(1, t / 0.04) * np.minimum(1, (t[-1] - t) / 0.08)
    return 0.3 * env * sum(a * np.sin(k * phase) for k, a in ((1, 1.0), (2, 0.5), (3, 0.3), (4, 0.2)))


def test_flat_vocal_with_vibrato_is_one_note_per_note(tmp_path, run):
    """Sung 40 cents flat with vibrato, each held note used to break into a dozen flickering ones."""
    import numpy as np

    line = [62, 64, 65, 67]
    gap = np.zeros(synth.SR // 10)
    y = np.concatenate([np.zeros(synth.SR // 2)] + [np.concatenate([sung(m, 1.2), gap]) for m in line])
    result = run(synth.write(tmp_path / "Vocals.wav", y), "vocal")
    assert [n for _, _, n, _ in sorted(result["notes"])] == line


def test_sharp_vocal_is_read_at_the_right_pitch(tmp_path, run):
    import numpy as np

    line = [60, 62, 64]
    y = np.concatenate(
        [np.zeros(synth.SR // 2)] + [np.concatenate([sung(m, 1.0, cents_off=35), np.zeros(4410)]) for m in line]
    )
    result = run(synth.write(tmp_path / "Lead Vocals.wav", y), "vocal")
    assert [n for _, _, n, _ in sorted(result["notes"])] == line


SUNO_STEMS = {  # Suno's stem names -> (stem type, General MIDI program; None for drums)
    "Vocals.wav": ("vocal", PROGRAMS["vocal"]),
    "Backing Vocals.wav": ("melodic", 52),  # harmonies are chords, so not the one-line vocal mode
    "Drums.wav": ("drums", None),
    "Percussion.wav": ("drums", None),
    "Bass.wav": ("bass", PROGRAMS["bass"]),
    "Guitar.wav": ("melodic", 25),
    "Keyboard.wav": ("melodic", 0),
    "Strings.wav": ("melodic", 48),
    "Brass.wav": ("melodic", 61),
    "Woodwinds.wav": ("melodic", 73),
    "Synth.wav": ("synth", PROGRAMS["synth"]),
    "FX.wav": ("synth", PROGRAMS["synth"]),
    "My Song (Organ).wav": ("melodic", 16),
    "Other.wav": ("melodic", PROGRAMS["melodic"]),
}


@pytest.mark.parametrize("name", SUNO_STEMS)
def test_stem_names_pick_type_and_instrument(name):
    from stemquill.core.pipeline import guess_type, instrument_for

    stem_type, program = SUNO_STEMS[name]
    assert guess_type(name) == stem_type
    if program is not None:
        assert instrument_for(name, stem_type) == program


def test_a_type_changed_by_hand_gets_that_types_sound():
    from stemquill.core.pipeline import instrument_for

    assert instrument_for("Strings.wav", "synth") == PROGRAMS["synth"]  # not strings any more


def test_fx_stems_carry_a_note(tmp_path):
    import numpy as np

    from stemquill.core import transcribe
    from stemquill.core.pipeline import is_fx

    assert is_fx("Song - FX.wav") and not is_fx("Effexor.wav") and not is_fx("Guitar.wav")
    lines = []
    y = np.concatenate([np.zeros(synth.SR // 4), synth.tone(60, 1.0)])
    transcribe(synth.write(tmp_path / "FX.wav", y), "auto", 120.0, 0, 0.8, [], lines.append)
    assert any("sound effects" in m for m in lines)


def slid(start, end, before=0.4, glide=0.15, after=0.65, amp=0.5):
    """A held bass note that slides smoothly to another and stays there."""
    import numpy as np

    t = np.arange(int((before + glide + after) * synth.SR)) / synth.SR
    progress = np.clip((t - before) / glide, 0, 1)
    f = 440.0 * 2 ** ((start + (end - start) * progress - 69) / 12)
    phase = 2 * np.pi * np.cumsum(f) / synth.SR
    env = np.minimum(1, t / 0.02) * np.minimum(1, (t[-1] - t) / 0.08)
    return amp * env * sum(a * np.sin(k * phase) for k, a in ((1, 1.0), (2, 0.5), (3, 0.25)))


@pytest.mark.parametrize("start, end", [(33, 40), (40, 33), (36, 43)])
def test_bass_slide_is_two_notes(tmp_path, run, start, end):
    """A slide passes through every note on the way; those used to come out as short extra notes."""
    import numpy as np

    lead_in = 0.25
    y = np.concatenate([np.zeros(int(lead_in * synth.SR)), slid(start, end)])
    result = run(synth.write(tmp_path / "Bass.wav", y), "bass")
    notes = sorted(result["notes"])
    assert [n for _, _, n, _ in notes] == [start, end]
    # the slid-from note carries on through the slide; the note it lands on starts on arrival
    assert notes[1][0] == pytest.approx(lead_in + 0.4 + 0.15, abs=0.04)


def test_quick_note_change_is_not_a_slide(stems, run):
    """Ordinary notes still start right on time (a jump between notes isn't mistaken for a slide)."""
    path, truth = stems["bass"]
    check_line(run(path, "bass"), truth)


def test_restrummed_chord_is_split(tmp_path):
    """Strummed again while still ringing, a chord never goes quiet; each strum is still a chord."""
    import numpy as np

    strums = [(i * 0.5, 0.5, [60, 64, 67]) for i in range(4)]  # eighth notes, ringing into the next
    y, _ = synth.note_sequence(strums, decay=3.0)
    y = np.asarray(y)
    path = synth.write(tmp_path / "Guitar.wav", y)
    audio, sr = librosa.load(path, sr=44100, mono=True)
    notes = transcribe_poly_simple(audio, sr, 120, None, "melodic", 0.8, lambda m: None)
    for pitch in (60, 64, 67):
        starts = sorted(s for s, _, n, _ in notes if n == pitch)
        assert starts == pytest.approx([0.0, 0.25, 0.5, 0.75], abs=ONSET_TOLERANCE), pitch
