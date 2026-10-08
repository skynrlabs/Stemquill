"""The command line: python -m stemquill ..."""

import subprocess
import sys

from stemquill import __version__


def cli(*args, env=None):
    return subprocess.run([sys.executable, "-m", "stemquill", *args], capture_output=True, text=True, env=env)


def test_version():
    r = cli("--version")
    assert r.returncode == 0
    assert __version__ in r.stdout


def test_converts_several_stems(stems, tmp_path):
    out = tmp_path / "out"
    r = cli(stems["beat"][0], stems["bass"][0], "--bpm", "120", "--grid", "0", "--out", str(out))
    assert r.returncode == 0, r.stderr
    assert sorted(p.name for p in out.iterdir()) == ["Bass - bass.mid", "Drums - drums.mid"]


def test_bad_custom_map_is_rejected(stems, tmp_path):
    r = cli(stems["beat"][0], "--map", "cowbell=56", "--out", str(tmp_path))
    assert r.returncode == 2
    assert "bad --map entry" in r.stderr


def test_log_file(stems, tmp_path):
    import os

    log = tmp_path / "log.txt"
    env = {**os.environ, "STEMQUILL_LOG": str(log)}
    r = cli(stems["beat"][0], "--bpm", "120", "--out", str(tmp_path), env=env)
    assert r.returncode == 0, r.stderr
    text = log.read_text()
    assert "kick: 8 hits" in text
    assert "saved:" in text
