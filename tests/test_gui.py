"""Window smoke tests: open the real app, click through it, and check what the user would see.

Needs a display. On Linux CI these run under xvfb (a virtual screen); elsewhere they're
skipped automatically when no display is available.
"""

import os
import tempfile
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

from stemquill.gui import app as app_module  # noqa: E402
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
    assert "Applied" in app.status_card.status.get()


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
    assert app.status_card.status.get() == "Done: 2 of 3 converted"
    assert app.status_card.kind == "warn"  # one stem was skipped
    assert "1 skipped" in app.status_card.detail.get()
    assert not app.status_card.progress.winfo_ismapped()


def test_converting_at_the_default_tempo_warns(app, monkeypatch, stems):
    """The MIDI's beat grid comes from the Tempo box, so an untouched 120 BPM gets a warning."""
    add_stems(app, monkeypatch, [stems["bass"][0]])
    app.converter.start()
    wait_until(app, lambda: not app.busy)
    assert app.status_card.status.get() == "Done: 1 of 1 converted"
    assert app.status_card.kind == "warn"
    assert "Tempo is still the default 120 BPM" in app.status_card.detail.get()

    page(app).bpm_var.set("100")  # typed (or detected): no warning
    app.converter.start()
    wait_until(app, lambda: not app.busy)
    assert app.status_card.kind == "ok"
    assert "Tempo is still" not in app.status_card.detail.get()


def test_time_signature_goes_into_the_midi_and_marks_saved_stems_changed(app, monkeypatch, stems):
    import mido

    add_stems(app, monkeypatch, [stems["bass"][0]])
    p = page(app)
    p.bpm_var.set("120")
    p.time_sig_var.set("6/8")
    app.converter.start()
    wait_until(app, lambda: not app.busy)
    out = os.path.join(app.settings_page.out_dir, "Bass - bass.mid")
    sig = next(m for m in mido.MidiFile(out).tracks[0] if m.type == "time_signature")
    assert (sig.numerator, sig.denominator) == (6, 8)
    assert "6/8" in activity(app)

    p.time_sig_var.set("3/4")
    app.root.update()
    assert p.stems[0].status == "changed · convert again"
    p.time_sig_var.set("6/8")  # back to what was saved
    app.root.update()
    assert p.stems[0].status.startswith("saved")


def test_preview_goes_to_a_private_folder(monkeypatch):
    import stat

    monkeypatch.setattr(journeys, "PREVIEW_WAV", None)
    wav = journeys.preview_wav()
    assert journeys.preview_wav() == wav  # one folder per run
    folder = os.path.dirname(wav)
    assert os.path.isdir(folder) and folder != tempfile.gettempdir()
    if os.name == "posix":
        assert stat.S_IMODE(os.stat(folder).st_mode) == 0o700  # nobody else can plant a file there


def test_open_path_only_opens_folders(app, tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(app_module.subprocess, "Popen", lambda args: opened.append(args))
    not_a_folder = tmp_path / "Bass - bass.mid"
    not_a_folder.write_bytes(b"MThd")
    app.open_path(str(not_a_folder))
    assert opened == []
    assert app.status_card.kind == "warn"


def test_status_card_appears_with_the_first_message(app):
    assert not app.status_card.shown
    app.say("Settings reset to defaults", "ok")
    app.root.update()
    assert app.status_card.shown and app.status_card.winfo_ismapped()
    app.status_card.clear()
    app.root.update()
    assert not app.status_card.winfo_ismapped()


def test_drum_settings_can_always_be_reached(app, monkeypatch, stems):
    """On a small or heavily scaled screen the Convert page scrolls instead of hiding settings.

    Stems are added after the window is open (as a user does), so the page grows afterwards.
    """
    app.root.minsize(1, 1)
    app.root.geometry("1200x460")
    for _ in range(5):
        app.root.update()
    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0]])
    page(app).select(0)  # the drum stem: the tallest settings
    for _ in range(5):
        app.root.update()
    area = app.convert_area
    assert area.needs_scroll() and area.bar.winfo_ismapped()
    assert area.inner.winfo_height() >= area.inner.winfo_reqheight()  # nothing clipped off the bottom

    # the wheel scrolls the page even with the pointer over a control on it
    button = page(app).detect_btn
    x, y = button.winfo_rootx() + 5, button.winfo_rooty() + 5
    button.event_generate("<MouseWheel>", delta=-120, x=5, y=5, rootx=x, rooty=y)
    for _ in range(3):
        app.root.update()
    assert area.canvas.yview()[0] > 0

    area.canvas.yview_moveto(1.0)
    app.root.update()
    card = page(app).card
    bottom = card.winfo_y() + card.winfo_height()
    assert area.canvas.canvasy(area.canvas.winfo_height()) >= bottom - 2  # the drum map can be reached


def test_convert_without_stems_says_what_to_do(app):
    app.converter.start()
    app.root.update()
    assert app.status_card.status.get() == "Add at least one stem first"
    assert app.status_card.kind == "warn"


