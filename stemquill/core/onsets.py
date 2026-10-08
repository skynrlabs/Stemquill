"""Place a note exactly where its sound starts.

The detectors work on overlapping analysis windows, so the moment they report is a few
milliseconds off: drum hits come out early (the window "hears" a hit before it lands) and
pitched notes come out late (pitch needs a moment of sound before it can be measured).
refine_onset looks at the waveform around a reported time and finds the real attack.
"""

import numpy as np
import scipy.ndimage


def refine_onset(y, sr, t, before=0.03, after=0.05, rise=0.2):
    """Return the time (seconds) where the sound near `t` actually starts rising.

    Looks from `before` seconds earlier to `after` seconds later, finds the loudest point,
    then walks back to where the level was still close to the quiet level before it.
    Falls back to `t` when there's no clear attack (e.g. legato notes).
    """
    a = max(0, int((t - before) * sr))
    b = min(len(y), int((t + after) * sr))
    if b - a < 64:
        return t
    env = scipy.ndimage.maximum_filter1d(np.abs(y[a:b]), size=max(1, int(0.002 * sr)))
    peak = int(np.argmax(env))
    floor = float(env[: peak + 1].min())
    top = float(env[peak])
    if top <= 0 or top < floor * 2:  # no real attack in this window
        return t
    below = np.flatnonzero(env[: peak + 1] <= floor + rise * (top - floor))
    if below.size == 0:
        return t
    return (a + int(below[-1])) / sr
