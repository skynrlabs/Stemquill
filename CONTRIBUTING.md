# Contributing to Stemquill

Thank you for your interest in contributing. Please read this document before opening issues or pull requests.

---

## Code of Conduct

Be respectful. Harassment, discrimination, or abusive language toward any contributor will not be tolerated and may result in removal from the project. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## License

Stemquill is open-source under the **MIT** license. By submitting a contribution you agree to license your work under the same terms.

---

## Branch Model

| Branch | Purpose |
|---|---|
| `main` | Stable, release-ready. Never commit directly here. |
| `dev` | Integration target. All PRs merge here first. |
| `feature/*` | New features (`feature/cowbell-detection`) |
| `fix/*` | Bug fixes (`fix/tempo-half-time`) |
| `release/*` | Release stabilization (`release/v1.1`) |

**Flow:** `feature/* / fix/*` → PR to `dev` → PR to `main` → tag release

---

## Opening Issues

Before opening an issue:

- Search existing issues to avoid duplicates.
- For bugs, include: OS, Python version, stem type, the settings you used, and what you expected vs. what happened.
- For detection problems (wrong drums, missing notes), a short clip of the stem helps a lot, if you have the rights to share it.
- For feature requests, describe the problem you are trying to solve, not just the solution.
- For security issues, **do not open a public issue** — see [SECURITY.md](SECURITY.md).

---

## Submitting a Pull Request

1. Fork the repo and create your branch from `dev`, not `main`.
2. Name your branch `feature/short-description` or `fix/short-description`.
3. Keep PRs focused — one feature or fix per PR.
4. Run the checks locally (see **Tests and lint** below). On GitHub, both workflows must pass: **Lint and test** (Linux) and **Build Windows app** (builds the installer and converts test stems).
5. Write a clear PR description — what changed and why. Before/after note counts on a test stem are great for detection changes.
6. Link any related issue in the PR body (`Closes #123`).

---

## Coding Standards

- **Language:** Python 3.10+
- **Style:** Follow existing patterns in the file. Do not reformat unrelated code.
- **Naming:** `snake_case` for functions and variables, `UPPER_CASE` for constants.
- **Keep the layers apart:** audio code goes in `stemquill/core/` and must not import Tkinter; window code goes in `stemquill/gui/`.
- **GUI threads:** Never touch Tkinter widgets from a worker thread. Use `app.post()` and `app.log()` from `gui/app.py`.
- **New page?** Add a module in `gui/pages/` and an entry in `PAGES`. **New workflow?** Add a journey class in `gui/journeys.py`.
- **Dependencies:** Do not add required dependencies without discussion. Optional ones (like basic-pitch) must fail gracefully.
- **No dead code:** Do not leave commented-out code in PRs.

---

## Running Locally

```
git clone https://github.com/skynrlabs/Stemquill.git
cd Stemquill
pip install -e ".[dev]"
python -m stemquill
```

---

## Tests and lint

```
ruff check .            # lint
ruff format .           # format (CI runs `ruff format --check`)
pytest                  # all tests, about 15 seconds
```

- The tests build **synthetic stems with a known right answer** (`tests/synth.py`): exact drum hits, exact tempos, exact notes. They check the right drum, note and timing come out, not just that nothing crashes.
- **Window tests** (`tests/test_gui.py`) open the real app. They need a display: on Linux run `xvfb-run -a pytest`; without one they're skipped.
- **Snapshot tests** (`tests/snapshots/`) catch any change to results. If you changed detection on purpose, run `pytest --update-snapshots` and commit the updated files so the change is visible in review.
- Add a test with every bug fix: reproduce it with a synthetic stem first.

---

## Releasing

Every push to `main` builds and tests the Windows app; the installer appears under the run's **Artifacts** on the Actions tab. To publish a release:

1. Bump `__version__` in `stemquill/__init__.py` and push.
2. On GitHub, go to **Releases → Draft a new release**, create the tag `v` + the version (for example `v1.0.1`) and click **Publish release**.
3. GitHub Actions builds and tests the installer for that tag. Download it from the run's **Artifacts** on the Actions tab.
4. Upload `Stemquill-Setup-x.y.z.exe` to the [itch.io page](https://skynrlabs.itch.io/stemquill). Downloads are only published on itch.io, not attached to GitHub releases.

---

## Questions

Open a GitHub Discussion if you have a question that is not a bug or feature request.