def test_bad_drum_note_sends_you_to_settings(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0]])
    app.settings_page.note_vars["kick"].set("200")
    app.converter.start()
    app.root.update()
    assert app.page_title.get() == "Settings"
    assert "0 to 127" in app.status_card.status.get()


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


def test_status_card_colours_and_progress(app):
    card = app.status_card
    assert not card.shown  # nothing to report when the app opens, so it's out of the way
    assert not card.winfo_ismapped()
    card.start_progress(4)
    card.say("Converting 4 stems...", "busy")
    app.root.update()
    assert card.progress.winfo_ismapped()
    card.say("Done: 4 of 4 converted", "ok", "Saved in ...")
    app.root.update()
    assert not card.progress.winfo_ismapped()
    assert card.msg_lbl.cget("fg") == card.edge.cget("bg")  # message and edge share the colour


# ---- Play/Stop on the row, the Convert label, "changed since saved", drag and drop


def test_convert_button_says_what_it_will_convert(app, monkeypatch, stems):
    assert app.action.convert_btn.cget("text") == "Convert to MIDI"
    add_stems(app, monkeypatch, [stems["beat"][0]])
    assert app.action.convert_btn.cget("text") == "Convert Drums.wav to MIDI"
    add_stems(app, monkeypatch, [stems["bass"][0], stems["vocal"][0]])
    assert app.action.convert_btn.cget("text") == "Convert 3 stems to MIDI"
    page(app).clear_stems()
    assert app.action.convert_btn.cget("text") == "Convert to MIDI"


def test_play_turns_into_stop_on_that_row(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0]])
    p = page(app)
    rows = p.table.rows
    p._play(1)
    wait_until(app, lambda: not app.busy)
    assert rows[1]["play"].cget("text") == "Stop"
    assert rows[0]["play"].cget("text") == "Play"
    assert p.selected_stem().name == "Bass.wav"
    assert app.status_card.status.get().startswith("Playing Bass.wav")
    p._play(1)  # same row again = Stop
    assert rows[1]["play"].cget("text") == "Play"
    assert app.status_card.status.get() == "Stopped"


def test_row_goes_back_to_play_when_the_preview_ends(app, monkeypatch, stems):
    add_stems(app, monkeypatch, [stems["beat"][0]])
    p = page(app)
    p._play(0)
    wait_until(app, lambda: not app.busy)
    assert p.table.rows[0]["play"].cget("text") == "Stop"
    app.preview._ended(app.preview.token)  # what the timer does when playback finishes
    assert p.table.rows[0]["play"].cget("text") == "Play"


def test_changed_since_saved(app, monkeypatch, stems):
    from stemquill.gui.pages.convert import CHANGED

    add_stems(app, monkeypatch, [stems["beat"][0], stems["bass"][0]])
    p = page(app)
    app.converter.start()
    wait_until(app, lambda: not app.busy)
    drums, bass = p.stems
    saved_text = drums.status
    assert saved_text.startswith("saved") and drums.status_kind == "ok"

    # this stem's own setting changes -> only this row is out of date
    p.select(0)
    p.card.sens_text.set("0.60")
    p.card.apply_typed_sensitivity()
    assert (drums.status, drums.status_kind) == (CHANGED, "warn")
    assert bass.status.startswith("saved")

    # changing it back restores "saved"
    p.card.sens_text.set("0.80")
    p.card.apply_typed_sensitivity()
    assert (drums.status, drums.status_kind) == (saved_text, "ok")

    # drum note numbers only matter for drum stems
    app.settings_page.note_vars["kick"].set("35")
    assert drums.status == CHANGED
    assert bass.status.startswith("saved")
    app.settings_page.note_vars["kick"].set("36")
    assert drums.status == saved_text

    # the song tempo matters for every stem
    p.bpm_var.set("128")
    assert drums.status == CHANGED and bass.status == CHANGED

    # converting again makes them current
    app.converter.start()
    wait_until(app, lambda: not app.busy)
    assert drums.status.startswith("saved") and bass.status.startswith("saved")


def test_audio_files_expands_folders(tmp_path):
    from stemquill.gui.pages.convert import audio_files

    (tmp_path / "Drums.wav").write_bytes(b"")
    (tmp_path / "Bass.MP3").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "sub").mkdir()
    got = audio_files([str(tmp_path), str(tmp_path / "notes.txt")])
    assert [os.path.basename(f) for f in got] == ["Bass.MP3", "Drums.wav"]


def test_drop_files_and_folders(app, stems, tmp_path):
    import shutil

    wait_until(app, lambda: app.dnd_enabled)  # turned on just after the window opens
    folder = tmp_path / "My Stems"  # a space in the name, like real folders
    folder.mkdir()
    shutil.copy(stems["bass"][0], folder / "Bass.wav")
    shutil.copy(stems["vocal"][0], folder / "Vocals.wav")
    data = f"{{{folder}}} {{{stems['beat'][0]}}}"  # how Tk hands over dropped paths
    app._on_drop(SimpleNamespace(data=data, action="copy"))
    p = page(app)
    assert sorted(s.name for s in p.stems) == ["Bass.wav", "Drums.wav", "Vocals.wav"]
    assert app.status_card.status.get() == "Added 3 stems"
    app._on_drop(SimpleNamespace(data=f"{{{folder}}}", action="copy"))  # dropping again adds nothing
    assert len(p.stems) == 3
    assert app.status_card.kind == "warn"


