"""The conversion journey for one stem: load, transcribe, humanize, save."""

import os
import re

import librosa
import numpy as np

from ..config import DEFAULT_DRUM_PARTS, DRUM_NOTES, PROGRAMS, SR, log_default
from .drums import transcribe_drums
from .humanize import humanize
from .melodic import transcribe_mono, transcribe_poly_basic_pitch, transcribe_poly_simple
from .midi import write_midi
from .tempo import detect_tempo

# What a stem's file name says it is, checked in order: (words, stem type, General MIDI program).
# The names cover Suno's stems (Vocals, Backing Vocals, Drums, Bass, Guitar, Keyboard, Percussion,
# Strings, Synth, FX, Brass, Woodwinds) and the usual names from other splitters and DAWs.
NAME_HINTS = [
    (("backing", "harmony", "harmonies", "choir", "bgv"), "melodic", 52),  # stacked harmonies: chords, not one line
    (("drum", "perc"), "drums", None),
    (("bass",), "bass", PROGRAMS["bass"]),
    (("vocal", "vox", "voice"), "vocal", PROGRAMS["vocal"]),
    (("synth", "pad"), "synth", PROGRAMS["synth"]),
    (("string", "violin", "viola", "cello", "orchestra"), "melodic", 48),
    (("brass", "trumpet", "trombone", "horn"), "melodic", 61),
    (("sax",), "melodic", 65),
    (("woodwind", "flute", "clarinet", "oboe"), "melodic", 73),
    (("organ",), "melodic", 16),
    (("piano", "key"), "melodic", 0),  # Keyboard, Keys
    (("guitar",), "melodic", PROGRAMS["melodic"]),
]
FX_WORDS = {"fx", "sfx", "effects", "riser", "risers"}  # whole words only: "fx" is inside other words


def _hint(path):
    name = os.path.basename(path).lower()
    for words, stem_type, program in NAME_HINTS:
        if any(w in name for w in words):
            return stem_type, program
    return None, None


def is_fx(path):
    """Sound-effect stems (Suno's FX: risers, sweeps, impacts) rarely make useful MIDI."""
    return bool(FX_WORDS & set(re.split(r"[^a-z]+", os.path.basename(path).lower())))


def guess_type(path):
    stem_type, _ = _hint(path)
    if stem_type:
        return stem_type
    return "synth" if is_fx(path) else "melodic"


def instrument_for(path, stem_type):
    """The General MIDI sound for a pitched stem: from its name when that names an instrument
    (Strings get strings, Keyboard gets piano), otherwise the stem type's usual sound."""
    hint_type, program = _hint(path)
    if hint_type == stem_type and program is not None:
        return program
    return PROGRAMS[stem_type]


_cache = {}


def transcribe(
    path,
    stem_type="auto",
    bpm=None,
    grid=4,
    sensitivity=0.8,
    drum_parts=DEFAULT_DRUM_PARTS,
    log=log_default,
    drum_map=None,
    humanize_amount=0.0,
):
    """Turn one stem into notes. Returns a dict, or None if the stem is silent."""
    if stem_type == "auto":
        stem_type = guess_type(path)
    drum_map = {**DRUM_NOTES, **(drum_map or {})}
    key = (
        os.path.abspath(path),
        os.path.getmtime(path),
        stem_type,
        bpm,
        grid,
        round(sensitivity, 3),
        tuple(sorted(drum_parts)),
        tuple(sorted(drum_map.items())),
        round(humanize_amount, 3),
    )
    if key in _cache:
        log(f"\n{os.path.basename(path)}  ->  {stem_type}  (using the preview result)")
        return _cache[key]

    log(f"\n{os.path.basename(path)}  ->  {stem_type}")
    if is_fx(path) and stem_type != "drums":
        log("  note: sound effects rarely make useful MIDI")
    y, sr = librosa.load(path, sr=SR, mono=True)
    if y.size == 0 or np.max(np.abs(y)) < 1e-4:
        log("  stem is silent, skipped")
        return None

    if not bpm:
        bpm = detect_tempo(path)
        log(f"  detected tempo: {bpm:g} BPM")
    grid_steps = None if not grid else int(grid)

    engine = None  # which chord engine was used, for polyphonic stems
    if stem_type == "drums":
        notes = transcribe_drums(y, sr, bpm, grid_steps, sensitivity, set(drum_parts), log, drum_map)
        channel, program = 9, None
    elif stem_type in ("bass", "vocal"):
        notes = transcribe_mono(y, sr, bpm, grid_steps, stem_type, sensitivity, log)
        channel, program = 0, instrument_for(path, stem_type)
    else:
        try:
            notes = transcribe_poly_basic_pitch(path, bpm, grid_steps, stem_type, sensitivity, log)
            engine = "basic-pitch"
        except ImportError as exc:
            if getattr(exc, "name", None) != "basic_pitch":  # installed, but something it needs is missing
                log(f"  basic-pitch couldn't load ({exc}); using built-in mode")
            notes = transcribe_poly_simple(y, sr, bpm, grid_steps, stem_type, sensitivity, log)
            engine = "built-in"
        except Exception as exc:  # basic-pitch installed but failed -> still produce a file
            log(f"  basic-pitch failed ({exc}); using built-in mode")
            notes = transcribe_poly_simple(y, sr, bpm, grid_steps, stem_type, sensitivity, log)
            engine = "built-in"
        channel, program = 0, instrument_for(path, stem_type)

    if humanize_amount > 0:
        notes = humanize(notes, bpm, humanize_amount, stem_type == "drums")
        log(f"  humanized ({int(humanize_amount * 100)}%)")

    result = {
        "notes": notes,
        "bpm": bpm,
        "stem_type": stem_type,
        "channel": channel,
        "program": program,
        "drum_map": drum_map,
        "path": path,
        "engine": engine,
    }
    _cache[key] = result
    return result


def save_result(result, out_dir=None, log=log_default, time_signature=(4, 4)):
    path, stem_type = result["path"], result["stem_type"]
    out_dir = out_dir or os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    out_path = os.path.join(out_dir, f"{base} - {stem_type}.mid")
    write_midi(
        result["notes"],
        out_path,
        result["bpm"],
        f"{base} ({stem_type})",
        result["channel"],
        result["program"],
        time_signature,
    )
    log(f"  saved: {out_path}")
    return out_path


def convert(
    path,
    stem_type="auto",
    bpm=None,
    grid=4,
    sensitivity=0.8,
    drum_parts=DEFAULT_DRUM_PARTS,
    out_dir=None,
    log=log_default,
    drum_map=None,
    humanize_amount=0.0,
    time_signature=(4, 4),
):
    result = transcribe(path, stem_type, bpm, grid, sensitivity, drum_parts, log, drum_map, humanize_amount)
    return save_result(result, out_dir, log, time_signature) if result else None
