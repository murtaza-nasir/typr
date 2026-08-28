"""Global hotkey management using evdev for direct keyboard access."""

import atexit
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from typr.config import HotkeyConfig
from typr.core.text_injector import INJECTOR_DEVICE_NAME
from typr.utils.logger import logger

try:
    import evdev
    from evdev import InputDevice, categorize, ecodes

    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False
    logger.warning("evdev not available - install with: pip install evdev")


# Key code mappings
KEY_NAMES = {
    "space": ecodes.KEY_SPACE if EVDEV_AVAILABLE else 57,
    "enter": ecodes.KEY_ENTER if EVDEV_AVAILABLE else 28,
    "return": ecodes.KEY_ENTER if EVDEV_AVAILABLE else 28,
    "escape": ecodes.KEY_ESC if EVDEV_AVAILABLE else 1,
    "tab": ecodes.KEY_TAB if EVDEV_AVAILABLE else 15,
    "backspace": ecodes.KEY_BACKSPACE if EVDEV_AVAILABLE else 14,
    "f1": ecodes.KEY_F1 if EVDEV_AVAILABLE else 59,
    "f2": ecodes.KEY_F2 if EVDEV_AVAILABLE else 60,
    "f3": ecodes.KEY_F3 if EVDEV_AVAILABLE else 61,
    "f4": ecodes.KEY_F4 if EVDEV_AVAILABLE else 62,
    "f5": ecodes.KEY_F5 if EVDEV_AVAILABLE else 63,
    "f6": ecodes.KEY_F6 if EVDEV_AVAILABLE else 64,
    "f7": ecodes.KEY_F7 if EVDEV_AVAILABLE else 65,
    "f8": ecodes.KEY_F8 if EVDEV_AVAILABLE else 66,
    "f9": ecodes.KEY_F9 if EVDEV_AVAILABLE else 67,
    "f10": ecodes.KEY_F10 if EVDEV_AVAILABLE else 68,
    "f11": ecodes.KEY_F11 if EVDEV_AVAILABLE else 87,
    "f12": ecodes.KEY_F12 if EVDEV_AVAILABLE else 88,
}

# Modifier key codes
if EVDEV_AVAILABLE:
    MODIFIER_KEYS = {
        ecodes.KEY_LEFTMETA: "meta",
        ecodes.KEY_RIGHTMETA: "meta",
        ecodes.KEY_LEFTSHIFT: "shift",
        ecodes.KEY_RIGHTSHIFT: "shift",
        ecodes.KEY_LEFTCTRL: "ctrl",
        ecodes.KEY_RIGHTCTRL: "ctrl",
        ecodes.KEY_LEFTALT: "alt",
        ecodes.KEY_RIGHTALT: "alt",
    }
else:
    MODIFIER_KEYS = {}


