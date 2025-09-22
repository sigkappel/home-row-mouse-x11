# Home-Row Mouse (X11)

Control your X11 pointer from the home row. Hold the left `Alt` key to enter mouse mode, steer with `I/J/K/L`, and click without ever leaving the keyboard. The controller injects X11 events directly (default) and falls back to `xdotool`/`xinput` when needed.

## Features

- **Alt-held mouse mode**: Press and hold the left `Alt` key to capture movement and click bindings; release `Alt` to give keyboard control back to the desktop.
- **Home-row navigation**: `I/J/K/L` (or the arrow keys) move the cursor; holding `Ctrl` increases the step size.
- **Scrolling**: `U` scrolls up, `M` or `N` scroll down. Scroll repeats while keys are held.
- **Clicks & drags**: `H` taps left click, `Space` presses and holds the left button (drag), `;` performs a right click.
- **No Alt+click surprises**: When Alt is held, clicks are emitted without the modifier so browsers (e.g. Chrome) follow links instead of downloading them.
- **Smooth, fast motion**: High-frequency update loop with optional interpolation; default `xlib` backend avoids Python subprocess overhead.
- **Backend fallbacks**: Choose `xdotool` or `xinput` explicitly for compatibility testing.

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```
2. (Recommended) Install X11 helper tools (`xdotool` is used for some edge cases):
```bash
sudo apt install xdotool x11-xserver-utils
```

## Usage

Activate a virtualenv if desired, then run the controller with the default backend:
```bash
python3 hrm.py
```

Select a backend explicitly (optional):
```bash
python3 hrm.py xlib     # default, lowest latency
python3 hrm.py xdotool  # subprocess-driven fallback
python3 hrm.py xinput   # low-level device control
```

### Controls

- **Enter mouse mode**: Hold `Alt`.
- **Move**: `I/J/K/L` or arrow keys (Alt must be held). Hold `Ctrl` for larger steps.
- **Scroll**: Alt+`U` scroll up; Alt+`M`/`N` scroll down.
- **Left click**: Alt+`H`. Alt+`Space` holds the left button for dragging; release `Space` to drop.
- **Right click**: Alt+`;` (semicolon).
- **Exit mouse mode**: Release `Alt`.
- **Quit controller**: `Ctrl+Q`.

### Configuration

Edit `config.py` to tune behavior:

- `DEFAULT_BACKEND` (`"xlib" | "xdotool" | "xinput"`)
- `MOVE_SPEED` (per‑tick pixels)
- `ACCELERATION` (applies when moving diagonally)
- `MOVEMENT_INTERVAL` (seconds between ticks)
- `CTRL_LEAP_DISTANCE` (bigger step while Ctrl is held)
- `SMOOTH_MOVEMENT`, `ANIMATION_STEPS`, `ANIMATION_DELAY`
- `SCROLL_STEP` (per‑tick scroll amount)

## Notes

- Designed for X11. On Wayland, behavior depends on the compositor and may be limited.
- The controller automatically routes Alt-held clicks through a modifier-free path; Chrome, Firefox, and other apps receive a normal left click.
- Backends fall back automatically when possible; `xlib` provides the lowest latency.

## License

MIT
