#!/usr/bin/env python3
"""
Stemquill - convert audio stems into MIDI files you can drag into any DAW.

Stem types:
  drums   -> kick / snare / hi-hat on General MIDI drum notes (works with MT Power Drumkit 2)
  bass    -> single-note line (pitch tracking)
  vocal   -> lead vocal melody (pitch tracking)
  melodic -> guitar, keys, fiddle, chords (polyphonic)
  synth   -> synths and pads (polyphonic)

Run with no arguments to open the window, or use the command line:
  python stemquill.py "Drums.wav" --type drums --bpm 116
  python stemquill.py "Bass.wav" "Other.wav" --bpm 116          (type guessed from filename)
"""

import argparse
import os
import sys
import threading

import numpy as np

try:
    import librosa
    import mido
    import scipy.ndimage
except ImportError as exc:  # pragma: no cover
    print(f"Missing library: {exc.name}. Run:  pip install -r requirements.txt")
    sys.exit(1)

SR = 44100
HOP = 256
TPB = 480  # MIDI ticks per beat

STEM_TYPES = ["drums", "bass", "vocal", "melodic", "synth"]

# General MIDI drum map (MT Power Drumkit 2 follows this)
DRUM_NOTES = {
    "kick": 36, "snare": 38, "hihat": 42, "openhat": 46,
    "tom_hi": 48, "tom_mid": 45, "tom_low": 43,
    "crash": 49, "ride": 51,
}
# Note layouts for different drum plugins. Every drum gets its own note.
DRUM_MAPS = {
    "General MIDI": dict(DRUM_NOTES),
    # For pad samplers (FL Studio FPC, Ableton Drum Rack, MPC-style kits): one pad per drum,
    # in this order, starting on the lowest pad (note 36). Load your sounds onto pads in this order.
    "Pads in order": {"kick": 36, "snare": 37, "hihat": 38, "openhat": 39, "tom_low": 40,
                      "tom_mid": 41, "tom_hi": 42, "crash": 43, "ride": 44},
}
DRUM_MAP_LABELS = {
    "General MIDI": "General MIDI (MT Power Drumkit, EZdrummer, most kits)",
    "Pads in order": "Pads in order (FPC, Drum Rack, MPC-style pads)",
    "Custom": "Custom: type your own notes",
}
DRUM_LABELS = {"kick": "Kick", "snare": "Snare", "hihat": "Hat cl.", "openhat": "Hat op.",
               "tom_hi": "Tom hi", "tom_mid": "Tom mid", "tom_low": "Tom low", "crash": "Crash", "ride": "Ride"}


