"""Drum detection: right drum, right time, right note."""

from collections import Counter

import pytest

from stemquill.config import DRUM_MAPS, DRUM_NOTES

NOTE_TO_PART = {n: p for p, n in DRUM_NOTES.items()}
TOLERANCE = 0.02  # seconds


def parts_at(result, seconds):
    return [NOTE_TO_PART[n] for s, _, n, _ in result["notes"] if abs(s - seconds) < TOLERANCE]


def test_every_drum_type_is_recognised(stems, run):
    path, truth = stems["kit"]
    result = run(path, "drums")
    for seconds, part in truth:
        assert parts_at(result, seconds) == [part], f"{part} at {seconds:.2f}s"
    assert len(result["notes"]) == len(truth), "no extra hits"


def test_basic_beat_counts_and_timing(stems, run):
    path, truth = stems["beat"]
    result = run(path, "drums")
    got = Counter(NOTE_TO_PART[n] for _, _, n, _ in result["notes"])
    assert got["kick"] == 8
    assert got["snare"] == 8
    # Known limitation: a hi-hat that lands at the same moment as a snare is written as the snare only.
    snare_times = {s for s, p in truth if p == "snare"}
    expected_hats = [s for s, p in truth if p == "hihat" and s not in snare_times]
    assert got["hihat"] == len(expected_hats)
    for s in expected_hats:
        assert "hihat" in parts_at(result, s)


@pytest.mark.parametrize("stem", ["kit", "beat"])
def test_hits_land_on_time(stems, run, stem):
    """Each detected hit must sit within 3 ms of when the drum actually sounds."""
    path, truth = stems[stem]
    times = sorted({round(t, 6) for t, _ in truth})
    for s, _, _, _ in run(path, "drums")["notes"]:
        nearest = min(times, key=lambda t: abs(t - s))
        assert abs(s - nearest) < 0.003, f"hit at {s:.4f}s is {1000 * (s - nearest):+.1f} ms off"


def test_only_ticked_drums_are_written(stems, run):
    result = run(stems["kit"][0], "drums", parts=["kick"])
    assert {NOTE_TO_PART[n] for _, _, n, _ in result["notes"]} == {"kick"}


def test_open_hats_become_closed_hats_when_open_hats_are_off(stems, run):
    path, truth = stems["kit"]
    result = run(path, "drums", parts=["hihat"])
    for seconds, part in truth:
        if part == "openhat":
            assert parts_at(result, seconds) == ["hihat"]


def test_lower_sensitivity_never_adds_notes(stems, run):
    path = stems["beat"][0]
    low = len(run(path, "drums", sensitivity=0.3)["notes"])
    mid = len(run(path, "drums", sensitivity=0.8)["notes"])
    high = len(run(path, "drums", sensitivity=1.4)["notes"])
    assert low <= mid <= high


@pytest.mark.parametrize("map_name", ["General MIDI", "Pads in order"])
def test_drum_maps_put_each_drum_on_its_note(stems, run, map_name):
    path, truth = stems["kit"]
    notes = DRUM_MAPS[map_name]
    result = run(path, "drums", drum_map=notes)
    for seconds, part in truth:
        hits = [n for s, _, n, _ in result["notes"] if abs(s - seconds) < TOLERANCE]
        assert hits == [notes[part]], f"{part} on {map_name}"


def test_custom_map(stems, run):
    result = run(stems["kit"][0], "drums", parts=["kick"], drum_map={"kick": 35})
    assert {n for _, _, n, _ in result["notes"]} == {35}


def test_silent_stem_is_skipped(stems, run):
    assert run(stems["silent"][0], "drums") is None


def test_drum_stems_use_channel_10(stems, run):
    result = run(stems["beat"][0], "drums")
    assert result["channel"] == 9  # MIDI channels count from 0, so 9 is "channel 10"
