"""Start Stemquill: `python -m stemquill` opens the window; add file names to use the command line."""

import importlib.util
import os
import sys


def _check_libraries():
    for name in ("numpy", "scipy", "librosa", "mido"):
        if importlib.util.find_spec(name) is None:
            print(f"Missing library: {name}. Run:  pip install -e .  (from the Stemquill folder)")
            sys.exit(1)


def _prepare_environment():
    """Make a packaged (double-clicked) copy behave like a normal one."""
    if sys.stdout is None:  # windowed app: no console to print to
        sys.stdout = open(os.devnull, "w")  # noqa: SIM115 - stays open for the life of the app
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")  # noqa: SIM115
    # Optional add-ons the Windows installer can put next to the app (e.g. basic-pitch chord detection)
    if getattr(sys, "frozen", False):
        addons = os.path.join(os.path.dirname(sys.executable), "addons")
        if os.path.isdir(addons):
            for name in sorted(os.listdir(addons)):
                path = os.path.join(addons, name)
                if os.path.isdir(path) and path not in sys.path:
                    sys.path.append(path)
    # librosa's speed-ups cache compiled code; point that somewhere writable and private. The cache is
    # loaded as code, so it must not live in a shared temp folder another user could write to.
    from .config import cache_dir

    os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(cache_dir(), "numba"))


def crash_log_path():
    """Where a crash is written: next to settings.json (%APPDATA%\\Stemquill\\crash.log on Windows)."""
    from .config import SETTINGS_PATH

    return os.path.join(os.path.dirname(SETTINGS_PATH), "crash.log")


def _open_crash_log():
    path = crash_log_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return open(path, "a", encoding="utf-8")  # noqa: SIM115 - the caller closes it, or it stays open for faulthandler


def write_crash(text):
    """Add an error report to the crash log; returns its path (or None if even that failed)."""
    import platform
    import time

    from . import __version__

    try:
        with _open_crash_log() as fh:
            fh.write(f"\n==== {time.strftime('%Y-%m-%d %H:%M:%S')} · Stemquill {__version__} · ")
            fh.write(f"Python {platform.python_version()} · {platform.platform()}\n{text}\n")
        return crash_log_path()
    except Exception:
        return None


def _show_startup_error(log_path):
    """A windowed app has no console, so say it on screen too."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        where = f"The details were saved to:\n{log_path}" if log_path else "The details couldn't be saved."
        messagebox.showerror("Stemquill couldn't start", f"Something went wrong while starting Stemquill.\n\n{where}")
        root.destroy()
    except Exception:
        pass


STARTUP_WATCH = 45  # seconds the installed app may take to open its window before it's logged as a hang


def window_opened():
    """Called once the window is on screen: the startup hang watch is no longer needed."""
    import faulthandler

    faulthandler.cancel_dump_traceback_later()


def main():
    gui = len(sys.argv) <= 1
    try:
        _prepare_environment()
        if getattr(sys, "frozen", False):
            # a crash inside a compiled library (no Python error at all) still leaves a trace
            import contextlib
            import faulthandler

            with contextlib.suppress(Exception):
                log = _open_crash_log()
                faulthandler.enable(file=log)
                if gui:
                    # If the window hasn't opened after a while, write down what every thread is
                    # doing: a hang leaves no error behind otherwise. Cancelled once the window is up.
                    faulthandler.dump_traceback_later(STARTUP_WATCH, file=log)
        _check_libraries()
        if not gui:
            from .cli import main as cli_main

            cli_main()
        else:
            from .gui import run_gui

            run_gui()
    except (SystemExit, KeyboardInterrupt):
        raise
    except BaseException:
        import traceback

        log_path = write_crash(traceback.format_exc())
        if gui:
            _show_startup_error(log_path)
        raise


if __name__ == "__main__":
    main()
