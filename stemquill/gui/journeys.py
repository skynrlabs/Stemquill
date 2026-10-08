"""The three things a user does: convert stems, preview a stem, and detect the tempo.

Each journey does its slow work on a background thread and reports back through
app.post(), because Tk widgets may only be touched from the main thread. Results go to
the Activity feed as short, readable entries (see activity.py).
"""

import os
import tempfile
import threading

from ..core import Player, detect_tempo, render_preview, save_result, transcribe
from .activity import describe, short_path

PREVIEW_WAV = os.path.join(tempfile.gettempdir(), "stemquill_preview.wav")


class EngineNotes:
    """Collects the engine's step-by-step output and keeps only what the user should see."""

    def __init__(self):
        self.lines = []

    def __call__(self, msg):
        self.lines.append(msg.strip())

    def warnings(self):
        return [m for m in self.lines if "failed" in m]


def run_transcribe(path, c, notes):
    return transcribe(
        path, c["stem_type"], c["bpm"], c["grid"], c["sensitivity"], c["parts"], notes, c["drum_map"], c["humanize"]
    )


def settings_line(c):
    snap = "no snap" if not c["grid"] else f"snap {c['grid_label']}"
    human = f"humanize {int(c['humanize'] * 100)}%" if c["humanize"] else "no humanize"
    return f"{c['bpm']:g} BPM · {snap} · sensitivity {c['sensitivity']:.2f} · {human} · {c['map_key']} drum map"


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


class ConvertJourney:
    """Convert every stem in the list and save the .mid files."""

    def __init__(self, app):
        self.app = app
        self.last_out_dir = None

    def start(self):
        app = self.app
        if app.busy:
            return
        c = app.collect()
        if not c:
            return
        files = list(app.convert_page.files)
        app.convert_page.activity.action(f"Convert {plural(len(files), 'stem')}", settings_line(c))
        app.set_busy(True)
        app.action.open_btn.state(["disabled"])
        app.say("Working...")
        app.action.progress.configure(maximum=len(files), value=0)
        threading.Thread(target=self._work, args=(files, c, app.output_page.out_dir), daemon=True).start()

    def _work(self, files, c, out_dir):
        app = self.app
        feed = app.convert_page.activity
        ok = 0
        for i, f in enumerate(files):
            name = os.path.basename(f)
            msg = f"Converting {name}  ({i + 1} of {len(files)})"
            app.post(lambda m=msg, v=i: (app.say(m), app.action.progress.configure(value=v)))
            notes = EngineNotes()
            try:
                result = run_transcribe(f, c, notes)
                if not result:
                    app.post(lambda n=name: feed.problem(n, "silent, skipped"))
                    continue
                out = save_result(result, out_dir, notes)
                ok += 1
                self.last_out_dir = os.path.dirname(out)
                found = f"{result['stem_type']} · {plural(len(result['notes']), 'note')}"
                details = describe(result)
                for w in notes.warnings():
                    details += f"  ({w})"
                app.post(lambda n=name, r=found, d=details, o=out: feed.stem(n, r, d, saved=o))
            except Exception as exc:  # keep going with the other stems
                err = f"couldn't convert: {exc}"
                app.post(lambda n=name, e=err: feed.problem(n, e))
        if ok:
            summary = ("Done", f"{ok} of {len(files)} saved", f"in {short_path(self.last_out_dir)}")
        else:
            summary = ("Nothing was converted", "", "")
        app.post(lambda: feed.summary(*summary, good=ok == len(files)))
        app.post(lambda: self._finish(ok, len(files)))

    def _finish(self, ok, total):
        app = self.app
        app.set_busy(False)
        app.action.progress["value"] = total
        app.say(f"Done: {ok} of {total} converted" if total else "Ready", "ok" if ok == total else "warn")
        if self.last_out_dir:
            app.action.open_btn.state(["!disabled"])
            if app.output_page.open_when_done.get() and ok:
                app.open_folder()


class PreviewJourney:
    """Turn the selected stem into notes and play them back before saving anything."""

    def __init__(self, app):
        self.app = app
        self.player = Player()

    def start(self):
        app = self.app
        if app.busy:
            return
        c = app.collect()
        if not c:
            return
        self.player.stop()
        f = app.convert_page.selected_stem()
        app.set_busy(True)
        app.say(f"Building preview of {os.path.basename(f)}...")
        include = app.action.with_original.get()
        threading.Thread(target=self._work, args=(f, c, include), daemon=True).start()

    def _work(self, f, c, include_original):
        app = self.app
        feed = app.convert_page.activity
        name = os.path.basename(f)
        try:
            result = run_transcribe(f, c, EngineNotes())
            if not result:
                app.post(
                    lambda: (
                        app.set_busy(False),
                        app.say("That stem is silent", "warn"),
                        feed.action(f"Preview {name}"),
                        feed.problem(name, "silent"),
                    )
                )
                return
            render_preview(result, PREVIEW_WAV, include_original)
            n = len(result["notes"])
            found = f"{result['stem_type']} · {plural(n, 'note')}"
            details = describe(result)
            app.post(lambda: (feed.action(f"Preview {name}", settings_line(c)), feed.stem(name, found, details)))
            app.post(lambda: self._play(f, n))
        except Exception as exc:
            msg = f"Preview failed: {exc}"
            app.post(lambda: (app.set_busy(False), app.say(msg, "warn")))

    def _play(self, f, n):
        app = self.app
        app.set_busy(False)
        try:
            self.player.play(PREVIEW_WAV)
            app.say(f"Playing {os.path.basename(f)}: {n} notes. Happy with it? Click Convert to save.", "ok")
        except Exception as exc:
            app.say(f"Couldn't play audio ({exc}). Preview saved to {PREVIEW_WAV}", "warn")

    def stop(self):
        self.player.stop()
        self.app.say("Stopped")


class TempoJourney:
    """Measure the real BPM of the selected stem."""

    def __init__(self, app):
        self.app = app

    def start(self):
        app = self.app
        if app.busy:
            return
        if not app.convert_page.files:
            app.say("Add a stem first, then Detect", "warn")
            app.show_page("convert")
            return
        f = app.convert_page.selected_stem()
        app.set_busy(True)
        app.say(f"Measuring tempo of {os.path.basename(f)}...")
        threading.Thread(target=self._work, args=(f,), daemon=True).start()

    def _work(self, f):
        app = self.app
        try:
            bpm = detect_tempo(f)
            app.post(lambda: self._apply(f, bpm))
        except Exception as exc:
            msg = f"Couldn't detect tempo: {exc}"
            app.post(lambda: (app.set_busy(False), app.say(msg, "warn")))

    def _apply(self, f, bpm):
        app = self.app
        app.set_busy(False)
        app.convert_page.set_tempo(bpm, f)
        app.say(f"Tempo detected: {bpm:g} BPM", "ok")
        feed = app.convert_page.activity
        feed.action("Detect tempo")
        feed.stem(os.path.basename(f), f"{bpm:g} BPM", "Set your DAW project to the same tempo")
