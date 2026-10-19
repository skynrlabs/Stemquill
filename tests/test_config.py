"""Small helpers in config."""

import pytest

import stemquill.config as config


@pytest.mark.parametrize("note, name", [(36, "C1"), (38, "D1"), (42, "F#1"), (60, "C3"), (127, "G8")])
def test_note_names(note, name):
    assert config.note_name(note) == name


def test_settings_round_trip():
    config.save_settings({"drum_map": "Custom", "custom_map": {"kick": 35}})
    assert config.load_settings()["custom_map"] == {"kick": 35}


def test_missing_settings_file_is_fine(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SETTINGS_PATH", str(tmp_path / "nope" / "settings.json"))
    assert config.load_settings() == {}


def test_drum_maps_cover_every_drum():
    for name, notes in config.DRUM_MAPS.items():
        assert set(notes) == set(config.DRUM_NOTES), name
        assert len(set(notes.values())) == len(notes), f"{name}: two drums share a note"


@pytest.mark.parametrize("text, sig", [("4/4", (4, 4)), (" 7/8 ", (7, 8)), ("5/16", (5, 16)), ("12/8", (12, 8))])
def test_parse_time_signature(text, sig):
    assert config.parse_time_signature(text) == sig


@pytest.mark.parametrize("text", ["7/9", "0/4", "4", "four/4", "4/0"])
def test_parse_time_signature_rejects_nonsense(text):
    with pytest.raises(ValueError):
        config.parse_time_signature(text)


def test_offered_time_signatures_are_valid():
    for label, sig in config.TIME_SIGNATURES.items():
        assert config.parse_time_signature(label) == sig
    assert config.DEFAULT_TIME_SIGNATURE == "4/4"


def test_cache_dir_is_private_not_the_shared_temp_folder():
    import tempfile

    assert not config.cache_dir().startswith(tempfile.gettempdir())


def test_numba_cache_goes_to_the_private_cache(monkeypatch):
    from stemquill import __main__ as entry

    monkeypatch.delenv("NUMBA_CACHE_DIR", raising=False)
    entry._prepare_environment()
    import os

    assert os.environ["NUMBA_CACHE_DIR"].startswith(config.cache_dir())


def test_a_startup_crash_is_logged(monkeypatch, tmp_path):
    """The installed app has no console: a crash while starting must leave a log behind."""
    import pytest

    import stemquill.config as config
    from stemquill import __main__ as entry

    monkeypatch.setattr(config, "SETTINGS_PATH", str(tmp_path / "Stemquill" / "settings.json"))
    monkeypatch.setattr(entry.sys, "argv", ["stemquill", "x.wav"])  # command line: no error window

    def broken():
        raise RuntimeError("missing DLL")

    monkeypatch.setattr(entry, "_check_libraries", broken)
    with pytest.raises(RuntimeError):
        entry.main()
    log = (tmp_path / "Stemquill" / "crash.log").read_text(encoding="utf-8")
    assert "missing DLL" in log and "Stemquill" in log and "Traceback" in log
