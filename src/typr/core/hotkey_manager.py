"""Global hotkey management using KDE's KGlobalAccel D-Bus interface."""

from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from typr.config import HotkeyConfig
from typr.utils.logger import logger

# D-Bus imports with graceful fallback
try:
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop

    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False
    logger.warning("dbus-python not available - hotkeys will not work")


class HotkeyManager(QObject):
    """Manages global hotkey registration with KDE's KGlobalAccel."""

    # Signals
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    hotkey_error = pyqtSignal(str)

    # Component identifiers for KGlobalAccel
    COMPONENT_NAME = "typr"
    COMPONENT_FRIENDLY = "Typr"

    def __init__(self, config: Optional[HotkeyConfig] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config = config or HotkeyConfig()
        self._session_bus: Optional["dbus.SessionBus"] = None
        self._component: Optional["dbus.Interface"] = None
        self._registered = False
        self._key_pressed = False

    def initialize(self) -> bool:
        """Initialize D-Bus connection and register shortcuts.

        Returns:
            True if initialization was successful, False otherwise.
        """
        if not DBUS_AVAILABLE:
            self.hotkey_error.emit("D-Bus not available")
            return False

        try:
            # Initialize D-Bus main loop
            DBusGMainLoop(set_as_default=True)
            self._session_bus = dbus.SessionBus()

            # Register shortcuts
            self._register_shortcuts()
            self._connect_signals()

            logger.info("Hotkey manager initialized")
            return True

        except dbus.exceptions.DBusException as e:
            error_msg = f"D-Bus error: {e}"
            logger.error(error_msg)
            self.hotkey_error.emit(error_msg)
            return False
        except Exception as e:
            error_msg = f"Hotkey initialization failed: {e}"
            logger.error(error_msg)
            self.hotkey_error.emit(error_msg)
            return False

    def _register_shortcuts(self) -> None:
        """Register shortcuts with KGlobalAccel."""
        if not self._session_bus:
            return

        # Get KGlobalAccel interface
        kglobalaccel = self._session_bus.get_object(
            "org.kde.kglobalaccel", "/kglobalaccel"
        )
        kga_iface = dbus.Interface(kglobalaccel, "org.kde.KGlobalAccel")

        # Action ID format: [component, action, friendly_component, friendly_action]
        action_id = dbus.Array(
            [
                self.COMPONENT_NAME,
                "push_to_talk",
                self.COMPONENT_FRIENDLY,
                "Push to Talk",
            ],
            signature="s",
        )

        # Register the action
        try:
            # doRegister returns the component path
            kga_iface.doRegister(action_id)
            logger.debug("Registered push_to_talk action")

            # Parse and set the shortcut
            shortcut_keys = self._parse_shortcut(self.config.push_to_talk)
            if shortcut_keys:
                # setShortcutKeys expects action_id and array of key sequences
                kga_iface.setShortcutKeys(
                    action_id,
                    dbus.Array([dbus.Array(shortcut_keys, signature="i")], signature="ai"),
                    0x2,  # SetPresent flag
                )
                logger.info(f"Set shortcut: {self.config.push_to_talk}")

            self._registered = True

        except dbus.exceptions.DBusException as e:
            logger.error(f"Failed to register shortcut: {e}")
            raise

    def _connect_signals(self) -> None:
        """Connect to component signals for press/release."""
        if not self._session_bus:
            return

        try:
            # Get the component object
            component_path = f"/component/{self.COMPONENT_NAME}"
            component = self._session_bus.get_object(
                "org.kde.kglobalaccel", component_path
            )

            # Store interface for later use
            self._component = dbus.Interface(
                component, "org.kde.kglobalaccel.Component"
            )

            # Connect to signals
            component.connect_to_signal(
                "globalShortcutPressed",
                self._on_shortcut_pressed,
                dbus_interface="org.kde.kglobalaccel.Component",
            )

            component.connect_to_signal(
                "globalShortcutReleased",
                self._on_shortcut_released,
                dbus_interface="org.kde.kglobalaccel.Component",
            )

            logger.debug("Connected to shortcut signals")

        except dbus.exceptions.DBusException as e:
            logger.error(f"Failed to connect signals: {e}")
            raise

    def _on_shortcut_pressed(
        self, component: str, shortcut: str, timestamp: int
    ) -> None:
        """Handle shortcut press event."""
        if shortcut == "push_to_talk" and not self._key_pressed:
            self._key_pressed = True
            logger.debug("Push-to-talk pressed")
            self.recording_started.emit()

    def _on_shortcut_released(
        self, component: str, shortcut: str, timestamp: int
    ) -> None:
        """Handle shortcut release event."""
        if shortcut == "push_to_talk" and self._key_pressed:
            self._key_pressed = False
            logger.debug("Push-to-talk released")
            self.recording_stopped.emit()

    def _parse_shortcut(self, shortcut_str: str) -> list[int]:
        """Convert shortcut string to Qt key codes.

        Args:
            shortcut_str: Shortcut like 'Meta+Shift+Space'.

        Returns:
            List of key codes for KGlobalAccel.
        """
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeySequence

        try:
            # Parse using Qt
            seq = QKeySequence.fromString(shortcut_str)
            if seq.isEmpty():
                logger.warning(f"Invalid shortcut: {shortcut_str}")
                return []

            # Get the key combination
            key_combo = seq[0]
            key = int(key_combo.key())
            modifiers = int(key_combo.keyboardModifiers())

            # Combine into single int (Qt format that KGlobalAccel understands)
            return [key | modifiers]

        except Exception as e:
            logger.error(f"Error parsing shortcut '{shortcut_str}': {e}")
            return []

    def update_shortcut(self, shortcut: str) -> bool:
        """Update the push-to-talk shortcut.

        Args:
            shortcut: New shortcut string.

        Returns:
            True if update was successful.
        """
        self.config.push_to_talk = shortcut

        if self._registered:
            try:
                self._register_shortcuts()
                return True
            except Exception as e:
                logger.error(f"Failed to update shortcut: {e}")
                return False

        return True

    def is_registered(self) -> bool:
        """Check if shortcuts are registered."""
        return self._registered

    def cleanup(self) -> None:
        """Clean up D-Bus resources."""
        # Note: KGlobalAccel keeps shortcuts registered even after app exits
        # This is intentional for user convenience
        self._session_bus = None
        self._component = None
        self._registered = False


class FallbackHotkeyManager(QObject):
    """Fallback hotkey manager using keyboard monitoring.

    Used when KDE D-Bus integration is not available.
    """

    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    hotkey_error = pyqtSignal(str)

    def __init__(self, config: Optional[HotkeyConfig] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config = config or HotkeyConfig()
        self._active = False
        logger.warning("Using fallback hotkey manager - functionality may be limited")

    def initialize(self) -> bool:
        """Initialize fallback hotkey monitoring."""
        # For now, just emit an error - could implement evdev-based monitoring
        self.hotkey_error.emit(
            "KDE shortcuts not available. Please configure a system shortcut manually."
        )
        return False

    def is_registered(self) -> bool:
        return False

    def cleanup(self) -> None:
        pass
