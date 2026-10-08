"""Synthetic test stems with a known right answer.

Every generator is seeded, so the same call always produces the same audio, and returns the
ground truth alongside it (which drums hit when, which notes were played).
"""

import numpy as np
import soundfile as sf

SR = 44100


def _t(seconds):
    return np.arange(int(seconds * SR)) / SR


def _noise(rng, n, bright=False):
    x = rng.normal(0, 1, n + 1)
    return np.diff(x) if bright else x[:n]


def _bandpass(x, lo, hi):
    spec = np.fft.rfft(x)
    freqs = np.fft.rfftfreq(len(x), 1 / SR)
    spec[(freqs < lo) | (freqs > hi)] = 0
    return np.fft.irfft(spec, len(x))


def drum_sound(part, rng):
    """One hit of each drum, built to sit in the bands the detector listens to."""
    if part == "kick":
        t = _t(0.35)
        return np.sin(2 * np.pi * (50 + 80 * np.exp(-t * 30)) * t) * np.exp(-t * 10)
    if part == "snare":
        t = _t(0.2)
        body = 0.3 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)
        crack = _bandpass(_noise(rng, t.size), 1500, 9000) * 2.5 * np.exp(-t * 28)
        return body + crack
    if part == "hihat":
        t = _t(0.05)
        return _bandpass(_noise(rng, t.size), 7000, 16000) * 1.2 * np.exp(-t * 90)
    if part == "openhat":
        t = _t(0.5)
        return _bandpass(_noise(rng, t.size), 7000, 16000) * 1.0 * np.exp(-t * 5)
    if part == "crash":
        t = _t(1.6)
        return _bandpass(_noise(rng, t.size), 4000, 16000) * 2.4 * np.exp(-t * 1.5)
    if part == "ride":
        t = _t(0.7)
        ping = 0.25 * np.sin(2 * np.pi * 4200 * t) * np.exp(-t * 4)
        return ping + _bandpass(_noise(rng, t.size), 3000, 7000) * 0.6 * np.exp(-t * 4)
    pitch = {"tom_hi": 210, "tom_mid": 145, "tom_low": 100}[part]
    t = _t(0.5)
    return np.sin(2 * np.pi * pitch * t) * np.exp(-t * 5)


def drum_loop(hits, bpm=120.0, seed=0, tail=2.0):
    """hits: list of (beat, part). Returns (audio, truth) where truth is [(seconds, part)]."""
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    length = max(b for b, _ in hits) * beat + tail
    y = np.zeros(int(length * SR))
    truth = []
    for b, part in hits:
        start = int(b * beat * SR)
        s = drum_sound(part, rng)
        end = min(y.size, start + s.size)
        y[start:end] += s[: end - start]
        truth.append((b * beat, part))
    return y / np.abs(y).max() * 0.9, truth


def basic_beat(bars=4):
    """Kick on 1 and 3, snare on 2 and 4, closed hats on every eighth."""
    hits = []
    for bar in range(bars):
        for b in range(4):
            beat = bar * 4 + b
            hits.append((beat, "kick" if b % 2 == 0 else "snare"))
        for e in range(8):
            hits.append((bar * 4 + e / 2, "hihat"))
    return hits


def full_kit():
    """Every drum the detector knows, spaced out so each hit can be checked on its own."""
    hits = []
    order = ["kick", "snare", "hihat", "openhat", "tom_hi", "tom_mid", "tom_low", "crash", "ride"]
    for rep in range(2):
        for i, part in enumerate(order):
            hits.append((rep * 40 + i * 4, part))
    return hits


def tone(midi, seconds, harmonics=((1, 1.0), (2, 0.4), (3, 0.2)), decay=1.5):
    t = _t(seconds)
    f = 440.0 * 2 ** ((midi - 69) / 12)
    wave = sum(a * np.sin(2 * np.pi * f * k * t) for k, a in harmonics)
    attack = np.minimum(1.0, t / 0.01)
    release = np.minimum(1.0, (t[-1] - t + 1e-3) / 0.02)
    return wave * attack * release * np.exp(-t * decay)


def note_sequence(notes, bpm=120.0, tail=1.0, **kw):
    """notes: list of (beat, length_in_beats, midi or [midis]). Returns (audio, truth)."""
    beat = 60.0 / bpm
    length = max(b + n for b, n, _ in notes) * beat + tail
    y = np.zeros(int(length * SR))
    truth = []
    for b, n, pitch in notes:
        pitches = pitch if isinstance(pitch, (list, tuple)) else [pitch]
        for p in pitches:
            s = tone(p, n * beat * 0.95, **kw)
            start = int(b * beat * SR)
            y[start : start + s.size] += s
            truth.append((b * beat, p))
    return y / np.abs(y).max() * 0.9, truth


def write(path, y):
    sf.write(str(path), y, SR)
    return str(path)