def test_support_link_opens_the_sponsor_page(app, monkeypatch):
    import webbrowser

    from stemquill.config import SUPPORT_URL

    opened = []
    monkeypatch.setattr(webbrowser, "open", opened.append)
    app.sidebar.support.event_generate("<Button-1>")
    app.root.update()
    assert opened == [SUPPORT_URL] == ["https://github.com/sponsors/skynrlabs"]


def test_about_opens_the_open_source_licenses(app):
    from tkinter import ttk

    from stemquill.gui import dialogs

    about = dialogs.show_about(app.root, app.fonts)
    buttons = about.winfo_children()[0].winfo_children()[-1].winfo_children()  # the button row
    next(b for b in buttons if b.cget("text") == "Open-source licenses").invoke()
    app.root.update()
    win = next(w for w in about.winfo_children() if isinstance(w, tk.Toplevel))
    assert win.title() == "Open-source licenses"
    text = win.text.get("1.0", "end")
    assert "librosa" in text and "MIT License" in text
    assert str(win.text.cget("state")) == "disabled"  # read-only
    close = next(b for b in win.winfo_children()[0].winfo_children() if isinstance(b, ttk.Button))
    assert close.cget("text") == "Close"
    close.invoke()
    app.root.update()
    assert not win.winfo_exists() and about.grab_current() is about  # back to the About box
    about.destroy()


def test_window_check_for_the_build(monkeypatch, tmp_path):
    """build.ps1 opens the packaged app with STEMQUILL_CHECK_WINDOW: it must open, report and close."""
    from stemquill.gui import app as app_module

    flag = tmp_path / "window-ok.txt"
    monkeypatch.setenv("STEMQUILL_CHECK_WINDOW", str(flag))
    app_module.run_gui()  # returns once the window has opened and closed itself
    assert flag.read_text(encoding="utf-8") == "window ok"


def test_splash_shows_then_hands_over_to_the_window(monkeypatch, tmp_path):
    """The splash appears before the audio libraries load, then the real window replaces it."""
    from stemquill import splash
    from stemquill.gui import app as app_module

    root = splash.show()
    assert root.splash.winfo_viewable() and root.state() == "withdrawn"
    flag = tmp_path / "window-ok.txt"
    monkeypatch.setenv("STEMQUILL_CHECK_WINDOW", str(flag))
    seen = {}
    real_close = splash.close

    def close(r):
        real_close(r)
        seen["main window shown"] = r.state() == "normal" and r.splash is None

    monkeypatch.setattr(splash, "close", close)
    app_module.run_gui(root)
    assert seen == {"main window shown": True}
    assert flag.read_text(encoding="utf-8") == "window ok"


def test_drag_and_drop_waits_for_the_window(app):
    """Turning on drag and drop can hang on some PCs, so the window is built and shown without it."""
    assert not app.dnd_enabled
    wait_until(app, lambda: app.dnd_enabled)


def test_a_drag_and_drop_hang_is_remembered(monkeypatch, tmp_path):
    """If turning on drag and drop hangs, the next start skips it (and says so) instead of hanging again."""
    import time as _time

    from stemquill.gui import app as app_module

    monkeypatch.setattr(app_module, "DND_WATCH", 0.2)
    monkeypatch.setattr(StemquillApp, "_enable_drag_and_drop", lambda self: _time.sleep(0.5) or True)
    monkeypatch.setattr(app_module, "clear_dnd_hang", lambda: None)  # the "next start" must still see the mark
    root = tk.Tk()
    try:
        a = StemquillApp(root)
        wait_until(a, lambda: a.dnd_enabled)
        assert app_module.dnd_hung_recently()

        b = StemquillApp(tk.Toplevel(root))  # the next start
        calls = []
        monkeypatch.setattr(StemquillApp, "_enable_drag_and_drop", lambda self: calls.append(1) or True)
        wait_until(b, lambda: b.status_card.status.get() == "Drag and drop is off for now")
        assert calls == [] and not b.dnd_enabled
    finally:
        root.destroy()


def test_an_old_drag_and_drop_hang_is_retried_and_cleared(app):
    """A week after a hang, drag and drop is tried again; once it works the mark is removed."""
    from stemquill.gui import app as app_module

    app_module.mark_dnd_hang()
    old = time.time() - 8 * 86400
    os.utime(app_module._dnd_mark_path(), (old, old))
    assert not app_module.dnd_hung_recently()
    app.dnd_enabled = False
    app._start_drag_and_drop()
    assert app.dnd_enabled
    assert not os.path.exists(app_module._dnd_mark_path())
