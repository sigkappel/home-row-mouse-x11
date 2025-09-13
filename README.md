# Mouse Controller

A Python application that allows you to control your mouse cursor using arrow keys on Linux.

## Features

- **Arrow Key Control**: Use arrow keys to move the mouse cursor
- **Click Functions**: Space for left click, Enter for right click
- **Configurable Speed**: Adjustable movement speed and acceleration
- **Smooth Movement**: High FPS movement for responsive control
- **Easy Exit**: Press ESC to exit gracefully

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Make the script executable:
```bash
chmod +x mouse_controller.py
```

## Usage

Run the application:
```bash
python3 mouse_controller.py
```

Or run directly:
```bash
./mouse_controller.py
```

### Controls

- **Arrow Keys**: Move mouse cursor
- **Space**: Left mouse click
- **Enter**: Right mouse click
- **ESC**: Exit application
- **Ctrl+C**: Force exit

### Configuration

When you start the application, you'll be prompted to set:
- **Movement Speed**: Base speed in pixels (default: 10)
- **Acceleration**: Multiplier for diagonal movement (default: 1.5)

## Requirements

- Python 3.6+
- Linux system
- Required packages (see requirements.txt):
  - pynput: For keyboard input capture
  - pyautogui: For mouse control

## Notes

- The application disables pyautogui's failsafe for smoother operation
- Movement speed increases gradually when holding keys for continuous movement
- Diagonal movement (multiple keys) uses acceleration for better control
- Requires appropriate permissions for keyboard input and mouse control

## Troubleshooting

If you encounter permission issues:
- Make sure you're running the script in a terminal that has access to input devices
- On some systems, you may need to run with `sudo` (though this is not recommended for security reasons)
- Check that your user has access to `/dev/input/` devices

## License

This project is open source and available under the MIT License.
