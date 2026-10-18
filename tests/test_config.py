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
