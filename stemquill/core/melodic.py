"""Pitched stems: single-line (bass, vocal) and polyphonic (guitar, keys, synth) transcription."""

import librosa
import numpy as np
import scipy.ndimage

from ..config import HOP, PITCH_RANGES
from .midi import clean_overlaps, snap
from .onsets import refine_onset


def transcribe_mono(y, sr, bpm, grid, stem_type, sensitivity, log):
    lo, hi = PITCH_RANGES[stem_type]
    f0, voiced, prob = librosa.pyin(
        y, fmin=librosa.note_to_hz(lo), fmax=librosa.note_to_hz(hi), sr=sr, frame_length=2048, hop_length=HOP
    )
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
        start = refine_onset(y, sr, librosa.frames_to_time(i, sr=sr, hop_length=HOP), before=0.05, after=0.015)
        end = librosa.frames_to_time(j + 1, sr=sr, hop_length=HOP)
        if end - start >= min_len:
            vel = int(np.clip(40 + 87 * np.sqrt(rms[i : j + 1].max() / peak_rms), 1, 127))
            s, e = snap(start, bpm, grid), snap(end, bpm, grid)
            if e <= s:
                e = s + (60.0 / bpm / (grid or 4))
            notes.append((s, e, int(pitch[i]), vel))
        i = j + 1
    log(f"  {len(notes)} notes")
    return clean_overlaps(notes)


def transcribe_poly_basic_pitch(path, bpm, grid, stem_type, sensitivity, log):
    from basic_pitch.inference import predict  # optional, higher quality

    lo, hi = PITCH_RANGES[stem_type]
    _, _, events = predict(
        path,
        onset_threshold=float(np.clip(0.5 * (1.6 - sensitivity), 0.2, 0.8)),
        frame_threshold=0.3,
        minimum_note_length=80,
        minimum_frequency=librosa.note_to_hz(lo),
        maximum_frequency=librosa.note_to_hz(hi),
    )
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
    C = np.abs(librosa.cqt(y, sr=sr, hop_length=512, fmin=librosa.midi_to_hz(lo_m), n_bins=n_bins, bins_per_octave=12))
    D = librosa.amplitude_to_db(C, ref=np.max)
    thresh = -30 - 10 * sensitivity  # dB below the loudest moment
    active = thresh < D

    # keep local peaks across pitch, and drop likely overtones of a louder lower note
    peaks = np.zeros_like(active)
    peaks[1:-1] = (D[1:-1] >= D[:-2]) & (D[1:-1] >= D[2:])
    active &= peaks
    for k, ratio in ((12, 0.0), (19, 3.0), (24, 6.0)):
        lower = np.zeros_like(D) - 200
        lower[k:] = D[:-k]
        lower_active = np.zeros_like(active)
        lower_active[k:] = active[:-k]
        active &= ~(lower_active & (lower + ratio > D))
    active = scipy.ndimage.binary_closing(active, structure=np.ones((1, 3)))

    hop_t = 512 / sr
    notes = []
    for b in range(n_bins):
        row = active[b]
        idx = np.flatnonzero(np.diff(np.concatenate(([0], row.astype(int), [0]))))
        for s_i, e_i in zip(idx[::2], idx[1::2], strict=True):
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