def note_name(n):
    """Note name with note 36 = C1 (Waveform and many DAWs; some label octaves differently)."""
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[n % 12]}{n // 12 - 2}"


SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stemquill_settings.json")


def load_settings():
    try:
        import json
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_settings(data):
    try:
        import json
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


# What each checkbox / --drum-parts name covers
DRUM_PARTS = {
    "kick": ["kick"], "snare": ["snare"], "hihat": ["hihat"], "openhat": ["openhat"],
    "toms": ["tom_hi", "tom_mid", "tom_low"], "crash": ["crash"], "ride": ["ride"],
}
DEFAULT_DRUM_PARTS = ("kick", "snare", "hihat", "openhat", "toms")  # cymbals off by default

# General MIDI program numbers so the file opens with a sensible sound
PROGRAMS = {"bass": 33, "vocal": 52, "melodic": 25, "synth": 89}

PITCH_RANGES = {  # (low note, high note) for each stem type
    "bass": ("E1", "G3"),
    "vocal": ("E2", "C6"),
    "melodic": ("E2", "C7"),
    "synth": ("C2", "C7"),
}


def log_default(msg):
    print(msg, flush=True)


# --------------------------------------------------------------------------- helpers

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


# --------------------------------------------------------------------------- drums

def band_flux(S, freqs, lo, hi):
    """Rise in energy inside one frequency band, scaled so a typical strong hit is ~1."""
    band = S[(freqs >= lo) & (freqs < hi)]
    env = np.log1p(band.sum(axis=0))
    flux = np.maximum(0.0, np.diff(env, prepend=0.0))
    ref = np.percentile(flux[flux > 0], 99) if np.any(flux > 0) else 1.0
    return flux / (ref or 1.0)


def band_energy(S, freqs, lo, hi):
    return S[(freqs >= lo) & (freqs < hi)].sum(axis=0)


def ring_ratio(env, f, after):
    """How much of a hit's energy is still ringing `after` frames later (0 = gone, 1 = still full)."""
    pre = env[max(0, f - 4):f].min() if f > 0 else 0.0
    peak = env[f:f + 4].max() - pre
    if peak <= 0:
        return 0.0
    later = env[min(len(env) - 1, f + after):min(len(env), f + after + 3)].mean() - pre
    return float(np.clip(later / peak, 0.0, 1.5))


def transcribe_drums(y, sr, bpm, grid, sensitivity, parts, log, note_map=None):
    """Find every hit, then decide which drum it is from how much each frequency band
    jumped, how long the hit rings, and (for toms) its pitch."""
    note_map = {**DRUM_NOTES, **(note_map or {})}
    want = set()
    for p in parts:
        want.update(DRUM_PARTS.get(p, [p]))

    pad = 4096  # a little silence up front so a hit on the very first sample is read correctly
    y = np.concatenate([np.zeros(pad), y])
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    E = S ** 2
    bands = {"low": (30, 130), "lowmid": (90, 400), "mid": (1500, 5000),
             "upper": (3000, 7000), "high": (7000, 16000)}
    env = {k: band_energy(E, freqs, *v) for k, v in bands.items()}
    ref = {k: (np.percentile(v, 99.5) or 1.0) for k, v in env.items()}  # "loud" level per band

    def rise(band, f):
        """How big a jump this hit makes in a band, compared with the loudest hits (about 0..1)."""
        e = env[band]
        before = e[max(0, f - 4):f].min() if f > 0 else 0.0
        jump = e[f:f + 4].max() - before
        return float(np.sqrt(max(0.0, jump) / ref[band]))

    # timing: spectral flux across all bands
    flux = np.maximum.reduce([band_flux(S, freqs, *bands[k]) for k in ("low", "lowmid", "mid", "high")])
    delta = max(0.02, 0.12 * (1.6 - sensitivity))  # sensitivity 0.1 .. 1.5
    frames = librosa.util.peak_pick(flux, pre_max=3, post_max=3, pre_avg=10, post_avg=10,
                                    delta=delta, wait=max(1, int(0.05 * sr / HOP)))
    k = 1.6 - sensitivity
    thr, snare_thr, tom_thr = 0.25 * k, 0.35 * k, 0.3 * k
    fps = sr / HOP
    f150, f450 = int(0.15 * fps), int(0.45 * fps)
    tom_bins = (freqs >= 60) & (freqs < 400)

    length = 60.0 / bpm / 4  # sixteenth note
    notes, counts = [], {p: 0 for p in DRUM_NOTES}
    for f in frames:
        l, lm, m, up, h = (rise(b, f) for b in ("low", "lowmid", "mid", "upper", "high"))
        mid_ring = ring_ratio(env["mid"], f, f150)
        high_ring = ring_ratio(env["high"], f, f150)
        high_long = ring_ratio(env["high"], f, f450)
        found = []

        # Snare: strong mid crack that dies away fast (rides and crashes keep ringing).
        is_snare = m > snare_thr and mid_ring < 0.35
        # Crash: big, bright and still ringing half a second later.
        is_crash = h > thr * 1.5 and high_long > 0.35

        # Kick or tom: both thump; toms sit higher in pitch and ring on.
        if l > thr or lm > tom_thr:
            spec = S[tom_bins, f:f + int(0.1 * fps)].mean(axis=1)
            pitch = freqs[tom_bins][int(np.argmax(spec))]
            tom_ring = ring_ratio(env["lowmid"], f, f150)
            if pitch >= 95 and tom_ring > 0.1 and lm > tom_thr and not is_snare:
                tom = "tom_hi" if pitch >= 170 else "tom_mid" if pitch >= 120 else "tom_low"
                found.append((tom, lm))
            elif l > thr:
                found.append(("kick", l))
        if is_snare:
            found.append(("snare", m))
        if is_crash:
            found.append(("crash", h))
        elif not is_snare and (h > thr or up > thr):
            if high_ring > 0.3 or ring_ratio(env["upper"], f, f150) > 0.3:
                # rides "ping" lower than hats; hats are mostly very high fizz
                found.append(("ride" if up > h * 1.1 else "openhat", max(h, up)))
            elif h > thr:
                found.append(("hihat", h))

        t = snap(max(0.0, librosa.frames_to_time(f, sr=sr, hop_length=HOP) - pad / sr), bpm, grid)
        for part, strength in found:
            if part == "openhat" and part not in want and "hihat" in want:
                part = "hihat"  # open hats become closed hats if open hats are switched off
            if part in want:
                vel = int(np.clip(45 + min(strength, 1.0) * 82, 1, 127))
                notes.append((t, t + length, int(note_map[part]), vel))
                counts[part] += 1
    for part in DRUM_NOTES:
        if part in want:
            log(f"  {part}: {counts[part]} hits")
    return clean_overlaps(notes)


# --------------------------------------------------------------------------- pitched (single line)

def transcribe_mono(y, sr, bpm, grid, stem_type, sensitivity, log):
    lo, hi = PITCH_RANGES[stem_type]
    f0, voiced, prob = librosa.pyin(y, fmin=librosa.note_to_hz(lo), fmax=librosa.note_to_hz(hi),
                                    sr=sr, frame_length=2048, hop_length=HOP)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0]
    n = min(len(f0), len(rms))
    f0, voiced, prob, rms = f0[:n], voiced[:n], prob[:n], rms[:n]

    peak_rms = rms.max() if rms.max() > 0 else 1.0
    loud = rms > peak_rms * 0.03 * (1.6 - sensitivity)
    pitch = np.where(voiced & loud & (prob > 0.05), np.round(librosa.hz_to_midi(f0)), -1)
    pitch = np.nan_to_num(pitch, nan=-1).astype(int)
    pitch = scipy.ndimage.median_filter(pitch, size=5)  # smooth out flickers

    # new attacks split repeated notes of the same pitch (e.g. G G G on the bass)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    onsets = set(librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=HOP).tolist())

    notes, i = [], 0
    min_len = 0.07
    while i < n:
        if pitch[i] < 0:
            i += 1
            continue
        j = i
        while j + 1 < n and pitch[j + 1] == pitch[i] and not ((j + 1) in onsets and j + 1 - i > 6):
            j += 1
        start = librosa.frames_to_time(i, sr=sr, hop_length=HOP)
        end = librosa.frames_to_time(j + 1, sr=sr, hop_length=HOP)
        if end - start >= min_len:
            vel = int(np.clip(40 + 87 * np.sqrt(rms[i:j + 1].max() / peak_rms), 1, 127))
            s, e = snap(start, bpm, grid), snap(end, bpm, grid)
            if e <= s:
                e = s + (60.0 / bpm / (grid or 4))
            notes.append((s, e, int(pitch[i]), vel))
        i = j + 1
    log(f"  {len(notes)} notes")
    return clean_overlaps(notes)


# --------------------------------------------------------------------------- polyphonic

def transcribe_poly_basic_pitch(path, bpm, grid, stem_type, sensitivity, log):
    from basic_pitch.inference import predict  # optional, higher quality
    lo, hi = PITCH_RANGES[stem_type]
    _, _, events = predict(path,
                           onset_threshold=float(np.clip(0.5 * (1.6 - sensitivity), 0.2, 0.8)),
                           frame_threshold=0.3,
                           minimum_note_length=80,
                           minimum_frequency=librosa.note_to_hz(lo),
                           maximum_frequency=librosa.note_to_hz(hi))
    notes = []
    for start, end, pitch, amp, *_ in events:
        s, e = snap(start, bpm, grid), snap(end, bpm, grid)
        if e <= s:
            e = s + (60.0 / bpm / (grid or 4))
        notes.append((s, e, int(pitch), int(np.clip(30 + amp * 97, 1, 127))))
    log(f"  {len(notes)} notes (basic-pitch)")
    return clean_overlaps(notes)


