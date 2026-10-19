"""Pitched stems: single-line (bass, vocal) and polyphonic (guitar, keys, synth) transcription."""

import librosa
import numpy as np
import scipy.ndimage

from ..config import HOP, PITCH_RANGES
from .midi import clean_overlaps, snap
from .onsets import refine_onset


def pitch_frame_length(fmin, sr):
    """Analysis window long enough to hold a bit more than two cycles of the lowest note.

    pYIN can't lock onto a pitch whose cycle doesn't fit twice in the window: with 2048 samples
    at 44.1 kHz, a bass's open low E (41 Hz) and low F/G were missed entirely. Vocals keep 2048.
    """
    frame = 2048
    while frame < 2.2 * sr / fmin:
        frame *= 2
    return frame


def mono_thresholds(sensitivity):
    """What sensitivity (0.1 .. 1.5, default 0.8) changes for single-line stems.

    Higher finds more notes: quieter ones, ones the pitch tracker is less sure of, and shorter
    ones. At the default 0.8 these are the values Stemquill has always used.
    """
    k = 1.6 - sensitivity  # 0.8 at the default
    loud = 0.03 * k  # fraction of the loudest moment a note must reach
    confidence = float(np.clip(0.05 + 0.25 * (0.8 - sensitivity), 0.01, 0.4))
    min_len = float(np.clip(0.07 * k / 0.8, 0.03, 0.15))  # seconds
    return loud, confidence, min_len


def tuning_offset(midi):
    """How far (in semitones, -0.5 .. 0.5) the whole stem sits from standard tuning.

    Singers, AI vocals and detuned instruments are often a steady 20-40 cents sharp or flat. Left
    alone, every held note sits between two pitches and rounding flips between them.
    """
    frac = midi[np.isfinite(midi)] % 1.0
    if frac.size < 20:
        return 0.0
    angle = np.angle(np.mean(np.exp(2j * np.pi * frac)))  # circular mean: 0.9 and 0.1 average to 0.0
    return float(angle / (2 * np.pi))


HYSTERESIS = 0.75  # semitones the pitch must move from the held note before a new note can start
HOLD = 0.05  # seconds it must stay there, so vibrato and scoops don't start new notes


GLIDE_RATE = 8.0  # semitones a second: faster than this, held steadily, is a slide
GLIDE_SPAN = 1.5  # semitones a slide must cover (vibrato swings fast too, but not this far)


GLIDE_GAP = 3  # frames (about 17 ms) of lost pitch a slide can carry on through


def bridge_gaps(midi, longest):
    """Fill gaps of up to `longest` frames in a pitch track by joining the pitches either side."""
    out = midi.copy()
    known = np.flatnonzero(np.isfinite(midi))
    for a, b in zip(known[:-1], known[1:], strict=True):
        if 1 < b - a <= longest + 1:
            out[a + 1 : b] = np.linspace(midi[a], midi[b], b - a + 1)[1:-1]
    return out


def glides(midi, sr):
    """Frames where the pitch slides smoothly from one note to another (a bass slide, a vocal
    glide), so the notes it passes on the way aren't written as short notes of their own."""
    hold = max(1, int(round(HOLD * sr / HOP)))
    midi = bridge_gaps(midi, GLIDE_GAP)  # the tracker often loses a frame or two mid-slide
    slope = np.full(midi.shape, np.nan)
    slope[2:-2] = (midi[4:] - midi[:-4]) / 4  # semitones a frame, over 5 frames
    rate = GLIDE_RATE * HOP / sr
    sign = np.where(np.abs(slope) > rate, np.sign(slope), 0)  # NaN compares False: 0
    out = np.zeros(midi.shape, dtype=bool)
    i = 0
    while i < len(sign):
        if sign[i] == 0:
            i += 1
            continue
        j = i
        while j + 1 < len(sign) and sign[j + 1] == sign[i]:
            j += 1
        lo, hi = max(0, i - 2), min(len(midi) - 1, j + 2)
        if j - i + 1 >= hold and abs(midi[hi] - midi[lo]) >= GLIDE_SPAN:
            out[i : j + 1] = True
        i = j + 1
    return out


