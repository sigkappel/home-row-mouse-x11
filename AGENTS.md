# Repository Guidelines

## Project Structure & Module Organization
Top-level Python sources live in `hrm.py`, which owns the X11 keyboard-to-mouse controller, and `config.py`, which exposes runtime tuning knobs (speed, acceleration, smoothness). Dependency pins sit in `requirements.txt`. `README.md` covers user-facing setup, while any local virtualenv should remain inside `venv/` and be excluded from commits. Keep new modules under the repository root unless you introduce a `src/` layout; group backend-specific helpers alongside `hrm.py` until they warrant their own package.

## Build, Test, and Development Commands
Set up a sandboxed environment before hacking:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Run the controller with the default backend or select one explicitly:
```bash
python3 hrm.py           # uses DEFAULT_BACKEND from config.py
python3 hrm.py xdotool   # switch backend for compatibility testing
```
Log statements print to stdout; prefer `python3 -u hrm.py` while debugging to keep output flush.

## Coding Style & Naming Conventions
Follow standard Python 3 style: 4-space indentation, snake_case for functions and variables, PascalCase for classes/enums. Type hints are welcome when they clarify complex data flows. Keep platform checks and subprocess calls wrapped in helper functions so alternative backends stay isolated. Configuration constants belong in `config.py`; avoid redefining them inline.

## Testing Guidelines
There is no automated test suite yet; validate changes by running `python3 hrm.py` and exercising key chords (movement, clicks, scroll, toggles) with each supported backend that your system offers. When adding new behavior, include a quick manual test checklist in your pull request. If you script regressions, co-locate them in a future `tests/` directory and document execution with `pytest` or `python -m unittest`.

## Commit & Pull Request Guidelines
History mixes imperative (“patched the issue…”) and scoped (“Docs: ...”) messages; prefer the scoped, capitalized style: `Type: concise summary` (e.g., `Fix: prevent ESC shutdown`). Keep commits focused—configuration tweaks separate from backend refactors. For pull requests, describe the motivation, enumerate user-visible changes, mention manual test coverage, and link related issues. Include screenshots or recordings if the behavior changes noticeably, especially for cursor motion or keybindings.

## Configuration & Safety Tips
Changes to motion feel should default to `config.py`; call out new knobs in the README. Be cautious with `xdotool`/`xinput` subprocess failures—wrap them with clear error logs so users know how to recover. On Wayland sessions, note the limitations prominently in your PR notes.
