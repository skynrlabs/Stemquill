"""Window smoke tests: open the real app, click through it, and check what the user would see.

Needs a display. On Linux CI these run under xvfb (a virtual screen); elsewhere they're
skipped automatically when no display is available.
"""

import os
import time
from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

pytestmark = pytest.mark.gui


def _display_available():
    try:
        root = tk.Tk()
        root.destroy()
        return True
    except tk.TclError:
        return False


if not _display_available():
    pytest.skip("no display available", allow_module_level=True)

from stemquill.gui import journeys  # noqa: E402
from stemquill.gui.app import StemquillApp  # noqa: E402
from stemquill.gui.pages import PAGES  # noqa: E402


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr(journeys.Player, "play", lambda self, wav: None)  # no speakers on CI
    monkeypatch.setattr(journeys, "PREVIEW_WAV", str(tmp_path / "preview.wav"))
    root = tk.Tk()
    a = StemquillApp(root)
    a.settings_page.out_dir = str(tmp_path / "out")
    root.update()
    yield a
    root.destroy()


def add_stems(app, monkeypatch, paths):
    from tkinter import filedialog

    monkeypatch.setattr(filedialog, "askopenfilenames", lambda **kw: list(paths))
    app.convert_page.add_files()
    app.root.update()


def wait_until(app, condition, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        app.root.update()
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError("timed out waiting for the window")


def activity(app):
    return app.activity.as_text()


def page(app):
    return app.convert_page


# ---- opening and navigating


def test_opens_on_convert_without_a_menu_bar(app):
    assert app.page_title.get() == "Convert"
    assert app.root.cget("menu") == ""
    assert "show up here" in activity(app)
    assert page(app).card.title.get() == "Stem settings"
    assert page(app).table.empty.winfo_ismapped()


@pytest.mark.parametrize("key, _label, title, _sub", PAGES)
def test_every_page_opens(app, key, _label, title, _sub):
    app.show_page(key)
    app.root.update()
    assert app.page_title.get() == title
    assert app.sidebar.current == key


# ---- the stems table


def test_adding_stems_makes_a_row_each_with_its_type(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0], stems["chords"][0]])
    p = page(app)
    assert [s.name for s in p.stems] == ["Drums.wav", "Bass.wav", "Other.wav"]
    assert [s.stem_type for s in p.stems] == ["drums", "bass", "melodic"]
    assert len(p.table.rows) == 3
    assert p.selected == 0
    assert p.card.title.get() == "Drums.wav settings"
    assert app.sidebar.items["convert"][1].cget("text") == "Convert  (3)"
    assert not p.table.empty.winfo_ismapped()


def test_adding_the_same_file_twice_is_ignored(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0]])
    add_stems(app, monkeypatch, [stems["beat"][0]])
    assert len(page(app).stems) == 1


def test_selecting_a_stem_shows_its_own_settings(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0]])
    p = page(app)
    p.select(1)
    app.root.update()
    assert p.card.title.get() == "Bass.wav settings"
    assert not p.card.drums.winfo_ismapped(), "drum options only show for drum stems"
    p.select(0)
    app.root.update()
    assert p.card.drums.winfo_ismapped()


def test_each_stem_keeps_its_own_settings(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0]])
    p = page(app)
    p.select(0)
    p.card.sens_text.set("0.55")
    p.card.apply_typed_sensitivity()
    p.card.human_var.set(40)
    p.card._on_humanize(40)
    p.card.kit_vars["ride"].set(True)
    p.select(1)
    assert p.card.sens_var.get() == pytest.approx(0.8)
    assert p.card.human_var.get() == 0
    drums, bass = p.stems
    assert (drums.sensitivity, drums.humanize) == (0.55, 40)
    assert "ride" in drums.parts
    assert (bass.sensitivity, bass.humanize) == (0.8, 0)
    p.select(0)
    assert p.card.sens_text.get() == "0.55"


def test_apply_to_all(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0], stems["vocal"][0]])
    p = page(app)
    p.card.sens_text.set("1.10")
    p.card.apply_typed_sensitivity()
    p.apply_to_all()
    assert [s.sensitivity for s in p.stems] == [1.1, 1.1, 1.1]
    assert "Applied" in app.action.status.get()


def test_changing_a_stems_type(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["chords"][0]])
    p = page(app)
    p.set_type(0, "drums")
    app.root.update()
    assert p.stems[0].stem_type == "drums"
    assert p.card.drums.winfo_ismapped()


def test_remove_keeps_a_sensible_selection(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0], stems["chords"][0]])
    p = page(app)
    p.select(2)
    p.remove(0)
    assert [s.name for s in p.stems] == ["Bass.wav", "Other.wav"]
    assert p.selected_stem().name == "Other.wav"
    p.clear_stems()
    assert p.selected_stem() is None
    assert p.card.title.get() == "Stem settings"


# ---- the journeys


