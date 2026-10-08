"""Write a short synthetic test stem for the build smoke tests.

    python make_test_stem.py out.wav          drum loop (kick, snare, hats)
    python make_test_stem.py out.wav chords   a few sustained chords
"""

import sys

import numpy as np
import soundfile as sf

sr, bpm, bars = 44100, 120, 4
beat = 60 / bpm
y = np.zeros(int(sr * beat * 4 * bars) + sr)
rng = np.random.default_rng(0)


def hit(t, sound):
    i = int(t * sr)
    y[i:i + sound.size] += sound[:max(0, y.size - i)]


tk = np.arange(int(0.3 * sr)) / sr
kick = np.sin(2 * np.pi * (50 + 80 * np.exp(-tk * 30)) * tk) * np.exp(-tk * 10)
ts = np.arange(int(0.2 * sr)) / sr
snare = rng.normal(0, 0.6, ts.size) * np.exp(-ts * 25) + 0.3 * np.sin(2 * np.pi * 190 * ts) * np.exp(-ts * 30)
th = np.arange(int(0.05 * sr)) / sr
hat = np.diff(rng.normal(0, 0.4, th.size + 1)) * np.exp(-th * 80)

for b in range(bars * 4):
    t = b * beat
    hit(t, kick if b % 2 == 0 else snare)
    hit(t, hat)
    hit(t + beat / 2, hat)
if len(sys.argv) > 2 and sys.argv[2] == "chords":
    y[:] = 0
    t = np.arange(int(sr * beat * 4)) / sr
    for i, chord in enumerate([(60, 64, 67), (57, 60, 64), (53, 57, 60), (55, 59, 62)]):
        tone = sum(np.sin(2 * np.pi * 440 * 2 ** ((n - 69) / 12) * t) for n in chord) * np.exp(-t * 0.8)
        hit(i * beat * 4, tone)
sf.write(sys.argv[1] if len(sys.argv) > 1 else "test-drums.wav", y / np.abs(y).max() * 0.9, sr)
