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


def run_transcribe(stem, c, notes):
    """Transcribe one stem with the shared song settings (c) and the stem's own settings."""
    return transcribe(
        stem.path,
        stem.stem_type,
        c["bpm"],
        c["grid"],
        stem.sensitivity,
        stem.parts,
        notes,
        c["drum_map"],
        stem.humanize / 100.0,
    )


def song_line(c):
    snap = "no snap" if not c["grid"] else f"snap {c['grid_label']}"
    return f"{c['bpm']:g} BPM · {snap} · {c['map_key']} drum map"


def stem_line(stem):
    human = f"humanize {stem.humanize}%" if stem.humanize else "no humanize"
    return f"sensitivity {stem.sensitivity:.2f} · {human}"


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
        stems = list(app.convert_page.stems)
        app.activity.action(f"Convert {plural(len(stems), 'stem')}", song_line(c))
        for stem in stems:
            self._status(stem, "waiting...", "muted")
        app.set_busy(True)
        app.action.open_btn.state(["disabled"])
        app.say(f"Converting {plural(len(stems), 'stem')}...", "busy", "Each row shows its result as it finishes")
        app.status_card.start_progress(len(stems))
        threading.Thread(target=self._work, args=(stems, c, app.settings_page.out_dir), daemon=True).start()

    def _status(self, stem, text, kind, saved=None):
        """Update a stem's status (call on the window's thread)."""
        stem.status, stem.status_kind = text, kind
        if saved:
            stem.saved = saved
        self.app.convert_page.show_status(stem)

    def _work(self, stems, c, out_dir):
        app = self.app
        feed = app.activity
        ok = 0
        for i, stem in enumerate(stems):
            name = stem.name
            msg = f"Converting {name}  ({i + 1} of {len(stems)})"
            app.post(
                lambda m=msg, v=i, s=stem: (
                    app.say(m, "busy", "Each row shows its result as it finishes"),
                    app.status_card.set_progress(v),
                    self._status(s, "converting...", "busy"),
                )
            )
            notes = EngineNotes()
            try:
                result = run_transcribe(stem, c, notes)
                if not result:
                    app.post(
                        lambda n=name, s=stem: (
                            feed.problem(n, "silent, skipped"),
                            self._status(s, "silent, skipped", "warn"),
                        )
                    )
                    continue
                out = save_result(result, out_dir, notes)
                ok += 1
                self.last_out_dir = os.path.dirname(out)
                count = plural(len(result["notes"]), "note")
                found = f"{result['stem_type']} · {count}"
                details = describe(result) + f" · {stem_line(stem)}"
                for w in notes.warnings():
                    details += f"  ({w})"
                done = f"saved · {count}"
                app.post(
                    lambda n=name, r=found, d=details, o=out, s=stem, t=done: (
                        feed.stem(n, r, d, saved=o),
                        self._status(s, t, "ok", saved=o),
                    )
                )
            except Exception as exc:  # keep going with the other stems
                err = f"couldn't convert: {exc}"
                app.post(lambda n=name, e=err, s=stem: (feed.problem(n, e), self._status(s, e, "warn")))
        if ok:
            summary = ("Done", f"{ok} of {len(stems)} saved", f"in {short_path(self.last_out_dir)}")
        else:
            summary = ("Nothing was converted", "", "")
        app.post(lambda: feed.summary(*summary, good=ok == len(stems)))
        app.post(lambda: self._finish(ok, len(stems)))

    def _finish(self, ok, total):
        app = self.app
        app.set_busy(False)
        app.status_card.set_progress(total)
        skipped = total - ok
        if ok:
            detail = f"Saved in {short_path(self.last_out_dir)} · drag each .mid onto its track at bar 1"
            if skipped:
                detail = f"{skipped} skipped (see the Stems list) · " + detail
        else:
            detail = "Check the Stems list for what went wrong"
        app.say(f"Done: {ok} of {total} converted", "ok" if ok == total else "warn", detail)
        if self.last_out_dir:
            app.action.open_btn.state(["!disabled"])
            if app.settings_page.open_when_done.get() and ok:
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
        stem = app.convert_page.selected_stem()
        app.set_busy(True)
        app.say(f"Building preview of {stem.name}...", "busy", "This takes a few seconds")
        include = app.action.with_original.get()
        threading.Thread(target=self._work, args=(stem, c, include), daemon=True).start()

    def _work(self, stem, c, include_original):
        app = self.app
        feed = app.activity
        name = stem.name
        f = stem.path
        try:
            result = run_transcribe(stem, c, EngineNotes())
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
            details = describe(result) + f" · {stem_line(stem)}"
            app.post(lambda: (feed.action(f"Preview {name}", song_line(c)), feed.stem(name, found, details)))
            app.post(lambda: self._play(f, n))
        except Exception as exc:
            msg = f"Preview failed: {exc}"
            app.post(lambda: (app.set_busy(False), app.say(msg, "warn")))

    def _play(self, f, n):
        app = self.app
        app.set_busy(False)
        try:
            self.player.play(PREVIEW_WAV)
            app.say(
                f"Playing {os.path.basename(f)} · {n} notes",
                "ok",
                "Happy with it? Click Convert all to MIDI to save. Stop preview ends playback.",
            )
        except Exception as exc:
            app.say("Couldn't play the preview", "warn", f"{exc}. The preview was saved to {PREVIEW_WAV}")

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
        stem = app.convert_page.selected_stem()
        if stem is None:
            app.say("Add a stem first, then Detect", "warn")
            app.show_page("convert")
            return
        f = stem.path
        app.set_busy(True)
        app.say(f"Measuring the tempo of {os.path.basename(f)}...", "busy", "This takes a few seconds")
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
        app.say(f"Tempo: {bpm:g} BPM", "ok", "Set your DAW project to the same tempo")
        feed = app.activity
        feed.action("Detect tempo")
        feed.stem(os.path.basename(f), f"{bpm:g} BPM", "Set your DAW project to the same tempo")