def transcribe_poly_simple(y, sr, bpm, grid, stem_type, sensitivity, log):
    """Lightweight fallback when basic-pitch isn't installed: CQT peaks + harmonic cleanup."""
    lo, hi = PITCH_RANGES[stem_type]
    lo_m, hi_m = int(librosa.note_to_midi(lo)), int(librosa.note_to_midi(hi))
    n_bins = hi_m - lo_m + 1
    C = np.abs(librosa.cqt(y, sr=sr, hop_length=512, fmin=librosa.midi_to_hz(lo_m),
                           n_bins=n_bins, bins_per_octave=12))
    D = librosa.amplitude_to_db(C, ref=np.max)
    thresh = -30 - 10 * sensitivity  # dB below the loudest moment
    active = D > thresh

    # keep local peaks across pitch, and drop likely overtones of a louder lower note
    peaks = np.zeros_like(active)
    peaks[1:-1] = (D[1:-1] >= D[:-2]) & (D[1:-1] >= D[2:])
    active &= peaks
    for k, ratio in ((12, 0.0), (19, 3.0), (24, 6.0)):
        lower = np.zeros_like(D) - 200
        lower[k:] = D[:-k]
        lower_active = np.zeros_like(active)
        lower_active[k:] = active[:-k]
        active &= ~(lower_active & (D < lower + ratio))
    active = scipy.ndimage.binary_closing(active, structure=np.ones((1, 3)))

    hop_t = 512 / sr
    notes = []
    for b in range(n_bins):
        row = active[b]
        idx = np.flatnonzero(np.diff(np.concatenate(([0], row.astype(int), [0]))))
        for s_i, e_i in zip(idx[::2], idx[1::2]):
            start, end = s_i * hop_t, e_i * hop_t
            if end - start < 0.1:
                continue
            level = D[b, s_i:e_i].max()
            vel = int(np.clip(127 + level * 2.2, 25, 127))
            s, e = snap(start, bpm, grid), snap(end, bpm, grid)
            if e <= s:
                e = s + (60.0 / bpm / (grid or 4))
            notes.append((s, e, lo_m + b, vel))
    log(f"  {len(notes)} notes (built-in polyphonic mode; install basic-pitch for better chords)")
    return clean_overlaps(notes)


# --------------------------------------------------------------------------- tempo

def detect_tempo(path, log=log_default):
    """Measure a stem's real tempo. Suno often plays a little faster or slower than the prompt asked,
    so this checks which tempo makes the hits line up best with a 1/16-note grid."""
    y, sr = librosa.load(path, sr=22050, mono=True)
    hop = 256
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    rough, _ = librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=hop)
    rough = float(np.atleast_1d(rough)[0]) or 120.0
    onsets = librosa.onset.onset_detect(onset_envelope=env, sr=sr, hop_length=hop, units="time")
    if len(onsets) < 8:
        return round(rough, 1)
    strength = env[librosa.time_to_frames(onsets, sr=sr, hop_length=hop)]
    weights = strength / strength.sum()

    def misfit(bpm):
        step = 60.0 / bpm / 4
        best = 1.0
        for off in np.linspace(0, step, 24, endpoint=False):
            r = (onsets - off) / step
            best = min(best, float(np.sum(weights * np.abs(r - np.round(r)))))
        return best

    # Refine only near the beat tracker's estimate. (Trying half or double speed would always
    # "win", because a finer grid fits more hits, so the octave comes from the beat tracker.)
    best_bpm, best_err = rough, 1.0
    for c in (rough,):  # coarse, then fine search
        for bpm in np.arange(c - 4, c + 4.01, 0.25):
            e = misfit(bpm)
            if e < best_err:
                best_bpm, best_err = bpm, e
    for bpm in np.arange(best_bpm - 0.3, best_bpm + 0.31, 0.05):
        e = misfit(bpm)
        if e < best_err:
            best_bpm, best_err = bpm, e
    return round(float(best_bpm), 1)


# --------------------------------------------------------------------------- humanize

def humanize(notes, bpm, amount, is_drums, seed=7):
    """Nudge timing and velocity a little so the part feels played rather than programmed.
    amount: 0 (off) .. 1 (strong). Same seed = same result, so a preview matches the saved file."""
    if amount <= 0:
        return notes
    rng = np.random.default_rng(seed)
    max_shift = 0.018 * amount            # up to ~18 ms early/late
    vel_spread = 14 * amount              # velocity wobble
    out = []
    for start, end, note, vel in notes:
        shift = float(np.clip(rng.normal(0, max_shift / 2), -max_shift, max_shift))
        # downbeats stay a touch steadier and stronger, like a real player
        beat_pos = (start * bpm / 60.0) % 1.0
        on_beat = beat_pos < 0.05 or beat_pos > 0.95
        if on_beat:
            shift *= 0.5
        v = vel + rng.normal(0, vel_spread / 2) + (4 * amount if on_beat else 0)
        if is_drums and not on_beat:
            v -= 3 * amount  # off-beat hits a little softer
        new_start = max(0.0, start + shift)
        out.append((new_start, max(new_start + 0.01, end + shift), note, int(np.clip(round(v), 1, 127))))
    return out


# --------------------------------------------------------------------------- main conversion

_cache = {}


def transcribe(path, stem_type="auto", bpm=None, grid=4, sensitivity=0.8,
               drum_parts=DEFAULT_DRUM_PARTS, log=log_default, drum_map=None, humanize_amount=0.0):
    """Turn one stem into notes. Returns a dict, or None if the stem is silent."""
    if stem_type == "auto":
        stem_type = guess_type(path)
    drum_map = {**DRUM_NOTES, **(drum_map or {})}
    key = (os.path.abspath(path), os.path.getmtime(path), stem_type, bpm, grid, round(sensitivity, 3),
           tuple(sorted(drum_parts)), tuple(sorted(drum_map.items())), round(humanize_amount, 3))
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

    if stem_type == "drums":
        notes = transcribe_drums(y, sr, bpm, grid_steps, sensitivity, set(drum_parts), log, drum_map)
        channel, program = 9, None
    elif stem_type in ("bass", "vocal"):
        notes = transcribe_mono(y, sr, bpm, grid_steps, stem_type, sensitivity, log)
        channel, program = 0, PROGRAMS[stem_type]
    else:
        try:
            notes = transcribe_poly_basic_pitch(path, bpm, grid_steps, stem_type, sensitivity, log)
        except ImportError:
            notes = transcribe_poly_simple(y, sr, bpm, grid_steps, stem_type, sensitivity, log)
        except Exception as exc:  # basic-pitch installed but failed -> still produce a file
            log(f"  basic-pitch failed ({exc}); using built-in mode")
            notes = transcribe_poly_simple(y, sr, bpm, grid_steps, stem_type, sensitivity, log)
        channel, program = 0, PROGRAMS[stem_type]

    if humanize_amount > 0:
        notes = humanize(notes, bpm, humanize_amount, stem_type == "drums")
        log(f"  humanized ({int(humanize_amount * 100)}%)")

    result = {"notes": notes, "bpm": bpm, "stem_type": stem_type, "channel": channel,
              "program": program, "drum_map": drum_map, "path": path}
    _cache[key] = result
    return result


def save_result(result, out_dir=None, log=log_default):
    path, stem_type = result["path"], result["stem_type"]
    out_dir = out_dir or os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    out_path = os.path.join(out_dir, f"{base} - {stem_type}.mid")
    write_midi(result["notes"], out_path, result["bpm"], f"{base} ({stem_type})",
               result["channel"], result["program"])
    log(f"  saved: {out_path}")
    return out_path


