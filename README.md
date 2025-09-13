# Home‑Row Mouse (X11)

Control the mouse entirely from the keyboard using home‑row keys on Linux/X11. Low‑latency X11 integration with optional fallbacks.

## Features

- **Home‑row navigation**: `I/J/K/L` to move (also supports arrow keys)
- **Scrolling**: `U` scroll up; `M` or `N` scroll down (continuous while held)
- **Clicks**:
  - `H` or `Space`: Left click (hold Space to drag)
  - `;` (semicolon): Right click
- **Toggle / exit**:
  - `Super+J`: Toggle mouse mode on/off
  - `X`: Exit mouse mode
  - `ESC`: Quit the app
- **Modifiers**:
  - `Ctrl` + movement: larger step jumps
- **Smooth movement**: High‑frequency updates with optional interpolation
- **Multiple X11 backends**: Direct `xlib` (default), `xdotool`, `xinput`

## Installation

1) Install Python dependencies
```bash
pip install -r requirements.txt
```

2) (Recommended) Ensure X11 utilities are available for fallbacks
```bash
sudo apt install xdotool x11-xserver-utils
```

## Usage

Run with the default backend (xlib):
```bash
python3 x11_mouse_controller.py
```

Select a backend explicitly:
```bash
python3 x11_mouse_controller.py xlib     # default, lowest latency
python3 x11_mouse_controller.py xdotool  # most compatible
python3 x11_mouse_controller.py xinput   # low-level device control
```

### Controls

- Movement: `I/J/K/L` or arrow keys
- Large steps: hold `Ctrl` while moving
- Scroll: `U` (up), `M`/`N` (down)
- Left click: `H` or `Space` (hold Space to drag)
- Right click: `;`
- Toggle mouse mode: `Super+J`
- Exit mouse mode: `X`
- Quit app: `ESC`

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

- Designed for X11. On Wayland, results vary; prefer running an X11 session.
- Backends fall back automatically when possible; `xlib` is recommended.

## License

MIT
