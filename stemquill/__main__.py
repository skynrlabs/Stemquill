"""Start Stemquill: `python -m stemquill` opens the window; add file names to use the command line."""

import importlib.util
import sys


def _check_libraries():
    for name in ("numpy", "scipy", "librosa", "mido"):
        if importlib.util.find_spec(name) is None:
            print(f"Missing library: {name}. Run:  pip install -r requirements.txt")
            sys.exit(1)


def main():
    _check_libraries()
    if len(sys.argv) > 1:
        from .cli import main as cli_main
        cli_main()
    else:
        from .gui import run_gui
        run_gui()


if __name__ == "__main__":
    main()