def convert(path, stem_type="auto", bpm=None, grid=4, sensitivity=0.8,
            drum_parts=DEFAULT_DRUM_PARTS, out_dir=None, log=log_default, drum_map=None, humanize_amount=0.0):
    result = transcribe(path, stem_type, bpm, grid, sensitivity, drum_parts, log, drum_map, humanize_amount)
    return save_result(result, out_dir, log) if result else None


# --------------------------------------------------------------------------- preview

PREVIEW_SR = 22050


def _drum_sound(part, vel, sr, rng):
    v = vel / 127.0
    if part == "kick":
        t = np.arange(int(0.35 * sr)) / sr
        return np.sin(2 * np.pi * (50 + 70 * np.exp(-t * 35)) * t) * np.exp(-t * 9) * v
    if part == "snare":
        t = np.arange(int(0.25 * sr)) / sr
        return (rng.normal(0, 0.5, t.size) * np.exp(-t * 22) + 0.4 * np.sin(2 * np.pi * 185 * t) * np.exp(-t * 25)) * v
    if part in ("hihat", "openhat", "crash", "ride"):
        length, decay, gain = {"hihat": (0.08, 70, 0.35), "openhat": (0.4, 9, 0.3),
                               "crash": (1.4, 2.5, 0.4), "ride": (0.6, 6, 0.25)}[part]
        t = np.arange(int(length * sr)) / sr
        noise = np.diff(rng.normal(0, 1, t.size + 1))  # brightened noise
        return noise * np.exp(-t * decay) * gain * v
    pitch = {"tom_hi": 200, "tom_mid": 150, "tom_low": 105}.get(part, 150)
    t = np.arange(int(0.45 * sr)) / sr
    return np.sin(2 * np.pi * pitch * (1 + 0.15 * np.exp(-t * 20)) * t) * np.exp(-t * 7) * v


def _tone(note, dur, vel, stem_type, sr):
    f = 440.0 * 2 ** ((note - 69) / 12)
    n = max(1, int(min(dur, 4.0) * sr))
    t = np.arange(n) / sr
    harmonics = [(1, 1.0), (2, 0.5), (3, 0.25)] if stem_type == "bass" else \
                [(1, 1.0), (2, 0.15)] if stem_type == "vocal" else [(1, 1.0), (2, 0.35), (3, 0.15), (4, 0.08)]
    wave = sum(a * np.sin(2 * np.pi * f * k * t) for k, a in harmonics)
    attack = np.minimum(1.0, t / 0.008)
    release = np.minimum(1.0, (t[-1] - t + 1e-3) / 0.03)
    decay = np.exp(-t * (1.5 if stem_type in ("synth", "vocal") else 3.0))
    return wave * attack * release * decay * (vel / 127.0) * 0.4


def render_preview(result, out_wav, include_original=False, original_gain=0.5):
    """Play the notes back with simple built-in sounds and write a WAV you can listen to."""
    import wave
    sr = PREVIEW_SR
    notes = result["notes"]
    length = (max((e for _, e, _, _ in notes), default=0) + 2.0)
    original = None
    if include_original:
        original, _ = librosa.load(result["path"], sr=sr, mono=True)
        length = max(length, original.size / sr)
    mix = np.zeros(int(length * sr) + sr)
    rng = np.random.default_rng(1)
    note_to_part = {}
    for part, n in result["drum_map"].items():
        note_to_part.setdefault(n, part)
    for start, end, note, vel in notes:
        if result["stem_type"] == "drums":
            sound = _drum_sound(note_to_part.get(note, "snare"), vel, sr, rng)
        else:
            sound = _tone(note, end - start, vel, result["stem_type"], sr)
        i = int(start * sr)
        j = min(mix.size, i + sound.size)
        mix[i:j] += sound[:j - i]
    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.8
    if original is not None:
        o = original / (np.max(np.abs(original)) or 1.0) * original_gain
        mix[:o.size] = mix[:o.size] * 0.8 + o
        mix /= max(1.0, np.max(np.abs(mix)) / 0.95)
    pcm = (np.clip(mix, -1, 1) * 32767).astype("<i2")
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return out_wav