def test_detect_preview_and_convert(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0], stems["silent"][0]])
    p = page(app)

    app.tempo.start()
    wait_until(app, lambda: not app.busy)
    assert float(p.bpm_var.get()) == pytest.approx(120, abs=0.2)
    assert p.tempo_hint.get() == "measured from Drums.wav"
    assert "Detect tempo" in activity(app)

    p._play(0)  # the Play button on the drum row
    wait_until(app, lambda: not app.busy)
    assert os.path.exists(journeys.PREVIEW_WAV)
    assert "Preview Drums.wav" in activity(app)
    assert "Kick 8" in activity(app)

    p.stems[1].sensitivity = 1.2  # the bass gets its own setting
    app.converter.start()
    wait_until(app, lambda: not app.busy)
    out = app.settings_page.out_dir
    assert sorted(os.listdir(out)) == ["Bass - bass.mid", "Drums - drums.mid"]
    drums, bass, silent = p.stems
    assert drums.status.startswith("saved") and drums.status_kind == "ok"
    assert drums.saved.endswith("Drums - drums.mid")
    assert bass.status.startswith("saved")
    assert silent.status == "silent, skipped" and silent.status_kind == "warn"
    text = activity(app)
    assert "Convert 3 stems" in text
    assert "sensitivity 1.20" in text  # per-stem setting recorded for the bass
    assert "Done | 2 of 3 saved" in text
    assert app.action.status.get() == "Done: 2 of 3 converted"


def test_convert_without_stems_says_what_to_do(app):
    app.converter.start()
    app.root.update()
    assert app.action.status.get() == "Add at least one stem first"


def test_bad_drum_note_sends_you_to_settings(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0]])
    app.settings_page.note_vars["kick"].set("200")
    app.converter.start()
    app.root.update()
    assert app.page_title.get() == "Settings"
    assert "0 to 127" in app.action.status.get()


def test_drum_map_is_shared_between_card_and_settings(app, monkeypatch, stems):
    from stemquill.config import DRUM_MAP_LABELS

    add_stems(app, monkeypatch, [stems["beat"][0]])
    app.settings_page.map_var.set(DRUM_MAP_LABELS["Pads in order"])
    app.settings_page.apply_map("Pads in order")
    assert page(app).card.map_box.get() == DRUM_MAP_LABELS["Pads in order"]
    assert app.settings_page.note_vars["snare"].get() == "37"


def test_reset_everything(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0]])
    p = page(app)
    p.stems[0].humanize = 60
    p.stems[0].parts.append("ride")
    p.bpm_var.set("99")
    app.settings_page.note_vars["kick"].set("35")
    app.reset_settings()
    assert p.stems[0].humanize == 0
    assert "ride" not in p.stems[0].parts
    assert p.bpm_var.get() == "120"
    assert app.settings_page.note_vars["kick"].get() == "36"
    assert app.settings_page.map_key() == "General MIDI"


def test_busy_disables_the_controls(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0]])
    app.set_busy(True)
    row = page(app).table.rows[0]
    assert row["play"].instate(["disabled"])
    assert page(app).detect_btn.instate(["disabled"])
    assert app.action.convert_btn.instate(["disabled"])
    app.set_busy(False)
    assert row["play"].instate(["!disabled"])


# ---- the History table


def test_activity_table_newest_first_older_folded(app):
    feed = app.activity
    first = feed.action("Detect tempo")
    feed.stem("Drums.wav", "120 BPM")
    second = feed.action("Convert 1 stem")
    tree = feed.tree
    assert tree.get_children()[0] == second
    assert tree.item(second, "open") in (True, 1)
    assert tree.item(first, "open") in (False, 0)


def test_activity_table_scrolls(app):
    app.show_page("history")
    feed = app.activity
    for i in range(30):
        feed.action(f"Convert {i}")
        feed.stem(f"Drums {i}.wav", "drums · 8 notes", "Kick 8", saved=f"/tmp/out/Drums {i} - drums.mid")
    for item in feed.tree.get_children():
        feed.tree.item(item, open=True)
    app.root.update()
    feed.tree.yview_moveto(0)
    app.root.update()
    top = feed.tree.yview()
    feed.tree.yview_scroll(5, "units")
    app.root.update()
    assert feed.tree.yview()[0] > top[0]


def test_double_click_saved_file_opens_its_folder(app, monkeypatch):
    app.show_page("history")
    opened = []
    monkeypatch.setattr(app.activity, "on_open", opened.append)
    feed = app.activity
    feed.action("Convert 1 stem")
    row = feed.stem("Drums.wav", "drums · 8 notes", "Kick 8", saved="/music/out/Drums - drums.mid")
    app.root.update()
    x, y, _, _ = feed.tree.bbox(row)
    feed._on_double_click(SimpleNamespace(x=x + 5, y=y + 5))  # Tk can't synthesise a double-click
    assert opened == ["/music/out"]


def test_empty_message_is_not_a_table_row(app):
    app.show_page("history")
    app.root.update()
    feed = app.activity
    assert feed.tree.get_children() == ()
    assert feed.empty_note.winfo_ismapped()
    feed.action("Detect tempo")
    app.root.update()
    assert not feed.empty_note.winfo_ismapped()
    feed.clear()
    app.root.update()
    assert feed.empty_note.winfo_ismapped()
