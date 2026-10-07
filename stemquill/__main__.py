"""Start Stemquill: `python -m stemquill` opens the window; add file names to use the command line."""

import importlib.util
import os
import sys
import tempfile


def _check_libraries():
    for name in ("numpy", "scipy", "librosa", "mido"):
        if importlib.util.find_spec(name) is None:
            print(f"Missing library: {name}. Run:  pip install -e .  (from the Stemquill folder)")
            sys.exit(1)


def _prepare_environment():
    """Make a packaged (double-clicked) copy behave like a normal one."""
    if sys.stdout is None:  # windowed app: no console to print to
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    # librosa's speed-ups cache compiled code; point that somewhere writable
    os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(tempfile.gettempdir(), "stemquill-numba"))


def main():
    _prepare_environment()
    _check_libraries()
    if len(sys.argv) > 1:
        from .cli import main as cli_main
        cli_main()
    else:
        from .gui import run_gui
        run_gui()


if __name__ == "__main__":
    main()
