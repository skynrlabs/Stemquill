"""Writing MIDI files, snapping to the grid, and tidying overlaps."""

import mido
import pytest

from stemquill.config import TPB
from stemquill.core import save_result
from stemquill.core.midi import clean_overlaps, snap, write_midi


def read_notes(path):
    mid = mido.MidiFile(path)
    t, on, notes, tempo, programs, channels = 0, {}, [], None, [], set()
    for msg in mid.tracks[0]:
        t += msg.time
        if msg.type == "set_tempo":
            tempo = mido.tempo2bpm(msg.tempo)
        elif msg.type == "program_change":
            programs.append(msg.program)
        elif msg.type == "note_on" and msg.velocity > 0:
            on[msg.note] = (t, msg.velocity)
            channels.add(msg.channel)
        elif msg.type in ("note_off", "note_on"):
            start, vel = on.pop(msg.note)
            notes.append((start, t, msg.note, vel))
    return mid, sorted(notes), tempo, programs, channels


def test_round_trip(tmp_path):
    bpm = 120
    notes = [(0.0, 0.5, 60, 100), (0.5, 1.0, 64, 80), (1.0, 2.0, 67, 64)]
    path = tmp_path / "x.mid"
    write_midi(notes, str(path), bpm, "test", channel=0, program=25)
    mid, got, tempo, programs, channels = read_notes(path)
    assert mid.ticks_per_beat == TPB
    assert tempo == pytest.approx(bpm)
    assert programs == [25]
    assert channels == {0}
    # 0.5 s at 120 BPM is one beat = TPB ticks
    assert got == [(0, TPB, 60, 100), (TPB, 2 * TPB, 64, 80), (2 * TPB, 4 * TPB, 67, 64)]


def test_zero_length_note_still_gets_a_length(tmp_path):
    path = tmp_path / "x.mid"
    write_midi([(1.0, 1.0, 36, 100)], str(path), 120, "drums", channel=9)
    _, got, _, _, channels = read_notes(path)
    start, end, _, _ = got[0]
    assert end > start
    assert channels == {9}


@pytest.mark.parametrize(
    "t, grid, expected",
    [(0.26, 4, 0.25), (0.30, 4, 0.25), (0.40, 4, 0.375), (0.40, 2, 0.5), (0.40, 0, 0.40), (0.40, None, 0.40)],
)
def test_snap(t, grid, expected):
    # at 120 BPM a beat is 0.5 s, so 1/16 notes (grid 4) are 0.125 s apart
    assert snap(t, 120, grid) == pytest.approx(expected)


def test_clean_overlaps_trims_same_pitch():
    out = clean_overlaps([(0.0, 1.0, 60, 90), (0.5, 1.5, 60, 90)])
    assert out == [(0.0, 0.5, 60, 90), (0.5, 1.5, 60, 90)]


def test_clean_overlaps_keeps_louder_duplicate():
    out = clean_overlaps([(0.0, 0.2, 36, 70), (0.01, 0.2, 36, 110)])
    assert out == [(0.01, 0.2, 36, 110)]


def test_save_result_names_and_folders(stems, run, tmp_path):
    result = run(stems["beat"][0], "drums")
    out = save_result(result, str(tmp_path / "new folder"), lambda m: None)
    assert out.endswith("Drums - drums.mid")
    assert (tmp_path / "new folder" / "Drums - drums.mid").exists()