class HotkeyManager(QObject):
    """Manages global hotkeys using evdev for direct keyboard access."""

    # Signals
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    copy_last_requested = pyqtSignal()
    hotkey_error = pyqtSignal(str)
    # Emitted with a combo string (e.g. "Ctrl+Alt+D") while in capture mode,
    # or an empty string if the capture was cancelled.
    hotkey_captured = pyqtSignal(str)

    def __init__(self, config: Optional[HotkeyConfig] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config = config or HotkeyConfig()
        self._devices: list = []
        self._grabbed: list = []
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._registered = False

        # All physically-held key codes, so we can tell when the keyboard is
        # idle. Used to defer an armed grab until the hotkey is fully released.
        self._pressed_keys: set[int] = set()
        self._grab_armed = False

        # Safety net: if the process exits while keyboards are grabbed,
        # release them so the user isn't locked out. (A hard crash closes
        # the fds and the kernel auto-releases the grab anyway, but this
        # covers normal/abnormal interpreter shutdown.)
        atexit.register(self.ungrab_all)

        # Current modifier state
        self._modifiers: set[str] = set()

        # Parse the configured hotkeys
        self._target_modifiers: set[str] = set()
        self._target_key: int = 0
        self._key_pressed = False

        # Copy-last-output hotkey (discrete press, not push-to-talk)
        self._copy_modifiers: set[str] = set()
        self._copy_key: int = 0
        self._copy_pressed = False

        # Capture mode: while active, key events are used to record a new
        # combo for the settings dialog instead of triggering any action.
        self._capturing = False

        self._reparse_hotkeys()

    def _reparse_hotkeys(self) -> None:
        """(Re)parse all configured hotkeys from the current config."""
        self._target_modifiers, self._target_key = self._parse_combo(self.config.push_to_talk)
        logger.info(
            f"Parsed push-to-talk: modifiers={self._target_modifiers}, key={self._target_key}"
        )
        self._copy_modifiers, self._copy_key = self._parse_combo(self.config.copy_last)
        logger.info(
            f"Parsed copy-last: modifiers={self._copy_modifiers}, key={self._copy_key}"
        )

    @staticmethod
    def _parse_combo(hotkey_str: str) -> tuple[set[str], int]:
        """Parse a hotkey string like 'Meta+Shift+Space' into (modifiers, key)."""
        modifiers: set[str] = set()
        key = 0

        if not hotkey_str:
            return modifiers, key

        for part in hotkey_str.lower().replace(" ", "").split("+"):
            if part in ("meta", "super", "win"):
                modifiers.add("meta")
            elif part in ("shift",):
                modifiers.add("shift")
            elif part in ("ctrl", "control"):
                modifiers.add("ctrl")
            elif part in ("alt",):
                modifiers.add("alt")
            elif part in KEY_NAMES:
                key = KEY_NAMES[part]
            elif EVDEV_AVAILABLE and getattr(ecodes, f"KEY_{part.upper()}", 0):
                # Letters, digits and any other evdev key name (KEY_COMMA, ...)
                key = getattr(ecodes, f"KEY_{part.upper()}")
            else:
                logger.warning(f"Unknown key in hotkey: {part}")

        return modifiers, key

    @staticmethod
    def _format_combo(modifiers: set[str], key_code: int) -> str:
        """Render (modifiers, key code) back into a string like 'Ctrl+Alt+D'."""
        parts = [
            label
            for name, label in (
                ("ctrl", "Ctrl"),
                ("alt", "Alt"),
                ("shift", "Shift"),
                ("meta", "Meta"),
            )
            if name in modifiers
        ]

        key_name = ""
        for name, code in KEY_NAMES.items():
            if code == key_code:
                key_name = name.capitalize()
                break
        if not key_name and EVDEV_AVAILABLE:
            evdev_name = ecodes.KEY.get(key_code)
            if isinstance(evdev_name, list):
                evdev_name = evdev_name[0]
            if evdev_name:
                key_name = evdev_name[len("KEY_"):].capitalize()

        if not key_name:
            return ""

        parts.append(key_name)
        return "+".join(parts)

    def initialize(self) -> bool:
        """Initialize evdev keyboard listeners.

        Returns:
            True if initialization was successful.
        """
        if not EVDEV_AVAILABLE:
            self.hotkey_error.emit("evdev not installed. Run: pip install evdev")
            return False

        try:
            # Find all keyboard devices
            self._devices = []
            input_dir = Path("/dev/input")

            for event_file in sorted(input_dir.glob("event*")):
                try:
                    device = InputDevice(str(event_file))

                    # Skip our own virtual keyboard so we don't read back
                    # injected events or grab the device we type through.
                    if device.name == INJECTOR_DEVICE_NAME:
                        device.close()
                        continue

                    capabilities = device.capabilities()

                    # Check if device has keyboard keys (EV_KEY with typical keyboard codes)
                    if ecodes.EV_KEY in capabilities:
                        keys = capabilities[ecodes.EV_KEY]
                        # Check for common keyboard keys
                        if ecodes.KEY_SPACE in keys or ecodes.KEY_A in keys:
                            self._devices.append(device)
                            logger.debug(f"Found keyboard: {device.name} ({device.path})")
                except PermissionError:
                    logger.debug(f"No permission for {event_file}")
                except Exception as e:
                    logger.debug(f"Error opening {event_file}: {e}")

            if not self._devices:
                error_msg = "No keyboard devices found. Make sure you're in the 'input' group."
                self.hotkey_error.emit(error_msg)
                return False

            logger.info(f"Found {len(self._devices)} keyboard device(s)")

            # Start listener thread
            self._running = True
            self._thread = threading.Thread(target=self._event_loop, daemon=True)
            self._thread.start()

            self._registered = True
            logger.info(f"Hotkey manager initialized: {self.config.push_to_talk}")
            return True

        except Exception as e:
            error_msg = f"Failed to initialize hotkeys: {e}"
            logger.error(error_msg)
            self.hotkey_error.emit(error_msg)
            return False

    def _event_loop(self) -> None:
        """Main event loop reading from all keyboard devices."""
        import select
        import time

        devices_by_fd = {dev.fd: dev for dev in self._devices}

        while self._running:
            try:
                # Wait for events with timeout
                r, _, _ = select.select(devices_by_fd.keys(), [], [], 0.1)

                for fd in r:
                    device = devices_by_fd.get(fd)
                    if not device:
                        continue

                    try:
                        for event in device.read():
                            if event.type == ecodes.EV_KEY:
                                self._handle_key_event(event)
                    except BlockingIOError:
                        pass
                    except OSError as e:
                        # Device disconnected - remove from tracking
                        logger.warning(f"Device {device.path} disconnected: {e}")
                        del devices_by_fd[fd]
                        try:
                            device.close()
                        except Exception:
                            pass
                    except Exception as e:
                        logger.debug(f"Error reading from {device.path}: {e}")

            except OSError as e:
                # select() failed - likely bad file descriptor
                logger.error(f"Event loop select error: {e}")
                # Remove all invalid fds
                valid_fds = {}
                for fd, dev in devices_by_fd.items():
                    try:
                        select.select([fd], [], [], 0)  # Quick test
                        valid_fds[fd] = dev
                    except Exception:
                        logger.warning(f"Removing invalid device: {dev.path}")
                        try:
                            dev.close()
                        except Exception:
                            pass
                devices_by_fd = valid_fds
                time.sleep(0.1)  # Prevent tight loop even if all devices gone

            except Exception as e:
                if self._running:
                    logger.error(f"Event loop error: {e}")
                    time.sleep(0.1)  # Prevent tight loop on unexpected errors

    def _handle_key_event(self, event) -> None:
        """Handle a key press/release event."""
        key_code = event.code
        key_state = event.value  # 0=release, 1=press, 2=repeat

        # Track every physically-held key so we know when the keyboard is
        # idle. A grab armed while the hotkey is still being released is
        # deferred until here, the moment the last key comes up — by then the
        # compositor has already seen those release events, so grabbing can't
        # strand them (which is what previously left modifiers stuck down).
        if key_state in (1, 2):
            self._pressed_keys.add(key_code)
        elif key_state == 0:
            self._pressed_keys.discard(key_code)
            if self._grab_armed and not self._pressed_keys:
                self._do_armed_grab()

        # In capture mode the keyboard is only used to record a new combo.
        if self._capturing:
            self._handle_capture_event(key_code, key_state)
            return

        # Update modifier state
        if key_code in MODIFIER_KEYS:
            modifier = MODIFIER_KEYS[key_code]
            if key_state == 1:  # Press
                self._modifiers.add(modifier)
            elif key_state == 0:  # Release
                self._modifiers.discard(modifier)

                # If we were recording and a modifier was released, stop
                if self._key_pressed and modifier in self._target_modifiers:
                    self._key_pressed = False
                    logger.debug("Hotkey released (modifier)")
                    self.recording_stopped.emit()
            return

        # Check for target key
        if key_code == self._target_key:
            if key_state == 1:  # Press
                # Check if all required modifiers are held
                if self._target_modifiers <= self._modifiers:
                    if not self._key_pressed:
                        self._key_pressed = True
                        logger.debug("Hotkey pressed")
                        self.recording_started.emit()

            elif key_state == 0:  # Release
                if self._key_pressed:
                    self._key_pressed = False
                    logger.debug("Hotkey released")
                    self.recording_stopped.emit()

        # Check for the copy-last-output key (discrete press trigger)
        if self._copy_key and key_code == self._copy_key:
            if key_state == 1:  # Press
                if self._copy_modifiers <= self._modifiers and not self._copy_pressed:
                    self._copy_pressed = True
                    logger.debug("Copy-last hotkey pressed")
                    self.copy_last_requested.emit()
            elif key_state == 0:  # Release
                self._copy_pressed = False

    def _handle_capture_event(self, key_code: int, key_state: int) -> None:
        """Build a combo from raw key events while capture mode is active."""
        if key_code in MODIFIER_KEYS:
            # Track modifiers in both directions so a released modifier does
            # not end up in the captured combo.
            if key_state == 1:
                self._modifiers.add(MODIFIER_KEYS[key_code])
            elif key_state == 0:
                self._modifiers.discard(MODIFIER_KEYS[key_code])
            return

        if key_state != 1:  # Otherwise only act on presses
            return

        if key_code == KEY_NAMES["escape"] and not self._modifiers:
            # Bare Escape cancels the capture.
            self.stop_capture()
            self.hotkey_captured.emit("")
            return

        combo = self._format_combo(self._modifiers, key_code)
        self.stop_capture()
        if combo:
            self.hotkey_captured.emit(combo)
        else:
            logger.warning(f"Unrecognized key code during capture: {key_code}")
            self.hotkey_captured.emit("")

    def start_capture(self) -> None:
        """Listen for the next key combo instead of triggering hotkeys.

        The settings dialog uses this so a new shortcut can be recorded from
        the same evdev stream the hotkeys themselves run on - Qt never sees
        these presses reliably, and without this the old push-to-talk combo
        would just start recording while you tried to rebind it.
        """
        self._capturing = True
        # Any in-flight hotkey state is meaningless once we switch modes.
        self._key_pressed = False
        self._copy_pressed = False
        self._modifiers.clear()

    def stop_capture(self) -> None:
        """Leave capture mode and resume normal hotkey handling."""
        self._capturing = False
        self._modifiers.clear()

    def is_capturing(self) -> bool:
        """Whether capture mode is currently active."""
        return self._capturing

    def update_shortcut(self, shortcut: str) -> bool:
        """Update the push-to-talk shortcut."""
        self.config.push_to_talk = shortcut
        self._reparse_hotkeys()
        return True

    def update_hotkeys(self, config: HotkeyConfig) -> None:
        """Adopt a new hotkey config and reparse every combo."""
        self.config = config
        self._reparse_hotkeys()

    def is_registered(self) -> bool:
        """Check if hotkeys are registered."""
        return self._registered

    def arm_grab(self) -> None:
        """Grab the keyboard as soon as it is physically idle.

        Deferring until no keys are held is what makes grabbing safe with a
        modifier-combo push-to-talk hotkey: grabbing mid-release would swallow
        the hotkey's own Ctrl/Alt release events and leave them stuck down.
        If the keyboard is already idle, grabs immediately; otherwise the grab
        happens in _handle_key_event when the last key is released.
        """
        self._grab_armed = True
        if not self._pressed_keys:
            self._do_armed_grab()

    def _do_armed_grab(self) -> None:
        """Perform a previously armed grab and disarm."""
        self._grab_armed = False
        if not self._grabbed:
            self.grab_all()

    def grab_all(self) -> None:
        """Take exclusive access to all physical keyboards.

        While grabbed, physical key events do not reach the compositor, so
        text injected (and anything the user presses during the wait) cannot
        corrupt the output. Must be paired with ungrab_all(). Safe to call
        repeatedly; already-grabbed devices are skipped.

        Prefer arm_grab() when the user may still be holding the hotkey;
        calling this directly while a modifier is held can strand its release.
        """
        for device in self._devices:
            if device in self._grabbed:
                continue
            try:
                device.grab()
                self._grabbed.append(device)
            except Exception as e:
                logger.warning(f"Failed to grab {device.path}: {e}")

    def ungrab_all(self) -> None:
        """Release exclusive access to any grabbed keyboards and disarm.

        Safe to call when nothing is grabbed or armed (used as an idempotent
        safety net on cleanup, watchdog timeout, and interpreter exit).
        """
        self._grab_armed = False
        if not self._grabbed:
            return
        for device in self._grabbed:
            try:
                device.ungrab()
            except Exception as e:
                logger.debug(f"Failed to ungrab {device.path}: {e}")
        self._grabbed = []

    def cleanup(self) -> None:
        """Clean up resources."""
        self._running = False

        self.ungrab_all()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        for device in self._devices:
            try:
                device.close()
            except Exception:
                pass

        self._devices = []
        self._registered = False
        logger.info("Hotkey manager cleaned up")