def stable_pitch(midi, sr):
    """Turn a wobbling pitch track into steady notes: a new note starts only when the pitch moves
    clearly away from the current one and stays there (it then starts where the move began).
    Through a slide the note slid from carries on; the note it lands on starts on arrival."""
    hold = max(1, int(round(HOLD * sr / HOP)))
    sliding = glides(midi, sr)
    out = np.full(midi.shape, -1, dtype=int)
    cur, pending, since = None, None, 0
    for i, m in enumerate(midi):
        if sliding[i] and cur is not None:
            out[i], pending = cur, None  # mid-slide, even where the tracker lost the pitch
            continue
        if not np.isfinite(m):
            cur, pending = None, None
            continue
        if cur is None:
            cur = int(round(m))
            out[i] = cur
            continue
        if abs(m - cur) <= HYSTERESIS:
            out[i], pending = cur, None
            continue
        cand = int(round(m))
        if cand != pending:
            pending, since = cand, i
        if i - since + 1 >= hold:
            cur, pending = cand, None
            out[since : i + 1] = cand
        else:
            out[i] = cur
    return out


def transcribe_mono(y, sr, bpm, grid, stem_type, sensitivity, log):
    lo, hi = PITCH_RANGES[stem_type]
    fmin = librosa.note_to_hz(lo)
    frame = pitch_frame_length(fmin, sr)
    f0, voiced, prob = librosa.pyin(
        y, fmin=fmin, fmax=librosa.note_to_hz(hi), sr=sr, frame_length=frame, hop_length=HOP
    )
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0]
    n = min(len(f0), len(rms))
    f0, voiced, prob, rms = f0[:n], voiced[:n], prob[:n], rms[:n]

    loud_frac, confidence, min_len = mono_thresholds(sensitivity)
    peak_rms = rms.max() if rms.max() > 0 else 1.0
    loud = rms > peak_rms * loud_frac
    midi = np.where(voiced & loud & (prob > confidence), librosa.hz_to_midi(f0), np.nan)
    offset = tuning_offset(midi)
    if abs(offset) >= 0.1:
        log(f"  tuning: {offset * 100:+.0f} cents from standard pitch, corrected")
    pitch = stable_pitch(midi - offset, sr)
    pitch = scipy.ndimage.median_filter(pitch, size=5)  # smooth out single-frame dropouts

    # new attacks split repeated notes of the same pitch (e.g. G G G on the bass)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    onsets = set(librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=HOP).tolist())

    def new_attack(k):
        """A real re-attack gets louder; a 'new onset' found in a fading note is ignored."""
        if k not in onsets:
            return False
        before = rms[max(0, k - 4) : k].min(initial=np.inf)
        return rms[k : k + 4].max(initial=0.0) > before * 1.25

    notes, i = [], 0
    while i < n:
        if pitch[i] < 0:
            i += 1
            continue
        j = i
        while j + 1 < n and pitch[j + 1] == pitch[i] and not (j + 1 - i > 6 and new_attack(j + 1)):
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


REATTACK_DB = 6.0  # a pitch that jumps this much louder within a few frames was played again
REATTACK_LOOKBACK = 4  # frames (about 46 ms) to look back for the quiet point before the jump


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
    min_frames = int(0.1 / hop_t)
    # A chord strummed again while it still rings never goes quiet, so its notes would merge into
    # one; a sharp rise in a pitch's level (a new attack) starts a new note.
    quietest = D.copy()  # quietest level over the last few frames, for each pitch
    for back in range(1, REATTACK_LOOKBACK):
        quietest[:, back:] = np.minimum(quietest[:, back:], D[:, :-back])
    reattack = np.zeros_like(active)
    reattack[:, 1:] = (D[:, 1:] - quietest[:, :-1]) > REATTACK_DB
    notes = []
    for b in range(n_bins):
        row = active[b]
        idx = np.flatnonzero(np.diff(np.concatenate(([0], row.astype(int), [0]))))
        runs = []
        for s_i, e_i in zip(idx[::2], idx[1::2], strict=True):
            start_i = s_i
            for k in np.flatnonzero(reattack[b, s_i + min_frames : e_i]) + s_i + min_frames:
                if k - start_i >= min_frames:
                    runs.append((start_i, k))
                    start_i = k
            runs.append((start_i, e_i))
        for s_i, e_i in runs:
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
