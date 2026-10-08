"""Preview rendering writes a playable WAV."""

import soundfile as sf

from stemquill.core import render_preview


def test_preview_wav(stems, run, tmp_path):
    result = run(stems["beat"][0], "drums")
    wav = render_preview(result, str(tmp_path / "p.wav"))
    y, sr = sf.read(wav)
    assert sr == 22050
    assert len(y) / sr > 7  # the loop is 8 seconds
    assert abs(y).max() > 0.1


def test_preview_with_original_mixed_in(stems, run, tmp_path):
    result = run(stems["bass"][0], "bass")
    wav = render_preview(result, str(tmp_path / "p.wav"), include_original=True)
    y, _ = sf.read(wav)
    assert abs(y).max() <= 1.0
