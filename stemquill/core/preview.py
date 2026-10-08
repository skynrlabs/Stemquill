"""Preview: render notes with simple built-in sounds and play them."""

import sys

import librosa
import numpy as np

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
        length, decay, gain = {
            "hihat": (0.08, 70, 0.35),
            "openhat": (0.4, 9, 0.3),
            "crash": (1.4, 2.5, 0.4),
            "ride": (0.6, 6, 0.25),
        }[part]
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
    harmonics = (
        [(1, 1.0), (2, 0.5), (3, 0.25)]
        if stem_type == "bass"
        else [(1, 1.0), (2, 0.15)]
        if stem_type == "vocal"
        else [(1, 1.0), (2, 0.35), (3, 0.15), (4, 0.08)]
    )
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
    length = max((e for _, e, _, _ in notes), default=0) + 2.0
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
        mix[i:j] += sound[: j - i]
    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.8
    if original is not None:
        o = original / (np.max(np.abs(original)) or 1.0) * original_gain
        mix[: o.size] = mix[: o.size] * 0.8 + o
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

            for cmd in (
                ["afplay"],
                ["aplay", "-q"],
                ["paplay"],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"],
            ):
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
