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
4. Make sure it runs: `python -m py_compile stemquill.py`, then open the GUI and convert a stem.
5. Write a clear PR description — what changed and why. Before/after note counts on a test stem are great for detection changes.
6. Link any related issue in the PR body (`Closes #123`).

---

## Coding Standards

- **Language:** Python 3.10+
- **Style:** Follow existing patterns in the file. Do not reformat unrelated code.
- **Naming:** `snake_case` for functions and variables, `UPPER_CASE` for constants.
- **GUI threads:** Never touch Tkinter widgets from a worker thread. Send updates through the existing queue.
- **Dependencies:** Do not add required dependencies without discussion. Optional ones (like basic-pitch) must fail gracefully.
- **No dead code:** Do not leave commented-out code in PRs.

---

## Running Locally

```
git clone https://github.com/skynrlabs/Stemquill.git
cd Stemquill
pip install -r requirements.txt
python stemquill.py
```

---

## Questions

Open a GitHub Discussion if you have a question that is not a bug or feature request.
