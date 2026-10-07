"""Timing helpers and MIDI file writing."""

import mido

from ..config import TPB


def snap(t, bpm, grid):
    """Snap a time in seconds to the nearest grid step (grid = steps per beat)."""
    if not grid:
        return t
    step = 60.0 / bpm / grid
    return round(t / step) * step


def to_ticks(t, bpm):
    return max(0, int(round(t * bpm / 60.0 * TPB)))


def write_midi(notes, out_path, bpm, track_name, channel, program=None):
    """notes: list of (start_sec, end_sec, midi_note, velocity)."""
    mid = mido.MidiFile(ticks_per_beat=TPB)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name=track_name, time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    if program is not None:
        track.append(mido.Message("program_change", channel=channel, program=program, time=0))

    events = []
    for start, end, note, vel in notes:
        on, off = to_ticks(start, bpm), to_ticks(end, bpm)
        if off <= on:
            off = on + TPB // 8
        events.append((on, 1, note, vel))
        events.append((off, 0, note, 0))
    events.sort(key=lambda e: (e[0], e[1]))  # note-offs before note-ons at the same tick

    last = 0
    for tick, is_on, note, vel in events:
        kind = "note_on" if is_on else "note_off"
        track.append(mido.Message(kind, channel=channel, note=int(note), velocity=int(vel), time=tick - last))
        last = tick
    track.append(mido.MetaMessage("end_of_track", time=TPB))
    mid.save(out_path)


def clean_overlaps(notes):
    """Trim overlapping notes on the same pitch so DAWs don't drop them."""
    notes = sorted(notes, key=lambda n: (n[2], n[0]))
    out = []
    for n in notes:
        if out and out[-1][2] == n[2] and out[-1][1] > n[0]:
            prev = out[-1]
            if n[0] - prev[0] < 0.02:  # same onset after snapping -> keep the louder one
                if n[3] > prev[3]:
                    out[-1] = n
                continue
            out[-1] = (prev[0], n[0], prev[2], prev[3])
        out.append(n)
    return sorted(out, key=lambda n: n[0])