class Player:
    """Plays a WAV in the background and can stop it. Uses Windows' built-in player when available."""

    def __init__(self):
        self.proc = None

    def play(self, wav):
        self.stop()
        if sys.platform.startswith("win"):
            import winsound
            winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            import shutil
            import subprocess
            for cmd in (["afplay"], ["aplay", "-q"], ["paplay"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
                if shutil.which(cmd[0]):
                    self.proc = subprocess.Popen(cmd + [wav])
                    return
            raise RuntimeError("no audio player found")

    def stop(self):
        if sys.platform.startswith("win"):
            import winsound
            winsound.PlaySound(None, 0)
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = None


# --------------------------------------------------------------------------- window

THEME = {
    "bg": "#1b1e22", "card": "#252a30", "field": "#14171a", "line": "#353b43",
    "text": "#e8eaed", "muted": "#9aa3ad", "accent": "#18c6cc", "accent_hover": "#3fd8dd",
    "accent_text": "#0d1013", "ok": "#4cd08a", "warn": "#f0b84a",
}
GRID_CHOICES = {"Off (keep original timing)": 0, "1/8 note": 2, "1/8 triplet": 3,
                "1/16 note": 4, "1/32 note": 8}
KIT_BOXES = [  # (label shown, part name, default on) - named like MT Power Drumkit's channels
    ("Kick", "kick", True), ("Snare", "snare", True), ("Hi-Hat cl.", "hihat", True),
    ("Hi-Hat op.", "openhat", True), ("Toms", "toms", True), ("Crash", "crash", False),
    ("Ride", "ride", False),
]


def run_gui():
    import queue
    import subprocess
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import filedialog, ttk

    T = THEME
    root = tk.Tk()
    root.title("Stemquill")
    root.configure(bg=T["bg"])
    root.minsize(820, 560)
    root.geometry("860x900")

    families = set(tkfont.families())
    family = next((f for f in ("Segoe UI", "Inter", "Helvetica Neue", "DejaVu Sans") if f in families),
                  tkfont.nametofont("TkDefaultFont").actual("family"))
    F = {
        "title": (family, 20, "bold"), "sub": (family, 10), "h": (family, 11, "bold"),
        "body": (family, 10), "small": (family, 9), "btn": (family, 10, "bold"),
        "big": (family, 12, "bold"), "mono": ("Consolas" if "Consolas" in families else "DejaVu Sans Mono", 9),
    }

    # ---- styles
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=T["bg"], foreground=T["text"], font=F["body"],
                 bordercolor=T["line"], lightcolor=T["line"], darkcolor=T["line"], troughcolor=T["field"],
                 fieldbackground=T["field"], focuscolor=T["accent"], selectbackground=T["accent"],
                 selectforeground=T["accent_text"], insertcolor=T["text"])
    st.configure("TFrame", background=T["bg"])
    st.configure("Card.TFrame", background=T["card"], relief="flat")
    st.configure("TLabel", background=T["bg"], foreground=T["text"])
    st.configure("Card.TLabel", background=T["card"])
    st.configure("Muted.TLabel", background=T["card"], foreground=T["muted"], font=F["small"])
    st.configure("Head.TLabel", background=T["card"], foreground=T["text"], font=F["h"])
    st.configure("Title.TLabel", font=F["title"])
    st.configure("Sub.TLabel", foreground=T["muted"], font=F["sub"])
    st.configure("Value.TLabel", background=T["card"], foreground=T["accent"], font=F["btn"])
    st.configure("TButton", background=T["line"], foreground=T["text"], font=F["btn"],
                 borderwidth=0, padding=(12, 6))
    st.map("TButton", background=[("active", "#434a53"), ("disabled", T["card"])],
           foreground=[("disabled", T["muted"])])
    st.configure("Accent.TButton", background=T["accent"], foreground=T["accent_text"], font=F["big"],
                 padding=(18, 10))
    st.map("Accent.TButton", background=[("active", T["accent_hover"]), ("disabled", T["line"])],
           foreground=[("disabled", T["muted"])])
    st.configure("TCheckbutton", background=T["card"], foreground=T["text"], indicatorbackground=T["field"],
                 indicatorforeground=T["accent"], indicatormargin=4)
    st.map("TCheckbutton", background=[("active", T["card"])],
           indicatorbackground=[("selected", T["accent"]), ("active", T["line"])],
           indicatorforeground=[("selected", T["accent_text"])])
    for w in ("TCombobox", "TSpinbox", "TEntry"):
        st.configure(w, fieldbackground=T["field"], background=T["line"], foreground=T["text"],
                     arrowcolor=T["text"], padding=5)
        st.map(w, fieldbackground=[("readonly", T["field"])], foreground=[("readonly", T["text"])],
               selectbackground=[("readonly", T["field"])], selectforeground=[("readonly", T["text"])])
    st.configure("Horizontal.TScale", background=T["accent"], troughcolor=T["field"], sliderthickness=16)
    st.configure("Horizontal.TProgressbar", background=T["accent"], troughcolor=T["field"], thickness=6)
    root.option_add("*TCombobox*Listbox.background", T["field"])
    root.option_add("*TCombobox*Listbox.foreground", T["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", T["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", T["accent_text"])
    root.option_add("*TCombobox*Listbox.font", F["body"])

    # ---- state
    files = []
    type_var = tk.StringVar(value="auto")
    bpm_var = tk.StringVar(value="120")
    grid_var = tk.StringVar(value="Off (keep original timing)")
    SENS_MIN, SENS_MAX = 0.1, 1.5
    sens_var = tk.DoubleVar(value=0.8)
    sens_text = tk.StringVar(value="0.80")
    out_dir = {"path": None}
    out_text = tk.StringVar(value="Same folder as each stem")
    kit_vars = {part: tk.BooleanVar(value=on) for _, part, on in KIT_BOXES}
    last_out = {"dir": None}

    # Everything sits in a scrollable area so the window also fits smaller laptop screens.
    canvas = tk.Canvas(root, bg=T["bg"], highlightthickness=0)
    vbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vbar.set)
    vbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    outer = ttk.Frame(canvas, padding=(20, 14))
    outer_id = canvas.create_window((0, 0), window=outer, anchor="nw")
    outer.columnconfigure(0, weight=1)
    outer.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(outer_id, width=e.width))

    def on_wheel(event):
        if outer.winfo_height() > canvas.winfo_height():
            step = -1 if (event.num == 4 or event.delta > 0) else 1
            canvas.yview_scroll(step * 2, "units")
    root.bind_all("<MouseWheel>", on_wheel)
    root.bind_all("<Button-4>", on_wheel)
    root.bind_all("<Button-5>", on_wheel)

    # ---- header
    head = ttk.Frame(outer)
    head.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    ttk.Label(head, text="Stemquill", style="Title.TLabel").pack(anchor="w")
    ttk.Label(head, text="Turn audio stems into MIDI you can play through your own instruments in any DAW",
              style="Sub.TLabel").pack(anchor="w")

    def card(row, title, hint=None):
        c = ttk.Frame(outer, style="Card.TFrame", padding=(16, 10))
        c.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        c.columnconfigure(1, weight=1)
        top = ttk.Frame(c, style="Card.TFrame")
        top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Label(top, text=title, style="Head.TLabel").pack(side="left")
        if hint:
            ttk.Label(top, text=hint, style="Muted.TLabel").pack(side="left", padx=(10, 0))
        return c

    # ---- 1. stems
    c1 = card(1, "1  Stems", "Drums, Bass, Vocals or Other from Suno; the type is read from the name")
    listbox = tk.Listbox(c1, height=3, bg=T["field"], fg=T["text"], selectbackground=T["accent"],
                         selectforeground=T["accent_text"], highlightthickness=1, highlightbackground=T["line"],
                         highlightcolor=T["accent"], relief="flat", font=F["body"], activestyle="none",
                         selectmode="extended")
    listbox.grid(row=1, column=0, columnspan=2, sticky="ew")
    btns = ttk.Frame(c1, style="Card.TFrame")
    btns.grid(row=1, column=2, sticky="ns", padx=(10, 0))

    def refresh_list():
        listbox.delete(0, "end")
        for f in files:
            kind = type_var.get() if type_var.get() != "auto" else guess_type(f)
            listbox.insert("end", f"  {os.path.basename(f)}    \u00b7    {kind}")
        if not files:
            listbox.insert("end", "  No stems yet. Click Add stems...")
            listbox.itemconfig(0, fg=T["muted"])
        update_kit_state()

    def add_files():
        chosen = filedialog.askopenfilenames(
            title="Choose stems",
            filetypes=[("Audio", "*.wav *.mp3 *.flac *.aif *.aiff *.ogg *.m4a"), ("All files", "*.*")])
        for f in chosen:
            if f not in files:
                files.append(f)
        refresh_list()

    def remove_selected():
        if not files:
            return
        for i in sorted(listbox.curselection(), reverse=True):
            if i < len(files):
                files.pop(i)
        refresh_list()

    def clear_files():
        files.clear()
        refresh_list()

    ttk.Button(btns, text="Add stems...", command=add_files).pack(fill="x")
    ttk.Button(btns, text="Remove", command=remove_selected).pack(fill="x", pady=6)
    ttk.Button(btns, text="Clear", command=clear_files).pack(fill="x")

    # ---- 2. settings
    c2 = card(2, "2  Settings", "Match the tempo to your DAW project")

    def row_label(r, text, hint=None):
        ttk.Label(c2, text=text, style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=4, padx=(0, 16))
        if hint:
            ttk.Label(c2, text=hint, style="Muted.TLabel").grid(row=r, column=2, sticky="w", padx=(12, 0))

    row_label(1, "Stem type", "auto reads the file name")
    type_box = ttk.Combobox(c2, textvariable=type_var, values=["auto"] + STEM_TYPES, state="readonly", width=24)
    type_box.grid(row=1, column=1, sticky="w")
    type_box.bind("<<ComboboxSelected>>", lambda e: refresh_list())

    row_label(2, "Tempo (BPM)")
    tempo_f = ttk.Frame(c2, style="Card.TFrame")
    tempo_f.grid(row=2, column=1, columnspan=2, sticky="w")
    ttk.Spinbox(tempo_f, from_=40, to=240, increment=0.1, textvariable=bpm_var, width=8).pack(side="left")
    detect_btn = ttk.Button(tempo_f, text="Detect", width=8)
    detect_btn.pack(side="left", padx=(8, 0))
    tempo_hint = tk.StringVar(value="must match the song and your DAW project; Detect measures it from a stem")
    ttk.Label(tempo_f, textvariable=tempo_hint, style="Muted.TLabel").pack(side="left", padx=(12, 0))

    row_label(3, "Snap to grid", "Off is safest for Suno stems")
    ttk.Combobox(c2, textvariable=grid_var, values=list(GRID_CHOICES), state="readonly", width=24)\
        .grid(row=3, column=1, sticky="w")

    def clamp(v):
        return max(SENS_MIN, min(SENS_MAX, v))

    def on_slide(value):
        sens_text.set(f"{float(value):.2f}")

    def on_typed(*_):
        try:
            v = clamp(float(sens_text.get()))
        except ValueError:
            v = sens_var.get()
        sens_var.set(v)
        sens_text.set(f"{v:.2f}")

    row_label(4, "Sensitivity")
    sens = ttk.Frame(c2, style="Card.TFrame")
    sens.grid(row=4, column=1, columnspan=2, sticky="w")
    ttk.Label(sens, text="fewer notes", style="Muted.TLabel").pack(side="left")
    tk.Scale(sens, from_=SENS_MIN, to=SENS_MAX, resolution=0.01, variable=sens_var, orient="horizontal",
             length=240, showvalue=False, command=on_slide, bg=T["accent"], activebackground=T["accent_hover"],
             troughcolor=T["field"], highlightthickness=0, bd=0, sliderrelief="flat", sliderlength=18,
             width=10).pack(side="left", padx=8)
    ttk.Label(sens, text="more notes", style="Muted.TLabel").pack(side="left")
    sbox = ttk.Spinbox(sens, from_=SENS_MIN, to=SENS_MAX, increment=0.05, width=6, textvariable=sens_text,
                       command=on_typed, format="%.2f")
    sbox.pack(side="left", padx=(14, 0))
    sbox.bind("<Return>", on_typed)
    sbox.bind("<FocusOut>", on_typed)

    human_var = tk.IntVar(value=0)
    human_text = tk.StringVar()

    def show_human(*_):
        v = human_var.get()
        word = "off" if v == 0 else "subtle" if v <= 30 else "natural" if v <= 65 else "loose"
        human_text.set(f"{v}%  ({word})")
    human_var.trace_add("write", show_human)
    show_human()
    row_label(5, "Humanize")
    hum = ttk.Frame(c2, style="Card.TFrame")
    hum.grid(row=5, column=1, columnspan=2, sticky="w")
    ttk.Label(hum, text="tight", style="Muted.TLabel").pack(side="left")
    tk.Scale(hum, from_=0, to=100, resolution=5, variable=human_var, orient="horizontal", length=240,
             showvalue=False, bg=T["accent"], activebackground=T["accent_hover"], troughcolor=T["field"],
             highlightthickness=0, bd=0, sliderrelief="flat", sliderlength=18, width=10).pack(side="left", padx=8)
    ttk.Label(hum, text="loose", style="Muted.TLabel").pack(side="left")
    ttk.Label(hum, textvariable=human_text, style="Value.TLabel").pack(side="left", padx=(14, 0))
    ttk.Label(c2, text="Humanize adds small timing and velocity changes so parts feel played, not programmed.",
              style="Muted.TLabel").grid(row=6, column=1, columnspan=2, sticky="w", pady=(0, 2))

    # ---- 3. drum kit
    c3 = card(3, "3  Drum kit", "Drum stems only: which drums to write, and which note each one goes on")
    kit = ttk.Frame(c3, style="Card.TFrame")
    kit.grid(row=1, column=0, columnspan=3, sticky="w")
    kit_checks = []
    for i, (label, part, _) in enumerate(KIT_BOXES):
        cb = ttk.Checkbutton(kit, text=label, variable=kit_vars[part])
        cb.grid(row=0, column=i, sticky="w", padx=(0, 18), pady=2)
        kit_checks.append(cb)
    kit_note = ttk.Label(c3, text="Crash and Ride start off: they can bring back metallic sounds.",
                         style="Muted.TLabel")
    kit_note.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

    # drum map: which note each drum is written on
    mapf = ttk.Frame(c3, style="Card.TFrame")
    mapf.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0))
    ttk.Label(mapf, text="Drum map", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12))
    label_to_key = {v: k for k, v in DRUM_MAP_LABELS.items()}
    saved = load_settings()
    start_key = saved.get("drum_map", "General MIDI")
    if start_key not in DRUM_MAP_LABELS:
        start_key = "General MIDI"
    map_var = tk.StringVar(value=DRUM_MAP_LABELS[start_key])
    map_box = ttk.Combobox(mapf, textvariable=map_var, values=list(DRUM_MAP_LABELS.values()),
                           state="readonly", width=48)
    map_box.grid(row=0, column=1, columnspan=9, sticky="w")

    start_notes = DRUM_MAPS.get(start_key) or {**DRUM_NOTES, **saved.get("custom_map", {})}
    note_vars, name_vars = {}, {}
    applying = {"on": False}

    def show_name(part):
        try:
            name_vars[part].set(note_name(int(note_vars[part].get())))
        except (ValueError, TypeError):
            name_vars[part].set("?")

    for col, part in enumerate(DRUM_LABELS):
        ttk.Label(mapf, text=DRUM_LABELS[part], style="Muted.TLabel").grid(row=1, column=col + 1, sticky="w",
                                                                         pady=(8, 2), padx=(0, 6))
        note_vars[part] = tk.StringVar(value=str(start_notes[part]))
        name_vars[part] = tk.StringVar()
        box = ttk.Spinbox(mapf, from_=0, to=127, increment=1, width=4, textvariable=note_vars[part])
        box.grid(row=2, column=col + 1, sticky="w", padx=(0, 6))
        ttk.Label(mapf, textvariable=name_vars[part], style="Muted.TLabel").grid(row=3, column=col + 1, sticky="w")
        show_name(part)

        def on_edit(*_, part=part):
            show_name(part)
            if not applying["on"]:
                map_var.set(DRUM_MAP_LABELS["Custom"])  # typing a note makes it a custom map
        note_vars[part].trace_add("write", on_edit)
    ttk.Label(mapf, text="Note numbers. Names use 36 = C1; some DAWs label octaves differently, the note is the same.",
              style="Muted.TLabel").grid(row=4, column=1, columnspan=9, sticky="w", pady=(4, 0))

    def on_map_pick(*_):
        key = label_to_key[map_var.get()]
        notes_for = DRUM_MAPS.get(key) or {**DRUM_NOTES, **load_settings().get("custom_map", {})}
        applying["on"] = True
        for part, var in note_vars.items():
            var.set(str(notes_for[part]))
        applying["on"] = False
    map_box.bind("<<ComboboxSelected>>", on_map_pick)

    def current_map():
        """Read the note boxes; returns (map, error message or None)."""
        out = {}
        for part, var in note_vars.items():
            try:
                n = int(var.get())
                if not 0 <= n <= 127:
                    raise ValueError
            except ValueError:
                return None, f"{DRUM_LABELS[part]} needs a note number from 0 to 127"
            out[part] = n
        return out, None

    def update_kit_state():
        drums_possible = type_var.get() in ("auto", "drums")
        for cb in kit_checks:
            cb.state(["!disabled"] if drums_possible else ["disabled"])
        try:
            map_box.state(["!disabled", "readonly"] if drums_possible else ["disabled"])
        except NameError:
            pass

    # ---- 4. output
    c4 = card(4, "4  Save to")
    ttk.Label(c4, textvariable=out_text, style="Card.TLabel").grid(row=1, column=0, columnspan=2, sticky="w")
    ob = ttk.Frame(c4, style="Card.TFrame")
    ob.grid(row=1, column=2, sticky="e")

    def pick_out():
        d = filedialog.askdirectory(title="Save MIDI files to")
        if d:
            out_dir["path"] = d
            out_text.set(d)

    def reset_out():
        out_dir["path"] = None
        out_text.set("Same folder as each stem")

    ttk.Button(ob, text="Change...", command=pick_out).pack(side="left")
    ttk.Button(ob, text="Reset", command=reset_out).pack(side="left", padx=(6, 0))

    # ---- convert + progress + log
    prev = ttk.Frame(outer, style="Card.TFrame", padding=(16, 10))
    prev.grid(row=5, column=0, sticky="ew", pady=(0, 10))
    ttk.Label(prev, text="Preview", style="Head.TLabel").pack(side="left")
    ttk.Label(prev, text="hear the selected stem as MIDI before saving", style="Muted.TLabel")\
        .pack(side="left", padx=(10, 16))
    play_btn = ttk.Button(prev, text="Play", width=8)
    play_btn.pack(side="left")
    stop_btn = ttk.Button(prev, text="Stop", width=8)
    stop_btn.pack(side="left", padx=(6, 14))
    with_orig = tk.BooleanVar(value=True)
    ttk.Checkbutton(prev, text="Mix in the original stem", variable=with_orig).pack(side="left")

    action = ttk.Frame(outer)
    action.grid(row=6, column=0, sticky="ew", pady=(4, 8))
    action.columnconfigure(1, weight=1)
    go = ttk.Button(action, text="Convert to MIDI", style="Accent.TButton")
    go.grid(row=0, column=0, sticky="w")
    status = tk.StringVar(value="Ready")
    status_lbl = ttk.Label(action, textvariable=status, foreground=T["muted"])
    status_lbl.grid(row=0, column=1, sticky="w", padx=14)
    open_btn = ttk.Button(action, text="Open folder")
    open_btn.grid(row=0, column=2, sticky="e")
    open_btn.state(["disabled"])
    progress = ttk.Progressbar(outer, mode="determinate", style="Horizontal.TProgressbar")
    progress.grid(row=7, column=0, sticky="ew", pady=(0, 8))

    logbox = tk.Text(outer, height=7, bg=T["field"], fg=T["muted"], insertbackground=T["text"], relief="flat",
                     font=F["mono"], highlightthickness=1, highlightbackground=T["line"], padx=10, pady=8,
                     wrap="word")
    logbox.grid(row=8, column=0, sticky="nsew")
    logbox.tag_configure("ok", foreground=T["ok"])
    logbox.tag_configure("warn", foreground=T["warn"])
    logbox.tag_configure("head", foreground=T["text"])

    # The conversion runs in a background thread; it hands updates to the window through
    # this queue, and the window picks them up every 100 ms (Tk is only safe on its own thread).
    updates = queue.Queue()

    def log(msg):
        updates.put(("log", msg))

    def write_log(msg):
        tag = "ok" if msg.strip().startswith(("saved", "Done")) else \
              "warn" if ("Error" in msg or "skipped" in msg or "failed" in msg or "Nothing" in msg) else \
              "head" if "->" in msg else ""
        logbox.insert("end", msg + "\n", tag)
        logbox.see("end")

    def poll():
        try:
            while True:
                kind, *args = updates.get_nowait()
                if kind == "log":
                    write_log(*args)
                elif kind == "status":
                    status.set(args[0])
                    progress.configure(value=args[1])
                elif kind == "done":
                    finish(*args)
                elif kind == "call":
                    args[0]()
        except queue.Empty:
            pass
        root.after(100, poll)

    def open_folder():
        d = last_out["dir"]
        if not d:
            return
        if sys.platform.startswith("win"):
            os.startfile(d)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", d])
        else:
            subprocess.Popen(["xdg-open", d])

    open_btn.configure(command=open_folder)

    busy_buttons = [go, play_btn, detect_btn]
    player = Player()
    preview_wav = os.path.join(__import__("tempfile").gettempdir(), "stemquill_preview.wav")

    def set_busy(on):
        for b in busy_buttons:
            b.state(["disabled"] if on else ["!disabled"])

    def say(msg, color="muted"):
        status.set(msg)
        status_lbl.configure(foreground=T[color])

    def finish(ok_count, total):
        set_busy(False)
        progress["value"] = total
        say(f"Done: {ok_count} of {total} converted" if total else "Ready", "ok" if ok_count == total else "warn")
        if last_out["dir"]:
            open_btn.state(["!disabled"])

    def collect():
        """Read and check every setting. Returns a dict, or None after showing what's wrong."""
        if not files:
            say("Add at least one stem first", "warn")
            return None
        on_typed()
        try:
            bpm = float(bpm_var.get())
            if not 40 <= bpm <= 240:
                raise ValueError
        except ValueError:
            say("Enter a tempo between 40 and 240 BPM", "warn")
            return None
        drum_map, err = current_map()
        if err:
            say(err, "warn")
            return None
        map_key = label_to_key[map_var.get()]
        settings = load_settings()
        settings["drum_map"] = map_key
        if map_key == "Custom":
            settings["custom_map"] = drum_map
        save_settings(settings)
        return {"bpm": bpm, "grid": GRID_CHOICES[grid_var.get()], "sensitivity": sens_var.get(),
                "parts": [p for p, v in kit_vars.items() if v.get()], "drum_map": drum_map,
                "humanize": human_var.get() / 100.0, "map_key": map_key}

    def run_one(f, c):
        return transcribe(f, type_var.get(), c["bpm"], c["grid"], c["sensitivity"], c["parts"], log,
                          c["drum_map"], c["humanize"])

    def selected_stem():
        sel = [i for i in listbox.curselection() if i < len(files)]
        return files[sel[0]] if sel else files[0]

    # ---- convert
    def work(c):
        ok = 0
        for i, f in enumerate(list(files)):
            updates.put(("status", f"Converting {os.path.basename(f)}  ({i + 1} of {len(files)})", i))
            try:
                result = run_one(f, c)
                if result:
                    out = save_result(result, out_dir["path"], log)
                    ok += 1
                    last_out["dir"] = os.path.dirname(out)
            except Exception as exc:  # keep going with the other stems
                log(f"  Error on {os.path.basename(f)}: {exc}")
        log("\nDone. Drag the .mid files onto a track in your DAW." if ok else "\nNothing was converted.")
        updates.put(("done", ok, len(files)))

    def start():
        c = collect()
        if not c:
            return
        logbox.delete("1.0", "end")
        log(f"Tempo {c['bpm']:g} BPM  |  snap: {grid_var.get()}  |  sensitivity {c['sensitivity']:.2f}"
            f"  |  humanize {int(c['humanize'] * 100)}%  |  drum map: {c['map_key']}")
        set_busy(True)
        open_btn.state(["disabled"])
        say("Working...")
        progress.configure(maximum=len(files), value=0)
        threading.Thread(target=work, args=(c,), daemon=True).start()

    # ---- preview
    def preview_work(f, c, include_original):
        try:
            result = run_one(f, c)
            if not result:
                updates.put(("call", lambda: (set_busy(False), say("That stem is silent", "warn"))))
                return
            render_preview(result, preview_wav, include_original)
            n = len(result["notes"])

            def play_now():
                set_busy(False)
                try:
                    player.play(preview_wav)
                    say(f"Playing {os.path.basename(f)}: {n} notes. Happy with it? Click Convert to save.", "ok")
                except Exception as exc:
                    say(f"Couldn't play audio ({exc}). Preview saved to {preview_wav}", "warn")
            updates.put(("call", play_now))
        except Exception as exc:
            updates.put(("call", lambda: (set_busy(False), say(f"Preview failed: {exc}", "warn"))))

    def preview():
        c = collect()
        if not c:
            return
        player.stop()
        f = selected_stem()
        set_busy(True)
        say(f"Building preview of {os.path.basename(f)}...")
        threading.Thread(target=preview_work, args=(f, c, with_orig.get()), daemon=True).start()

    def stop():
        player.stop()
        say("Stopped")

    # ---- tempo detection
    def detect_work(f):
        try:
            bpm = detect_tempo(f)

            def apply():
                set_busy(False)
                bpm_var.set(f"{bpm:g}")
                tempo_hint.set(f"measured from {os.path.basename(f)}; set your DAW project to {bpm:g} BPM too")
                say(f"Tempo detected: {bpm:g} BPM", "ok")
            updates.put(("call", apply))
        except Exception as exc:
            updates.put(("call", lambda: (set_busy(False), say(f"Couldn't detect tempo: {exc}", "warn"))))

    def detect():
        if not files:
            say("Add a stem first, then Detect", "warn")
            return
        f = selected_stem()
        set_busy(True)
        say(f"Measuring tempo of {os.path.basename(f)}...")
        threading.Thread(target=detect_work, args=(f,), daemon=True).start()

    play_btn.configure(command=preview)
    stop_btn.configure(command=stop)
    detect_btn.configure(command=detect)
    root.protocol("WM_DELETE_WINDOW", lambda: (player.stop(), root.destroy()))

    go.configure(command=start)
    refresh_list()
    poll()
    root.mainloop()


