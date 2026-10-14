"""The open-source licenses file the Windows app ships, and what the About dialog shows."""

import sys

from stemquill import licenses


def test_lists_every_library_the_app_needs():
    names = {d.metadata["Name"].lower() for d in licenses.libraries()}
    assert {"numpy", "scipy", "librosa", "soundfile", "mido", "tkinterdnd2", "soxr"} <= names
    assert "stemquill" not in names and "pip" not in names
    assert "scikit-learn" not in names  # left out of the Windows build
    assert "pytest" not in names and "ruff" not in names  # dev tools aren't shipped


def test_full_file_has_every_license_text(tmp_path):
    out = tmp_path / licenses.FILE_NAME
    licenses.main(["--out", str(out)])
    text = out.read_text(encoding="utf-8")
    assert text.startswith("Stemquill - open-source licenses")
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in text  # libsndfile and libsoxr
    assert "ISC" in text and "NumPy Developers" in text
    for name in ("librosa", "numpy", "mido", "soundfile"):
        assert f"\n  {name} " in text  # in the list at the top
    assert licenses.ADDON_TITLE not in text  # no add-on folder given


def test_addon_libraries_are_listed_without_repeats(tmp_path):
    def fake_dist(name, version, license_text):
        info = tmp_path / f"{name}-{version}.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n")
        (info / "LICENSE").write_text(license_text)
        (info / "RECORD").write_text(f"{info.name}/METADATA,,\n{info.name}/LICENSE,,\n")

    fake_dist("basic_pitch", "0.4.0", "Apache License\nVersion 2.0, January 2004")
    fake_dist("numpy", "1.0", "already in the app")
    text = licenses.full_text(addon=str(tmp_path))
    addon = text.split(licenses.ADDON_TITLE)[1].split("=" * 100)[0]
    assert "basic_pitch 0.4.0" in addon and "Apache-2.0" in addon  # recognised from the license text
    assert "numpy" not in addon  # the app's own copy is already listed
    assert "Version 2.0, January 2004" in text


def test_dialog_lists_libraries_when_installed_with_pip():
    text = licenses.dialog_text()
    assert "MIT License" in text and "librosa" in text
    assert "GNU LESSER GENERAL PUBLIC LICENSE" not in text  # no full texts: pip installed those itself


def test_packaged_app_shows_the_shipped_file(tmp_path, monkeypatch):
    (tmp_path / licenses.FILE_NAME).write_text("the shipped file", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Stemquill.exe"))
    assert licenses.dialog_text() == "the shipped file"
