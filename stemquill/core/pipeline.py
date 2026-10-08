"""The conversion journey for one stem: load, transcribe, humanize, save."""

import os

import librosa
import numpy as np

from ..config import DEFAULT_DRUM_PARTS, DRUM_NOTES, PROGRAMS, SR, log_default
from .drums import transcribe_drums
from .humanize import humanize
from .melodic import transcribe_mono, transcribe_poly_basic_pitch, transcribe_poly_simple
from .midi import write_midi
from .tempo import detect_tempo


def guess_type(path):
    name = os.path.basename(path).lower()
    if "drum" in name or "perc" in name:
        return "drums"
    if "bass" in name:
        return "bass"
    if "vocal" in name or "vox" in name or "voice" in name:
        return "vocal"
    if "synth" in name or "pad" in name or "key" in name:
        return "synth"
    return "melodic"


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
        channel, program = 0, PROGRAMS[stem_type]
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
        channel, program = 0, PROGRAMS[stem_type]

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


def save_result(result, out_dir=None, log=log_default):
    path, stem_type = result["path"], result["stem_type"]
    out_dir = out_dir or os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    out_path = os.path.join(out_dir, f"{base} - {stem_type}.mid")
    write_midi(result["notes"], out_path, result["bpm"], f"{base} ({stem_type})", result["channel"], result["program"])
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
):
    result = transcribe(path, stem_type, bpm, grid, sensitivity, drum_parts, log, drum_map, humanize_amount)
    return save_result(result, out_dir, log) if result else None