def main():
    if len(sys.argv) == 1:
        run_gui()
        return
    ap = argparse.ArgumentParser(description="Convert audio stems to MIDI.")
    ap.add_argument("stems", nargs="+", help="audio files (wav, mp3, flac...)")
    ap.add_argument("--type", default="auto", choices=["auto"] + STEM_TYPES)
    ap.add_argument("--bpm", type=float, help="song tempo (detected if left out)")
    ap.add_argument("--grid", type=int, default=4,
                    help="snap steps per beat: 4 = 1/16 notes, 2 = 1/8, 3 = triplets, 0 = off")
    ap.add_argument("--sensitivity", type=float, default=0.8, help="0.1 (fewer notes) to 1.5 (more notes)")
    ap.add_argument("--drum-parts", default=",".join(DEFAULT_DRUM_PARTS),
                    help="any of kick,snare,hihat,openhat,toms,crash,ride (default: all but crash and ride)")
    ap.add_argument("--drum-map", default="gm", choices=["gm", "pads"],
                    help="gm = General MIDI (MT Power Drumkit etc.), pads = one pad per drum from note 36")
    ap.add_argument("--map", help="custom notes, e.g. kick=36,snare=40,hihat=42 (overrides --drum-map)")
    ap.add_argument("--humanize", type=int, default=0, help="0 (exact) to 100 (loose) timing and velocity feel")
    ap.add_argument("--out", help="folder for the .mid files")
    a = ap.parse_args()
    drum_map = dict(DRUM_MAPS["General MIDI" if a.drum_map == "gm" else "Pads in order"])
    if a.map:
        for pair in a.map.split(","):
            name, _, num = pair.partition("=")
            name = name.strip()
            if name not in DRUM_NOTES or not num.strip().isdigit() or not 0 <= int(num) <= 127:
                ap.error(f"bad --map entry '{pair}'. Use names like {', '.join(DRUM_NOTES)} with notes 0-127")
            drum_map[name] = int(num)
    for stem in a.stems:
        convert(stem, a.type, a.bpm, a.grid, a.sensitivity, a.drum_parts.split(","), a.out, drum_map=drum_map,
                humanize_amount=max(0, min(100, a.humanize)) / 100)


if __name__ == "__main__":
    main()
