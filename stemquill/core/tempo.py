"""Tempo detection."""

import librosa
import numpy as np

from ..config import log_default


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
