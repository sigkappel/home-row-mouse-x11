#!/usr/bin/env python3
"""
X11-based Mouse Controller - Direct X11 integration with multiple backend options
Provides closer-to-metal X11 control compared to PyAutoGUI
"""

import time
import sys
import subprocess
import os
import threading
import gc
from contextlib import nullcontext
from pynput import keyboard
import config
from enum import Enum
from typing import Tuple, Optional
import signal

class X11Backend(Enum):
    XLIB = "xlib"           # Direct python3-xlib (fastest)
    XDOTOOL = "xdotool"     # Command-line xdotool (most compatible)
    XINPUT = "xinput"       # Low-level device control

class X11MouseController:
    def __init__(self, backend: X11Backend = X11Backend.XLIB, move_speed: Optional[int] = None, acceleration: Optional[float] = None):
        """
        Initialize X11 mouse controller with selectable backend.
        
        Args:
            backend: X11Backend to use for mouse control
            move_speed: Base movement speed in pixels (default: 5px)
            acceleration: Acceleration multiplier for diagonal movement
        """
        self.backend = backend
        self.move_speed = move_speed if move_speed is not None else int(getattr(config, 'MOVE_SPEED', 5))
        self.acceleration = acceleration if acceleration is not None else float(getattr(config, 'ACCELERATION', 1.5))
        self.display_lock = threading.RLock()
        self.current_speed = self.move_speed
        self.running = True
        self.mouse_mode = False
        self.movement_keys = set()  # Track which movement keys are pressed
        self.ctrl_pressed = False
        self.shift_pressed = False
        self.alt_pressed = False
        self.ctrl_leap_distance = int(getattr(config, 'CTRL_LEAP_DISTANCE', 50))  # Ctrl modifier distance
        self.last_cursor_refresh = 0  # Track last cursor refresh time
        self.space_click_active = False  # Track Space-as-left-button state

        # X11 key grabbing for suppression
        self.grabbed_keys = set()  # Track grabbed keys
        self.key_grab_active = False
        self.x11_event_thread = None
        self.x11_events_active = False
        self.listener = None

        # Continuous movement settings
        self.movement_thread = None
        self.movement_active = False
        self.movement_interval = float(getattr(config, 'MOVEMENT_INTERVAL', 0.004))
        
        # Performance optimization counters
        self.movement_counter = 0  # Track movements to reduce expensive operations
        self.last_gc_time = time.time()  # Track last garbage collection
        
        # Cached mouse position to avoid repeated X11 queries
        self.cached_mouse_x = 0
        self.cached_mouse_y = 0
        self.last_position_update = 0
        
        # Debug/logging control and activity tracking
        self.debug = False
        self.last_movement_time = time.time()
        
        # Smooth movement settings
        self.smooth_movement = bool(getattr(config, 'SMOOTH_MOVEMENT', True))
        self.animation_steps = int(getattr(config, 'ANIMATION_STEPS', 2))
        self.animation_delay = float(getattr(config, 'ANIMATION_DELAY', 0.002))
        
        # Throttles for expensive operations
        self.last_wake_time = 0.0
        self.animation_move_counter = 0
        
        # Scroll key tracking (U/M)
        self.scroll_keys = set()
        
        # Screen geometry (for clamping)
        self.screen_width = 0
        self.screen_height = 0

        # Scroll settings
        self.scroll_step = int(getattr(config, 'SCROLL_STEP', 1))

        # Environment capability detection
        self.session_type = os.environ.get('XDG_SESSION_TYPE', '').lower()
        self.is_wayland = self.session_type == 'wayland'
        try:
            self.ydotool_available = (subprocess.run(['which', 'ydotool'], capture_output=True).returncode == 0)
        except:
            self.ydotool_available = False
        
        # Initialize X11 backend
        self._init_backend()
        
        # Ensure cursor is visible on startup
        self._restore_cursor_visibility()
        
        # Disable screen saver and DPMS to prevent cursor hiding
        self._disable_screensaver()
        
        print(f"X11 Mouse Controller Started! (Backend: {backend.value})")
        print("Controls:")
        print(f"  Hold Alt + Arrow Keys/I/J/K/L: Move mouse ({self.move_speed}px per press)")
        print(f"  Hold Alt + Ctrl: Larger steps ({self.ctrl_leap_distance}px per press)")
        print("  Hold Alt + U: Scroll up; Alt + M/N: Scroll down")
        print("  Ctrl+Q: Exit app")
        print("  Hold Alt + H/Space: Left click (Space holds for drag); Alt + ;: Right click")
        smooth_status = "ON" if self.smooth_movement else "OFF"
        print(f"\nSmooth movement: {smooth_status}")
        print("Mouse mode: Press and hold Alt to control the cursor")

        if self.backend == X11Backend.XLIB:
            self._grab_alt_keys_only()

    def _display_guard(self):
        """Return an appropriate context manager for Display access."""
        if self.backend != X11Backend.XLIB or self.display_lock is None:
            return nullcontext()
        return self.display_lock

    def _grab_alt_keys_only(self):
        """Ensure Alt toggles mouse mode without breaking desktop shortcuts."""
        if self.backend != X11Backend.XLIB:
            return

        # Previous revisions grabbed Alt globally, which blocked Alt+Tab and other
        # window manager shortcuts. We now rely on the pynput listener for Alt
        # detection, so make sure no stale grabs remain.
        with self._display_guard():
            try:
                from Xlib import X
                import Xlib.XK

                self._push_ignore_badaccess()
                try:
                    for keysym in (Xlib.XK.XK_Alt_L, Xlib.XK.XK_Alt_R):
                        keycode = self.display.keysym_to_keycode(keysym)
                        if not keycode:
                            continue
                        try:
                            # Release any passive grabs from earlier runs.
                            self.root.ungrab_key(keycode, X.AnyModifier)
                        except:
                            pass
                finally:
                    self._pop_error_handler()
            except Exception as e:
                if self.debug:
                    print(f"Alt ungrab check failed: {e}")

    def _init_backend(self):
        """Initialize the selected X11 backend"""
        if self.backend == X11Backend.XLIB:
            try:
                from Xlib.display import Display
                from Xlib import X
                from Xlib.ext.xtest import fake_input
                import Xlib.XK
                
                self.display = Display()
                self.screen = self.display.screen()
                self.root = self.screen.root
                # Cache screen geometry for clamping
                try:
                    self.screen_width = int(self.screen.width_in_pixels)
                    self.screen_height = int(self.screen.height_in_pixels)
                except:
                    self.screen_width = 0
                    self.screen_height = 0
                print("✓ Using python3-xlib backend (direct X11)")
            except ImportError as e:
                print(f"✗ python3-xlib not available: {e}")
                print("  Falling back to xdotool...")
                self.backend = X11Backend.XDOTOOL
                self._init_backend()
                
        elif self.backend == X11Backend.XDOTOOL:
            if subprocess.run(['which', 'xdotool'], capture_output=True).returncode == 0:
                print("✓ Using xdotool backend")
                # Best-effort detect screen size for clamping utilities
                try:
                    result = subprocess.run(['xrandr'], capture_output=True, text=True)
                    width = height = 0
                    for line in result.stdout.split('\n'):
                        if ' connected primary ' in line and 'x' in line:
                            # Example: "eDP-1 connected primary 2560x1600+0+0 ..."
                            try:
                                res = line.split()[3].split('+')[0]
                                width, height = map(int, res.split('x'))
                                break
                            except:
                                pass
                    if width == 0 or height == 0:
                        # Fallback: try first ' connected '
                        for line in result.stdout.split('\n'):
                            if ' connected ' in line and 'x' in line:
                                try:
                                    # Some xrandr formats use position at field 2
                                    parts = line.split()
                                    for token in parts:
                                        if 'x' in token and '+' in token:
                                            res = token.split('+')[0]
                                            width, height = map(int, res.split('x'))
                                            raise Exception('done')
                                except:
                                    pass
                        # If still unknown, leave as 0,0
                    self.screen_width = width
                    self.screen_height = height
                except:
                    self.screen_width = 0
                    self.screen_height = 0
            else:
                print("✗ xdotool not found, install with: sudo apt install xdotool")
                sys.exit(1)
                
        elif self.backend == X11Backend.XINPUT:
            if subprocess.run(['which', 'xinput'], capture_output=True).returncode == 0:
                print("✓ Using xinput backend")
                # Best-effort detect screen size via xrandr
                try:
                    result = subprocess.run(['xrandr'], capture_output=True, text=True)
                    width = height = 0
                    for line in result.stdout.split('\n'):
                        if ' connected primary ' in line and 'x' in line:
                            try:
                                res = line.split()[3].split('+')[0]
                                width, height = map(int, res.split('x'))
                                break
                            except:
                                pass
                    self.screen_width = width
                    self.screen_height = height
                except:
                    self.screen_width = 0
                    self.screen_height = 0
                # Get pointer device info
                try:
                    result = subprocess.run(['xinput', 'list', '--short'], 
                                          capture_output=True, text=True)
                    print("Available input devices:")
                    for line in result.stdout.split('\n')[:3]:  # Show first 3 devices
                        if 'pointer' in line.lower():
                            print(f"  {line.strip()}")
                except:
                    pass
            else:
                print("✗ xinput not found")
                sys.exit(1)

    def _restore_cursor_visibility(self):
        """Force cursor to be visible using multiple X11 methods"""
        try:
            # Method 1: Use xsetroot to refresh cursor
            subprocess.run(['xsetroot', '-cursor_name', 'left_ptr'], 
                          capture_output=True, timeout=1)
        except:
            pass
            
        try:
            # Method 2: Reset cursor theme via gsettings (GNOME)
            subprocess.run(['gsettings', 'set', 'org.gnome.desktop.interface', 
                          'cursor-theme', 'default'], capture_output=True, timeout=1)
        except:
            pass
            
        try:
            # Method 3: Use xset to reset screen saver (can affect cursor)
            subprocess.run(['xset', 's', 'reset'], capture_output=True, timeout=1)
        except:
            pass

    def _disable_screensaver(self):
        """Disable screensaver and DPMS to prevent cursor hiding"""
        try:
            # Disable X11 screensaver
            subprocess.run(['xset', 's', 'off'], capture_output=True, timeout=1)
            subprocess.run(['xset', 's', 'noblank'], capture_output=True, timeout=1)
            # Disable DPMS (Display Power Management)
            subprocess.run(['xset', '-dpms'], capture_output=True, timeout=1)
        except:
            pass

    def _set_mouse_mode(self, enabled: bool):
        """Enable or disable mouse mode depending on Alt state."""
        enabled = bool(enabled)
        if self.mouse_mode == enabled:
            return

        self.mouse_mode = enabled
        if self.mouse_mode:
            self._grab_navigation_keys()
            self._sync_cached_position_from_os()
            print("\nMouse mode: ON (Alt held)")
        else:
            self.movement_keys.clear()
            self.scroll_keys.clear()
            self._stop_continuous_movement()
            if self.space_click_active:
                self.release_mouse(1)
                self.space_click_active = False
            self._ungrab_navigation_keys_only()
            print("\nMouse mode: OFF")

    def _push_ignore_badaccess(self):
        """Temporarily ignore BadAccess X errors (used during grab/ungrab)."""
        if self.backend != X11Backend.XLIB:
            return
        with self._display_guard():
            try:
                from Xlib import error as xerror
                # Save old handler if available
                try:
                    self._old_x_error_handler = self.display.get_error_handler()
                except:
                    self._old_x_error_handler = None

                def _handler(err, *args, **kwargs):
                    # Silently ignore BadAccess errors
                    if isinstance(err, xerror.BadAccess):
                        return None
                    # Fallback to previous handler if it exists
                    if self._old_x_error_handler:
                        try:
                            return self._old_x_error_handler(err, *args, **kwargs)
                        except:
                            return None
                    # Otherwise, swallow
                    return None

                self.display.set_error_handler(_handler)
            except:
                pass

    def _pop_error_handler(self):
        """Restore previous X error handler if we changed it."""
        if self.backend != X11Backend.XLIB:
            return
        with self._display_guard():
            try:
                if hasattr(self, '_old_x_error_handler'):
                    self.display.set_error_handler(self._old_x_error_handler)
                    self._old_x_error_handler = None
            except:
                pass

    def _suppress_current_event(self):
        """Best-effort suppression for the keyboard event currently being handled."""
        if self.listener and hasattr(self.listener, 'suppress_event'):
            try:
                self.listener.suppress_event()
            except AttributeError:
                pass

    def _release_movement_key(self, key_equivalent) -> bool:
        """Centralised helper to stop movement tied to a specific key."""
        removed = False
        if key_equivalent in self.movement_keys:
            self.movement_keys.discard(key_equivalent)
            removed = True
        if removed and not self.movement_keys and not self.scroll_keys:
            self._stop_continuous_movement()
        return removed

    def _release_scroll_key(self, direction: str) -> bool:
        removed = direction in self.scroll_keys
        if removed:
            self.scroll_keys.discard(direction)
            if not self.movement_keys and not self.scroll_keys:
                self._stop_continuous_movement()
        return removed

    def _grab_navigation_keys(self):
        """Grab navigation keys to prevent them from reaching other applications"""
        if self.backend != X11Backend.XLIB:
            return  # Only works with direct X11 access

        if self.key_grab_active:
            return  # Already grabbed

        with self._display_guard():
            try:
                from Xlib import X
                import Xlib.XK

                # Define keys to grab with their keysyms
                navigation_keys = {
                    # Arrow keys
                    'Up': Xlib.XK.XK_Up,
                    'Down': Xlib.XK.XK_Down,
                    'Left': Xlib.XK.XK_Left,
                    'Right': Xlib.XK.XK_Right,
                    # IJKL keys
                    'i': Xlib.XK.XK_i,
                    'j': Xlib.XK.XK_j,
                    'k': Xlib.XK.XK_k,
                    'l': Xlib.XK.XK_l,
                    # Scroll keys
                    'u': Xlib.XK.XK_u,
                    'm': Xlib.XK.XK_m,
                    'n': Xlib.XK.XK_n,
                    # Exit key
                    'x': Xlib.XK.XK_x,
                    # Click keys
                    'h': Xlib.XK.XK_h,
                    'semicolon': Xlib.XK.XK_semicolon,
                    'space': Xlib.XK.XK_space
                }

                # Build comprehensive modifier combinations to account for CapsLock/NumLock/Super states
                base_mods = [
                    0,
                    X.ControlMask,
                    X.ShiftMask,
                    X.Mod1Mask,  # Alt
                    X.ControlMask | X.ShiftMask,
                    X.ControlMask | X.Mod1Mask,
                    X.ShiftMask | X.Mod1Mask,
                    X.ControlMask | X.ShiftMask | X.Mod1Mask,
                ]

                caps_variants = [0, X.LockMask]         # CapsLock
                numlock_variants = [0, X.Mod2Mask]      # NumLock
                super_variants = [0, X.Mod4Mask]        # Super/Windows

                all_modifier_combinations = set()
                for base in base_mods:
                    for caps in caps_variants:
                        for numl in numlock_variants:
                            for sup in super_variants:
                                all_modifier_combinations.add(base | caps | numl | sup)

                # Suppress BadAccess errors during grabs (some combos may already be grabbed)
                self._push_ignore_badaccess()
                try:
                    for key_name, keysym in navigation_keys.items():
                        try:
                            keycode = self.display.keysym_to_keycode(keysym)
                            if keycode != 0:
                                for modifiers in all_modifier_combinations:
                                    try:
                                        self.root.grab_key(keycode, modifiers, False, X.GrabModeAsync, X.GrabModeAsync)
                                        self.grabbed_keys.add((keycode, modifiers))
                                    except:
                                        pass
                        except:
                            continue
                    self.display.sync()
                finally:
                    self._pop_error_handler()

                self.key_grab_active = True

                # Start X11 event handling thread for grabbed keys
                self._start_x11_event_handling()

                print(f"✓ Grabbed navigation keys for suppression (grabbed {len(self.grabbed_keys)} key combinations)")
            except Exception as e:
                print(f"✗ Could not grab keys: {e}")

    def _ungrab_navigation_keys_only(self):
        """Release grabbed navigation keys while leaving global shortcuts alone."""
        if self.backend != X11Backend.XLIB:
            return

        with self._display_guard():
            try:
                import Xlib.XK

                # Identify Alt key keycodes so we keep their grabs
                alt_keycodes = set()
                for keysym in (Xlib.XK.XK_Alt_L, Xlib.XK.XK_Alt_R):
                    keycode = self.display.keysym_to_keycode(keysym)
                    if keycode != 0:
                        alt_keycodes.add(keycode)

                keys_to_remove = []

                self._push_ignore_badaccess()
                try:
                    for keycode, modifiers in self.grabbed_keys:
                        if keycode not in alt_keycodes:
                            try:
                                self.root.ungrab_key(keycode, modifiers)
                                keys_to_remove.append((keycode, modifiers))
                            except:
                                pass

                    for combo in keys_to_remove:
                        self.grabbed_keys.discard(combo)

                    self.display.sync()
                finally:
                    self._pop_error_handler()

                self.key_grab_active = False
                if keys_to_remove:
                    print("✓ Released navigation key grabs")
            except:
                pass

    def _ungrab_navigation_keys(self):
        """Release grabbed navigation keys"""
        if self.backend != X11Backend.XLIB or not self.grabbed_keys:
            return

        with self._display_guard():
            try:
                # Stop X11 event handling
                self._stop_x11_event_handling()

                # Ungrab all previously grabbed keys
                self._push_ignore_badaccess()
                try:
                    for keycode, modifiers in self.grabbed_keys:
                        try:
                            self.root.ungrab_key(keycode, modifiers)
                        except:
                            pass
                    self.display.sync()
                finally:
                    self._pop_error_handler()

                self.grabbed_keys.clear()
                self.key_grab_active = False
                print("✓ Released navigation key grabs")
            except:
                pass

    def _start_x11_event_handling(self):
        """Start X11 event handling thread for grabbed keys"""
        if not self.x11_events_active:
            self.x11_events_active = True
            self.x11_event_thread = threading.Thread(target=self._x11_event_loop, daemon=True)
            with self._display_guard():
                try:
                    from Xlib import X
                    # Ensure we receive KeyPress/KeyRelease events on the root window
                    self.root.change_attributes(event_mask=X.KeyPressMask | X.KeyReleaseMask)
                    self.display.sync()
                except:
                    pass
            self.x11_event_thread.start()
            print("✓ Started X11 event handling")

    def _stop_x11_event_handling(self):
        """Stop X11 event handling"""
        self.x11_events_active = False
        if self.x11_event_thread:
            self.x11_event_thread = None
        print("✓ Stopped X11 event handling")

    def _x11_event_loop(self):
        """X11 event loop to handle grabbed key events"""
        from Xlib import X

        while self.x11_events_active and self.running:
            event = None
            try:
                with self._display_guard():
                    # Check for pending X11 events (non-blocking)
                    if self.display.pending_events() > 0:
                        event = self.display.next_event()
            except Exception as e:
                if self.debug:
                    print(f"X11 event loop error: {e}")
                break

            if event is not None:
                try:
                    # Handle KeyPress events for grabbed keys
                    if event.type == X.KeyPress:
                        self._handle_grabbed_key_event(event)
                    # Consume KeyRelease events too to prevent them from propagating
                    elif event.type == X.KeyRelease:
                        self._handle_grabbed_key_event(event)
                except Exception as e:
                    if self.debug:
                        print(f"X11 event dispatch error: {e}")

            time.sleep(0.001)  # Small sleep to prevent CPU spinning

    def _handle_grabbed_key_event(self, event):
        """Handle grabbed key events and convert them to mouse actions"""
        try:
            from Xlib import X
            import Xlib.XK

            # Get keycode from event
            keycode = event.detail

            # Convert keycode back to keysym to identify the key
            with self._display_guard():
                keysym = self.display.keycode_to_keysym(keycode, 0)

            # Debug logging suppressed by default
            if self.debug:
                event_type = "KeyPress" if event.type == X.KeyPress else "KeyRelease"
                key_name = Xlib.XK.keysym_to_string(keysym) or f"keysym_{keysym}"
                print(f"DEBUG: Grabbed {event_type} for key: {key_name}")

            if event.type == X.KeyPress and keysym in (Xlib.XK.XK_Alt_L, Xlib.XK.XK_Alt_R):
                if not self.alt_pressed:
                    self.alt_pressed = True
                    self._set_mouse_mode(True)
                return

            if event.type == X.KeyRelease and keysym in (Xlib.XK.XK_Alt_L, Xlib.XK.XK_Alt_R):
                if self.alt_pressed:
                    self.alt_pressed = False
                    self._set_mouse_mode(False)
                return

            if not self.mouse_mode:
                return

            if event.type == X.KeyPress:
                # Space acts as left-button hold (drag). Tap = click.
                if keysym == Xlib.XK.XK_space:
                    if not self.space_click_active:
                        self.space_click_active = True
                        self.press_mouse(1)
                    return

                # Alt+U/M/N => scroll
                if keysym == Xlib.XK.XK_u:
                    self.scroll_keys.add('up')
                    self._start_continuous_movement()
                    return
                if keysym == Xlib.XK.XK_m or keysym == Xlib.XK.XK_n:
                    self.scroll_keys.add('down')
                    self._start_continuous_movement()
                    return

                # Map navigation keys to movement directions
                if keysym == Xlib.XK.XK_Up:
                    self.movement_keys.add(keyboard.Key.up)
                    self._start_continuous_movement()
                    self._move_single_step(keyboard.Key.up)
                elif keysym == Xlib.XK.XK_Down:
                    self.movement_keys.add(keyboard.Key.down)
                    self._start_continuous_movement()
                    self._move_single_step(keyboard.Key.down)
                elif keysym == Xlib.XK.XK_Left:
                    self.movement_keys.add(keyboard.Key.left)
                    self._start_continuous_movement()
                    self._move_single_step(keyboard.Key.left)
                elif keysym == Xlib.XK.XK_Right:
                    self.movement_keys.add(keyboard.Key.right)
                    self._start_continuous_movement()
                    self._move_single_step(keyboard.Key.right)
                elif keysym == Xlib.XK.XK_i:
                    self.movement_keys.add(keyboard.Key.up)
                    self._start_continuous_movement()
                    self._move_single_step(keyboard.Key.up)
                elif keysym == Xlib.XK.XK_j:
                    self.movement_keys.add(keyboard.Key.left)
                    self._start_continuous_movement()
                    self._move_single_step(keyboard.Key.left)
                elif keysym == Xlib.XK.XK_k:
                    self.movement_keys.add(keyboard.Key.down)
                    self._start_continuous_movement()
                    self._move_single_step(keyboard.Key.down)
                elif keysym == Xlib.XK.XK_l:
                    self.movement_keys.add(keyboard.Key.right)
                    self._start_continuous_movement()
                    self._move_single_step(keyboard.Key.right)
                elif keysym == Xlib.XK.XK_space or keysym == Xlib.XK.XK_h:
                    self.click_mouse(1)
                elif keysym == Xlib.XK.XK_semicolon:
                    self.click_mouse(3)

            elif event.type == X.KeyRelease:
                # Handle key releases to stop movement
                if keysym == Xlib.XK.XK_space:
                    if self.space_click_active:
                        self.release_mouse(1)
                        self.space_click_active = False
                    return

                released = False
                if keysym == Xlib.XK.XK_Up:
                    released = self._release_movement_key(keyboard.Key.up)
                elif keysym == Xlib.XK.XK_Down:
                    released = self._release_movement_key(keyboard.Key.down)
                elif keysym == Xlib.XK.XK_Left:
                    released = self._release_movement_key(keyboard.Key.left)
                elif keysym == Xlib.XK.XK_Right:
                    released = self._release_movement_key(keyboard.Key.right)
                elif keysym == Xlib.XK.XK_i:
                    released = self._release_movement_key(keyboard.Key.up)
                elif keysym == Xlib.XK.XK_j:
                    released = self._release_movement_key(keyboard.Key.left)
                elif keysym == Xlib.XK.XK_k:
                    released = self._release_movement_key(keyboard.Key.down)
                elif keysym == Xlib.XK.XK_l:
                    released = self._release_movement_key(keyboard.Key.right)
                elif keysym == Xlib.XK.XK_u:
                    released = self._release_scroll_key('up')
                elif keysym == Xlib.XK.XK_m or keysym == Xlib.XK.XK_n:
                    released = self._release_scroll_key('down')

                if released:
                    return

        except Exception as e:
            print(f"Error handling grabbed key: {e}")

    def _restore_screensaver(self):
        """Restore screensaver settings"""
        try:
            subprocess.run(['xset', 's', 'on'], capture_output=True, timeout=1)
            subprocess.run(['xset', '+dpms'], capture_output=True, timeout=1)
        except:
            pass

    def _wake_cursor(self):
        """Wake up cursor after programmatic movement"""
        # Throttle wake ops to at most once per 250ms
        now = time.time()
        if now - getattr(self, 'last_wake_time', 0) < 0.25:
            return
        self.last_wake_time = now

        if self.backend == X11Backend.XLIB:
            with self._display_guard():
                try:
                    # Method 1: Force cursor redraw at current position
                    from Xlib.ext.xtest import fake_input
                    from Xlib import X
                    coord = self.root.query_pointer()._data
                    current_x, current_y = coord["root_x"], coord["root_y"]
                    fake_input(self.display, X.MotionNotify, x=current_x, y=current_y, root=self.root)
                    # Prefer flush, only occasional sync
                    self.display.flush()
                    
                    # Method 2: Force cursor visibility through root window
                    self.root.change_attributes(cursor=0)  # Reset cursor
                    self.display.flush()
                except:
                    pass
        
        # Avoid extra subprocess calls during frequent movement; these can accumulate
        # and degrade performance over time. Leave heavy wake methods disabled by default.

    def _wake_cursor_light(self):
        """Lightweight cursor wake - no-op by default to avoid subprocess churn"""
        return

    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position using selected backend"""
        if self.backend == X11Backend.XLIB:
            with self._display_guard():
                coord = self.root.query_pointer()._data
                return coord["root_x"], coord["root_y"]
            
        elif self.backend == X11Backend.XDOTOOL:
            try:
                result = subprocess.run(['xdotool', 'getmouselocation'], 
                                      capture_output=True, text=True, check=True)
                # Parse: "x:123 y:456 screen:0 window:789"
                parts = result.stdout.strip().split()
                x = int(parts[0].split(':')[1])
                y = int(parts[1].split(':')[1])
                return x, y
            except:
                return 0, 0
                
        elif self.backend == X11Backend.XINPUT:
            # xinput doesn't directly provide cursor position
            # Fall back to xdotool for position queries
            return self.get_mouse_position_fallback()
        
        return 0, 0

    def get_mouse_position_fallback(self) -> Tuple[int, int]:
        """Fallback method using xdotool"""
        try:
            result = subprocess.run(['xdotool', 'getmouselocation'], 
                                  capture_output=True, text=True, check=True)
            parts = result.stdout.strip().split()
            x = int(parts[0].split(':')[1])
            y = int(parts[1].split(':')[1])
            return x, y
        except:
            return 0, 0

    def move_mouse_to(self, x: int, y: int):
        """Move mouse to absolute position"""
        # Clamp target within screen bounds when known
        x, y = self._clamp_position(x, y)
        if self.backend == X11Backend.XLIB:
            from Xlib.ext.xtest import fake_input
            from Xlib import X
            with self._display_guard():
                fake_input(self.display, X.MotionNotify, x=x, y=y)
                # Throttle expensive syncs; avoid draining event queue here
                self.movement_counter += 1
                if self.movement_counter % 25 == 0:
                    self.display.sync()
                else:
                    self.display.flush()
            
        elif self.backend == X11Backend.XDOTOOL:
            subprocess.run(['xdotool', 'mousemove', str(x), str(y)], 
                         capture_output=True)
            
        elif self.backend == X11Backend.XINPUT:
            # Get screen dimensions for xinput (needs absolute coordinates)
            try:
                # Use xrandr to get screen size
                result = subprocess.run(['xrandr'], capture_output=True, text=True)
                # Parse primary display resolution
                for line in result.stdout.split('\n'):
                    if 'primary' in line and 'x' in line:
                        res = line.split()[3].split('+')[0]  # Get "1920x1080" part
                        width, height = map(int, res.split('x'))
                        break
                else:
                    width, height = 1920, 1080  # Default fallback
                    
                # Convert to xinput coordinates (0-65535 range)
                xinput_x = int((x / width) * 65535)
                xinput_y = int((y / height) * 65535)
                
                subprocess.run(['xinput', 'set-prop', 'Virtual core pointer', 
                              'Coordinate Transformation Matrix', 
                              '1', '0', str(xinput_x/65535), '0', '1', str(xinput_y/65535), '0', '0', '1'], 
                             capture_output=True)
            except:
                # Fallback to xdotool
                subprocess.run(['xdotool', 'mousemove', str(x), str(y)], 
                             capture_output=True)
        
        # Wake cursor after movement to ensure visibility
        self._wake_cursor()

    def move_mouse_relative(self, dx: int, dy: int):
        """Move mouse by relative offset with optional smooth animation"""
        if not self.smooth_movement:
            # Direct movement (original behavior)
            if self.backend == X11Backend.XLIB:
                # Use cached position; clamp to screen to prevent overshoot beyond edges
                from Xlib.ext.xtest import fake_input
                from Xlib import X

                if self.last_position_update == 0:
                    # Initialize from actual OS position on first move
                    self.cached_mouse_x, self.cached_mouse_y = self.get_mouse_position()
                    self.last_position_update = time.time()

                target_x = self.cached_mouse_x + dx
                target_y = self.cached_mouse_y + dy
                target_x, target_y = self._clamp_position(target_x, target_y)

                # Update cached to clamped target to stay in sync with actual cursor
                self.cached_mouse_x = target_x
                self.cached_mouse_y = target_y

                with self._display_guard():
                    fake_input(self.display, X.MotionNotify, x=target_x, y=target_y)

                    # Less frequent sync to prevent server-side buildup
                    self.movement_counter += 1
                    if self.movement_counter % 20 == 0:
                        self.display.sync()
                    else:
                        self.display.flush()
            elif self.backend == X11Backend.XDOTOOL:
                # Use Popen with proper cleanup to prevent subprocess buildup
                proc = subprocess.Popen(['xdotool', 'mousemove_relative', '--', str(dx), str(dy)], 
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc.wait()
                # Only wake cursor every 30 movements (~0.5 seconds at 125fps) to avoid buildup
                self.movement_counter += 1
                if self.movement_counter % 30 == 0:
                    self._wake_cursor_light()
            elif self.backend == X11Backend.XINPUT:
                # Use Popen with proper cleanup to prevent subprocess buildup
                proc = subprocess.Popen(['xdotool', 'mousemove_relative', '--', str(dx), str(dy)], 
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc.wait()
                # Only wake cursor every 30 movements to avoid buildup
                self.movement_counter += 1
                if self.movement_counter % 30 == 0:
                    self._wake_cursor_light()
        else:
            # Smooth animated movement
            # Use cached position to avoid repeated queries during animation
            if self.last_position_update == 0:
                self.cached_mouse_x, self.cached_mouse_y = self.get_mouse_position()
                self.last_position_update = time.time()
            current_x, current_y = self.cached_mouse_x, self.cached_mouse_y
            target_x = current_x + dx
            target_y = current_y + dy
            target_x, target_y = self._clamp_position(target_x, target_y)
            self._animate_to_position(current_x, current_y, target_x, target_y)
            # Update cached position to the final clamped target so subsequent moves accumulate
            self.cached_mouse_x = target_x
            self.cached_mouse_y = target_y
            self.last_position_update = time.time()
            self.last_movement_time = self.last_position_update

    def _clamp_position(self, x: int, y: int) -> Tuple[int, int]:
        """Clamp coordinates to the screen bounds when known."""
        # Lazily populate dimensions for Xlib if unknown
        if (self.screen_width == 0 or self.screen_height == 0) and self.backend == X11Backend.XLIB:
            try:
                self.screen_width = int(self.screen.width_in_pixels)
                self.screen_height = int(self.screen.height_in_pixels)
            except:
                pass

        # Ensure non-negative at minimum
        clamped_x = x if x >= 0 else 0
        clamped_y = y if y >= 0 else 0

        # If we know width/height, clamp upper bounds too
        if self.screen_width > 0 and self.screen_height > 0:
            if clamped_x >= self.screen_width:
                clamped_x = self.screen_width - 1
            if clamped_y >= self.screen_height:
                clamped_y = self.screen_height - 1

        return clamped_x, clamped_y

    def _sync_cached_position_from_os(self):
        """Refresh internal cached cursor coordinates from actual OS cursor."""
        x, y = self.get_mouse_position()
        self.cached_mouse_x = x
        self.cached_mouse_y = y
        self.last_position_update = time.time()

    def _animate_to_position(self, start_x: int, start_y: int, end_x: int, end_y: int):
        """Animate cursor movement between two positions"""
        for i in range(1, self.animation_steps + 1):
            # Linear interpolation
            progress = i / self.animation_steps
            current_x = int(start_x + (end_x - start_x) * progress)
            current_y = int(start_y + (end_y - start_y) * progress)
            
            # Move to interpolated position
            self._move_mouse_direct(current_x, current_y)
            
            # Small delay for smooth animation
            if i < self.animation_steps:  # Don't delay on final step
                time.sleep(self.animation_delay)
        
        # Final wake cursor call
        self._wake_cursor()

    def _move_mouse_direct(self, x: int, y: int):
        """Direct mouse movement without wake cursor calls (for animation)"""
        if self.backend == X11Backend.XLIB:
            from Xlib.ext.xtest import fake_input
            from Xlib import X
            # Clamp to screen to avoid overshoot
            cx, cy = self._clamp_position(x, y)
            with self._display_guard():
                fake_input(self.display, X.MotionNotify, x=cx, y=cy)
                # Prefer flush; sync occasionally to avoid server lag
                self.animation_move_counter += 1
                if self.animation_move_counter % 20 == 0:
                    self.display.sync()
                else:
                    self.display.flush()
            
        elif self.backend == X11Backend.XDOTOOL:
            subprocess.run(['xdotool', 'mousemove', str(x), str(y)], 
                         capture_output=True)
            
        elif self.backend == X11Backend.XINPUT:
            # Use xdotool fallback for xinput
            subprocess.run(['xdotool', 'mousemove', str(x), str(y)], 
                         capture_output=True)

    def click_mouse(self, button: int = 1):
        """Click mouse button (1=left, 2=middle, 3=right)"""
        if self.backend == X11Backend.XLIB:
            from Xlib.ext.xtest import fake_input
            from Xlib import X
            with self._display_guard():
                fake_input(self.display, X.ButtonPress, button)
                self.display.sync()
                fake_input(self.display, X.ButtonRelease, button)
                self.display.sync()
            
        elif self.backend == X11Backend.XDOTOOL:
            subprocess.run(['xdotool', 'click', str(button)], capture_output=True)
            
        elif self.backend == X11Backend.XINPUT:
            # xinput doesn't have direct click, use xdotool fallback
            subprocess.run(['xdotool', 'click', str(button)], capture_output=True)

    def scroll_vertical(self, clicks: int = 1):
        """Scroll vertically; positive=up, negative=down."""
        if clicks == 0:
            return
        repeat = abs(int(clicks))
        # Prefer ydotool on Wayland if available for compatibility with native apps
        if self.is_wayland and self.ydotool_available:
            button = '4' if clicks > 0 else '5'
            try:
                subprocess.run(['ydotool', 'click', '--repeat', str(repeat), button], capture_output=True)
                return
            except Exception as e:
                if self.debug:
                    print(f"ydotool scroll failed: {e}. Falling back to X methods.")
        if self.backend == X11Backend.XLIB:
            from Xlib.ext.xtest import fake_input
            from Xlib import X
            button = 4 if clicks > 0 else 5
            with self._display_guard():
                for _ in range(repeat):
                    fake_input(self.display, X.ButtonPress, button)
                    self.display.flush()
                    fake_input(self.display, X.ButtonRelease, button)
                    self.display.flush()
                # Ensure events are delivered promptly
                try:
                    self.display.sync()
                except:
                    pass
        else:
            button = '4' if clicks > 0 else '5'
            try:
                subprocess.run(['xdotool', 'click', '--repeat', str(repeat), '--delay', '0', button], capture_output=True)
            except:
                for _ in range(repeat):
                    subprocess.run(['xdotool', 'click', button], capture_output=True)

    def press_mouse(self, button: int = 1):
        """Press mouse button down (for drag/select)."""
        if self.backend == X11Backend.XLIB:
            from Xlib.ext.xtest import fake_input
            from Xlib import X
            with self._display_guard():
                fake_input(self.display, X.ButtonPress, button)
                self.display.sync()
        else:
            subprocess.run(['xdotool', 'mousedown', str(button)], capture_output=True)

    def release_mouse(self, button: int = 1):
        """Release mouse button (for drag/select)."""
        if self.backend == X11Backend.XLIB:
            from Xlib.ext.xtest import fake_input
            from Xlib import X
            with self._display_guard():
                fake_input(self.display, X.ButtonRelease, button)
                self.display.sync()
        else:
            subprocess.run(['xdotool', 'mouseup', str(button)], capture_output=True)

    def on_key_press(self, key):
        """Handle key press events"""
        suppress = False
        handle_locally = not self.key_grab_active
        try:
            if key == keyboard.Key.esc:
                # Ignore ESC to avoid accidental app exit (e.g., GNOME overview sends ESC)
                return None
            
            elif key == keyboard.Key.space and self.mouse_mode:
                # Space acts as left click/hold
                if not self.space_click_active:
                    self.space_click_active = True
                    self.press_mouse(1)
                suppress = handle_locally
                
            elif key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
                self.ctrl_pressed = True
            
            elif key in [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r]:
                self.shift_pressed = True

            elif key in [keyboard.Key.alt_l, keyboard.Key.alt_r]:
                if not self.alt_pressed:
                    self.alt_pressed = True
                    self._set_mouse_mode(True)
                # Allow Alt to propagate so desktop shortcuts (Alt+Tab, etc.) keep working
                suppress = False

            elif key in [keyboard.Key.up, keyboard.Key.down, 
                        keyboard.Key.left, keyboard.Key.right]:
                if self.mouse_mode and handle_locally:
                    # Start continuous movement for arrow keys
                    if key not in self.movement_keys:
                        self.movement_keys.add(key)
                        self._start_continuous_movement()
                    self._move_single_step(key)
                    suppress = True
                
            elif hasattr(key, 'char') and key.char:
                raw_char = key.char
                char = raw_char.lower()
                # New explicit exit shortcut
                if char == 'q' and self.ctrl_pressed:
                    print("\nExiting...")
                    self.running = False
                    return False
                if self.mouse_mode and handle_locally:
                    # U/M => scroll
                    if char == 'u':
                        self.scroll_keys.add('up')
                        self._start_continuous_movement()
                        suppress = True
                        return None
                    if char == 'm' or char == 'n':
                        self.scroll_keys.add('down')
                        self._start_continuous_movement()
                        suppress = True
                        return None
                    # Handle IJKL navigation - continuous movement
                    movement_map = {
                        'i': keyboard.Key.up,    # Up
                        'j': keyboard.Key.left,  # Left  
                        'k': keyboard.Key.down,  # Down
                        'l': keyboard.Key.right  # Right
                    }
                    
                    if char in movement_map:
                        key_equivalent = movement_map[char]
                        if key_equivalent not in self.movement_keys:
                            self.movement_keys.add(key_equivalent)
                            self._start_continuous_movement()
                        self._move_single_step(key_equivalent)
                        suppress = True
                    elif char == 'h':  # Left click
                        self.click_mouse(1)
                        suppress = True
                    elif char == ';':  # Right click
                        self.click_mouse(3)
                        suppress = True

        except AttributeError:
            pass
        finally:
            if suppress:
                self._suppress_current_event()

        return None

    def on_key_release(self, key):
        """Handle key release events"""
        suppress = False
        handle_locally = not self.key_grab_active
        try:
            if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r]:
                self.ctrl_pressed = False
            elif key == keyboard.Key.space:
                if self.space_click_active:
                    self.release_mouse(1)
                    self.space_click_active = False
                suppress = handle_locally
                
            elif key in [keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r]:
                self.shift_pressed = False
            elif key in [keyboard.Key.alt_l, keyboard.Key.alt_r]:
                if self.alt_pressed:
                    self.alt_pressed = False
                    self._set_mouse_mode(False)
                suppress = False
                
            elif key in [keyboard.Key.up, keyboard.Key.down, 
                        keyboard.Key.left, keyboard.Key.right]:
                removed = self._release_movement_key(key)
                if removed and (self.mouse_mode or handle_locally):
                    suppress = handle_locally
                        
            elif hasattr(key, 'char') and key.char:
                char = key.char.lower()
                # Handle IJKL key releases
                movement_map = {
                    'i': keyboard.Key.up,
                    'j': keyboard.Key.left,
                    'k': keyboard.Key.down,
                    'l': keyboard.Key.right
                }

                if char in movement_map:
                    removed = self._release_movement_key(movement_map[char])
                    if removed and (self.mouse_mode or handle_locally):
                        suppress = handle_locally
                elif char == 'u':
                    removed = self._release_scroll_key('up')
                    if removed and (self.mouse_mode or handle_locally):
                        suppress = handle_locally
                elif char == 'm' or char == 'n':
                    removed = self._release_scroll_key('down')
                    if removed and (self.mouse_mode or handle_locally):
                        suppress = handle_locally

        except AttributeError:
            pass
        finally:
            if suppress:
                self._suppress_current_event()

        return None

    def _move_single_step(self, direction_key):
        """Move mouse by a single step in the given direction"""
        if not self.mouse_mode:
            print("Mouse control is inactive - hold Alt to engage")
            return
            
        # Determine movement distance
        if self.ctrl_pressed:
            move_distance = self.ctrl_leap_distance
            if self.debug:
                print(f"Moving {move_distance}px (Ctrl held)")
        else:
            move_distance = self.move_speed
            if self.debug:
                print(f"Moving {move_distance}px")
        
        # Calculate movement direction
        dx = dy = 0
        if direction_key == keyboard.Key.up:
            dy = -move_distance
        elif direction_key == keyboard.Key.down:
            dy = move_distance
        elif direction_key == keyboard.Key.left:
            dx = -move_distance
        elif direction_key == keyboard.Key.right:
            dx = move_distance
        
        # Perform movement
        if dx != 0 or dy != 0:
            if self.debug:
                print(f"Moving cursor by dx={dx}, dy={dy}")
            self.move_mouse_relative(dx, dy)

    def _start_continuous_movement(self):
        """Start continuous movement thread if not already running"""
        if not self.movement_active and self.movement_keys:
            # Sync cached position from actual OS cursor on movement start
            self._sync_cached_position_from_os()
            self.movement_active = True
            self.movement_thread = threading.Thread(target=self._continuous_movement_loop, daemon=True)
            self.movement_thread.start()
            if self.debug:
                print("Started continuous movement")

    def _stop_continuous_movement(self):
        """Stop continuous movement"""
        self.movement_active = False
        if self.movement_thread:
            self.movement_thread = None
        if self.debug:
            print("Stopped continuous movement")

    def _continuous_movement_loop(self):
        """Continuous movement loop that runs in a separate thread"""
        while self.movement_active and self.running:
            if not self.mouse_mode:
                time.sleep(self.movement_interval)
                continue
                
            if self.movement_keys or self.scroll_keys:
                # If Shift is held, convert vertical movement keys to scroll
                if self.scroll_keys:
                    # Scroll according to currently held U/M keys
                    direction = 0
                    if 'up' in self.scroll_keys:
                        direction += 1
                    if 'down' in self.scroll_keys:
                        direction -= 1
                    if direction != 0:
                        self.scroll_vertical(self.scroll_step * direction)
                        self.last_movement_time = time.time()
                        time.sleep(self.movement_interval)
                        continue

                # Calculate combined movement from all pressed keys
                dx = dy = 0
                
                # Determine movement distance
                if self.ctrl_pressed:
                    move_distance = self.ctrl_leap_distance
                else:
                    move_distance = self.move_speed
                
                # Combine movements from all pressed keys
                for key in self.movement_keys:
                    if key == keyboard.Key.up:
                        dy -= move_distance
                    elif key == keyboard.Key.down:
                        dy += move_distance
                    elif key == keyboard.Key.left:
                        dx -= move_distance
                    elif key == keyboard.Key.right:
                        dx += move_distance
                
                # Apply diagonal acceleration if moving diagonally
                if dx != 0 and dy != 0:
                    dx = int(dx * self.acceleration)
                    dy = int(dy * self.acceleration)
                
                # Perform movement if there's any
                if dx != 0 or dy != 0:
                    self.move_mouse_relative(dx, dy)
                
                # Periodic cleanup to prevent memory buildup (lighter weight)
                current_time = time.time()
                if current_time - self.last_gc_time > 10.0:  # Less frequent
                    gc.collect()
                    if self.backend == X11Backend.XLIB:
                        try:
                            with self._display_guard():
                                self.display.flush()
                        except:
                            pass
                    self.last_gc_time = current_time
                    if self.movement_counter > 100000:
                        self.movement_counter = 0
            
            # Track last movement time for idle-based maintenance
            self.last_movement_time = time.time()
            time.sleep(self.movement_interval)

    def run(self):
        """Main application loop"""
        # Set up keyboard listener
        self.listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release,
            suppress=False
        )
        
        self.listener.start()
        
        try:
            while self.running:
                current_time = time.time()
                
                # Periodic cursor refresh only when idle for > 2s to avoid subprocess churn
                if (current_time - self.last_cursor_refresh > 5.0 and
                    current_time - self.last_movement_time > 2.0):
                    self._restore_cursor_visibility()
                    self.last_cursor_refresh = current_time
                
                time.sleep(0.01)  # 100 FPS - just for keeping the loop alive
                
        except KeyboardInterrupt:
            print("\nForce exit (Ctrl+C)")
        finally:
            # Stop continuous movement
            self._stop_continuous_movement()
            if self.listener:
                self.listener.stop()
                self.listener = None
            # Ungrab keys on exit (this also stops X11 event handling)
            self._ungrab_navigation_keys()
            # Restore cursor visibility and screensaver on exit
            self._restore_cursor_visibility()
            self._restore_screensaver()
            print("X11 Mouse Controller stopped.")

def main():
    """Main entry point with backend selection"""
    def _handle_signal(signum, frame):
        raise KeyboardInterrupt()

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except Exception:
        pass
    # Default backend from config
    default_backend_name = getattr(config, 'DEFAULT_BACKEND', 'xlib').lower()
    backend_map = {
        'xlib': X11Backend.XLIB,
        'xdotool': X11Backend.XDOTOOL, 
        'xinput': X11Backend.XINPUT
    }
    backend = backend_map.get(default_backend_name, X11Backend.XLIB)
    
    # Allow backend selection via command line
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in backend_map:
            backend = backend_map[sys.argv[1].lower()]
        else:
            print(f"Usage: {sys.argv[0]} [xlib|xdotool|xinput]")
            print("Available backends:")
            print("  xlib    - Direct python3-xlib (fastest, default)")
            print("  xdotool - Command-line xdotool (most compatible)")
            print("  xinput  - Low-level device control")
            sys.exit(1)
    
    # Create and run controller
    controller = X11MouseController(backend=backend)
    controller.run()

if __name__ == "__main__":
    main()
