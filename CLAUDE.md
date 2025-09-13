# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based mouse controller application for Linux that allows keyboard-based mouse cursor control. The project consists of several Python scripts with no complex build system or traditional package structure.

## Development Commands

### Installation and Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Make scripts executable
chmod +x mouse_controller.py
chmod +x toggle_mouse.py
```

### Running the Application

#### Original PyAutoGUI Version
```bash
# Run the main mouse controller
python3 mouse_controller.py
# or
./mouse_controller.py

# Toggle the controller on/off (background daemon)
./toggle_mouse.py
```

#### X11-Native Version (Recommended)
```bash
# Run with default backend (python3-xlib - fastest)
python3 x11_mouse_controller.py
# or
./x11_mouse_controller.py

# Run with specific X11 backend
./x11_mouse_controller.py xlib     # Direct X11 via python3-xlib (fastest)
./x11_mouse_controller.py xdotool  # Command-line xdotool (most compatible)
./x11_mouse_controller.py xinput   # Low-level device control

# Enhanced toggle script with backend selection
./toggle_x11_mouse.py              # Toggle on/off (xlib backend)
./toggle_x11_mouse.py xdotool      # Toggle with xdotool backend
./toggle_x11_mouse.py start xlib   # Start with xlib backend
./toggle_x11_mouse.py stop         # Stop controller
./toggle_x11_mouse.py status       # Show status
./toggle_x11_mouse.py help         # Show all options
```

#### Test Scripts
```bash
# Test GUI overlay functionality
python3 simple_test.py
python3 test_overlay.py
```

## Architecture Overview

### Core Components

#### PyAutoGUI Version (Original)
- **mouse_controller.py**: Main application with `MouseController` class that handles:
  - Keyboard event listening using `pynput`
  - Mouse movement and clicking via `pyautogui` 
  - Toggle mode system (Super+J to enable/disable mouse control)
  - Multiple input schemes: arrow keys and IJKL navigation
  - Acceleration and speed control for smooth movement

- **toggle_mouse.py**: Basic daemon management script for PyAutoGUI version

#### X11-Native Version (Recommended)
- **x11_mouse_controller.py**: Enhanced X11-native controller with `X11MouseController` class:
  - **Multiple X11 backends**: Direct python3-xlib, xdotool commands, xinput device control
  - **Lower latency**: Direct X11 protocol communication eliminates PyAutoGUI overhead
  - **Better compatibility**: Fallback mechanisms between different X11 approaches
  - **Same controls**: Identical key mappings and behavior as original
  - **Enhanced debugging**: Backend selection and status reporting

- **toggle_x11_mouse.py**: Advanced daemon management with:
  - Backend selection support (`xlib`, `xdotool`, `xinput`)
  - Status reporting and process monitoring
  - Enhanced command-line interface
  - Uses PID file management (`/tmp/x11_mouse_controller.pid`)
  - Comprehensive logging to `/tmp/x11_toggle_debug.log`

- **Test Scripts**: Simple GUI overlay tests using tkinter to verify display functionality

### Key Design Patterns

- **Event-driven architecture**: Uses `pynput.keyboard.Listener` for non-blocking keyboard input
- **State management**: Tracks pressed keys, speed, and mode state in the controller class
- **Process management**: Toggle script manages background daemon execution
- **Failsafe mechanisms**: PyAutoGUI failsafe enabled, cursor visibility restoration

### Control Scheme

The application supports dual control modes:
- Arrow keys + Space/Enter for clicking
- IJKL navigation (vim-like) + U/O for clicking  
- Ctrl+movement keys for large leaps (200px)
- Super+J to toggle mouse mode on/off

### Important Implementation Details

- Runs at 1000 FPS (1ms sleep) for ultra-responsive movement
- Non-suppressive keyboard listening to prevent cursor hiding issues
- Cursor visibility restoration using X11 commands (`xsetroot`, `gsettings`)
- PID-based process management for daemon functionality

## Dependencies

### Python Packages
- `pynput==1.7.6`: Keyboard input capture (both versions)
- `pyautogui==0.9.54`: Mouse control for original version
- `python3-xlib==0.15`: Direct X11 protocol access (X11 version)

### System Dependencies (X11 Version)
- `xdotool`: Command-line X11 automation (install: `sudo apt install xdotool`)
- `xinput`: Low-level input device control (usually pre-installed)
- `xset`, `xrandr`: Display configuration utilities (usually pre-installed)

### Standard Library
- `tkinter`, `subprocess`, `os`, `signal`, `enum`, `typing`

## X11 Backend Comparison

| Backend | Speed | Compatibility | Use Case |
|---------|-------|---------------|----------|
| **xlib** | Fastest | Good | Default choice, direct X11 protocol |
| **xdotool** | Medium | Excellent | Fallback, works with all X11 setups |
| **xinput** | Medium | Good | Low-level device control, complex setup |

**Recommendation**: Use `xlib` backend (default) for best performance, fallback to `xdotool` if issues occur.