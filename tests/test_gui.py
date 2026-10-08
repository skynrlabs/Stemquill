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
    a.output_page.out_dir = str(tmp_path / "out")
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
    return app.convert_page.activity.as_text()


def test_opens_on_convert_without_a_menu_bar(app):
    assert app.page_title.get() == "Convert"
    assert app.root.cget("menu") == ""
    assert "show up here" in activity(app)


@pytest.mark.parametrize("key, _label, title, _sub", PAGES)
def test_every_page_opens(app, key, _label, title, _sub):
    app.show_page(key)
    app.root.update()
    assert app.page_title.get() == title
    assert app.sidebar.current == key


def test_adding_stems(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0]])
    assert app.convert_page.listbox.size() == 2
    assert app.convert_page.listbox.curselection() == (0,)
    assert app.action.target.get().startswith("Plays: Drums.wav")
    assert app.sidebar.items["convert"][1].cget("text") == "Convert  (2)"


def test_detect_preview_and_convert(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0], stems["silent"][0]])

    app.tempo.start()
    wait_until(app, lambda: not app.busy)
    assert float(app.convert_page.bpm_var.get()) == pytest.approx(120, abs=0.2)
    assert "Detect tempo" in activity(app)

    app.preview.start()
    wait_until(app, lambda: not app.busy)
    assert os.path.exists(journeys.PREVIEW_WAV)
    assert "Preview Drums.wav" in activity(app)
    assert "Kick 8" in activity(app)

    app.converter.start()
    wait_until(app, lambda: not app.busy)
    out = app.output_page.out_dir
    assert sorted(os.listdir(out)) == ["Bass - bass.mid", "Drums - drums.mid"]
    text = activity(app)
    assert "Convert 3 stems" in text
    assert "Drums - drums.mid" in text
    assert "silent, skipped" in text
    assert "Done | 2 of 3 saved" in text
    assert app.action.status.get() == "Done: 2 of 3 converted"


def test_convert_without_stems_says_what_to_do(app):
    app.converter.start()
    app.root.update()
    assert app.action.status.get() == "Add at least one stem first"


def test_bad_drum_note_sends_you_to_the_drum_kit_page(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0]])
    app.drum_page.note_vars["kick"].set("200")
    app.converter.start()
    app.root.update()
    assert app.page_title.get() == "Drum Kit"
    assert "0 to 127" in app.action.status.get()


def test_reset_to_defaults(app):
    app.convert_page.human_var.set(60)
    app.drum_page.kit_vars["ride"].set(True)
    app.drum_page.note_vars["kick"].set("35")
    app.reset_settings()
    assert app.convert_page.human_var.get() == 0
    assert app.drum_page.kit_vars["ride"].get() is False
    assert app.drum_page.note_vars["kick"].get() == "36"
    assert app.drum_page.map_key() == "General MIDI"


def test_clear_activity(app):
    app.convert_page.activity.action("Something")
    app.convert_page.activity.clear()
    assert "show up here" in activity(app)


def test_activity_table_newest_first_older_folded(app):
    feed = app.convert_page.activity
    first = feed.action("Detect tempo")
    feed.stem("Drums.wav", "120 BPM")
    second = feed.action("Convert 1 stem")
    tree = feed.tree
    assert tree.get_children()[0] == second
    assert tree.item(second, "open") in (True, 1)
    assert tree.item(first, "open") in (False, 0)


def test_activity_table_scrolls(app):
    feed = app.convert_page.activity
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
    opened = []
    monkeypatch.setattr(app.convert_page.activity, "on_open", opened.append)
    feed = app.convert_page.activity
    feed.action("Convert 1 stem")
    row = feed.stem("Drums.wav", "drums · 8 notes", "Kick 8", saved="/music/out/Drums - drums.mid")
    app.root.update()
    x, y, _, _ = feed.tree.bbox(row)
    feed._on_double_click(SimpleNamespace(x=x + 5, y=y + 5))  # Tk can't synthesise a double-click
    assert opened == ["/music/out"]
