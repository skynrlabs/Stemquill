"""Humanize: small timing and velocity changes so parts feel played."""

import numpy as np


def humanize(notes, bpm, amount, is_drums, seed=7):
    """Nudge timing and velocity a little so the part feels played rather than programmed.
    amount: 0 (off) .. 1 (strong). Same seed = same result, so a preview matches the saved file."""
    if amount <= 0:
        return notes
    rng = np.random.default_rng(seed)
    max_shift = 0.018 * amount  # up to ~18 ms early/late
    vel_spread = 14 * amount  # velocity wobble
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
