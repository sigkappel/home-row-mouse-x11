"""
Home Row Mouse - Configuration

Edit these values to tune cursor behavior. Changes are picked up on next run.

Notes:
- MOVE_SPEED controls pixels per tick in one axis during continuous movement.
- MOVEMENT_INTERVAL controls how often movement ticks happen (seconds).
- ACCELERATION multiplies dx/dy when moving diagonally to keep speed natural.
- CTRL_LEAP_DISTANCE is the per-tick jump while Ctrl is held.
- SMOOTH_MOVEMENT enables small in-between steps for smoother motion.
- ANIMATION_STEPS and ANIMATION_DELAY tune the feel of smooth movement.
"""

# Backend to use by default: "xlib" (fastest), "xdotool" (compatible), or "xinput" (low-level)
DEFAULT_BACKEND = "xlib"

# Base step size in pixels per movement tick (per axis)
MOVE_SPEED = 2

# Diagonal acceleration multiplier (applied when moving both x and y)
ACCELERATION = 1.5

# Time between 
#movement updates (seconds). Lower = faster cursor (more ticks/sec)
MOVEMENT_INTERVAL = 0.004  # 250 Hz

# Per-tick jump size when Ctrl is held
CTRL_LEAP_DISTANCE = 10

# Smooth movement interpolates frames between ticks for visual smoothness
SMOOTH_MOVEMENT = True

# Number of interpolation steps per tick when smooth movement is ON
ANIMATION_STEPS = 2

# Delay between interpolation steps (seconds) when smooth movement is ON
ANIMATION_DELAY = 0.002

# Advanced: throttle heavy wake/refresh ops (seconds). Usually no need to change
WAKE_THROTTLE_SEC = 0.25
CURSOR_REFRESH_IDLE_SEC = 2.0
CURSOR_REFRESH_INTERVAL_SEC = 5.0


