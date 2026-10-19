"""Drum stems: find every hit and decide which drum it is."""

import librosa
import numpy as np

from ..config import DRUM_NOTES, DRUM_PARTS, HOP
from .midi import clean_overlaps, snap
from .onsets import refine_onset


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
    pre = env[max(0, f - 4) : f].min() if f > 0 else 0.0
    peak = env[f : f + 4].max() - pre
    if peak <= 0:
        return 0.0
    later = env[min(len(env) - 1, f + after) : min(len(env), f + after + 3)].mean() - pre
    return float(np.clip(later / peak, 0.0, 1.5))


SPILL = 0.003  # a band that gains less than this share of a hit's biggest jump only caught spill
SNARE_BODY = 0.25  # a snare puts at least this much energy in its band, compared with the hat band


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
    E = S**2
    bands = {"low": (30, 130), "lowmid": (90, 400), "mid": (1500, 5000), "upper": (3000, 7000), "high": (7000, 16000)}
    env = {k: band_energy(E, freqs, *v) for k, v in bands.items()}
    ref = {k: (np.percentile(v, 99.5) or 1.0) for k, v in env.items()}  # "loud" level per band

    def jumps(f):
        """How much energy each band gained at this hit."""
        out = {}
        for band, e in env.items():
            before = e[max(0, f - 4) : f].min() if f > 0 else 0.0
            out[band] = max(0.0, float(e[f : f + 4].max() - before))
        return out

    def rises(f):
        """How big a jump this hit makes in each band, compared with that band's loudest hits
        (about 0..1). A band that only caught a sliver of the hit's energy (spill from a hi-hat
        into the kick's band, say) counts as no jump: otherwise a hats-only stem, whose low band
        holds nothing but spill, would read every hat as a kick or snare as well."""
        j = jumps(f)
        top = max(j.values()) or 1.0
        r = {b: (float(np.sqrt(v / ref[b])) if v >= SPILL * top else 0.0) for b, v in j.items()}
        return r, j

    # timing: spectral flux across all bands
    flux = np.maximum.reduce([band_flux(S, freqs, *bands[k]) for k in ("low", "lowmid", "mid", "high")])
    delta = max(0.02, 0.12 * (1.6 - sensitivity))  # sensitivity 0.1 .. 1.5
    frames = librosa.util.peak_pick(
        flux, pre_max=3, post_max=3, pre_avg=10, post_avg=10, delta=delta, wait=max(1, int(0.05 * sr / HOP))
    )
    k = 1.6 - sensitivity
    thr, snare_thr, tom_thr = 0.25 * k, 0.35 * k, 0.3 * k
    fps = sr / HOP
    f150_full, f450_full = int(0.15 * fps), int(0.45 * fps)
    tom_bins = (freqs >= 60) & (freqs < 400)

    length = 60.0 / bpm / 4  # sixteenth note
    notes, counts = [], {p: 0 for p in DRUM_NOTES}
    following = list(frames[1:]) + [None]
    for f, nxt in zip(frames, following, strict=True):
        # How long a hit rings is read before the next hit starts, so a fast run of closed hats
        # doesn't look like one long ringing cymbal.
        gap = (nxt - f - 4) if nxt is not None else f450_full  # ring_ratio reads 3 frames from here
        f150, f450 = max(3, min(f150_full, gap)), max(3, min(f450_full, gap))
        r, j = rises(f)
        lo, lm, m, up, h = (r[b] for b in ("low", "lowmid", "mid", "upper", "high"))
        mid_ring = ring_ratio(env["mid"], f, f150)
        high_ring = ring_ratio(env["high"], f, f150)
        high_long = ring_ratio(env["high"], f, f450)
        found = []

        # Snare: strong mid crack that dies away fast (rides and crashes keep ringing).
        # A hi-hat's fizz reaches down into the snare's band too, but it is mostly far higher.
        is_snare = m > snare_thr and mid_ring < 0.2 and j["mid"] >= SNARE_BODY * j["high"]
        # Crash: big, bright and still ringing half a second later.
        is_crash = h > thr * 1.5 and high_long > 0.35

        # Kick or tom: both thump; toms sit higher in pitch and ring on.
        if lo > thr or lm > tom_thr:
            spec = S[tom_bins, f : f + int(0.1 * fps)].mean(axis=1)
            pitch = freqs[tom_bins][int(np.argmax(spec))]
            tom_ring = ring_ratio(env["lowmid"], f, f150)
            if pitch >= 95 and tom_ring > 0.1 and lm > tom_thr and not is_snare:
                tom = "tom_hi" if pitch >= 170 else "tom_mid" if pitch >= 120 else "tom_low"
                found.append((tom, lm))
            elif lo > thr:
                found.append(("kick", lo))
        if is_snare:
            found.append(("snare", m))
        if is_crash:
            found.append(("crash", h))
        elif not is_snare and (h > thr or up > thr):
            if high_ring > 0.3 or ring_ratio(env["upper"], f, f150) > 0.3:
                # rides "ping" lower than hats; hats are mostly very high fizz
                found.append(("ride" if j["upper"] > j["high"] * 0.5 else "openhat", max(h, up)))
            elif h > thr:
                found.append(("hihat", h))

        t_frame = librosa.frames_to_time(f, sr=sr, hop_length=HOP)
        t = snap(max(0.0, refine_onset(y, sr, t_frame, before=0.01, after=0.04) - pad / sr), bpm, grid)
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
