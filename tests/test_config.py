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
