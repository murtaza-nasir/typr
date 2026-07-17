"""System tray icon for Typr."""

from enum import Enum, auto
from typing import Callable, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from typr.utils.logger import logger


def _truncate_output(text: str, length: int = 60) -> str:
    """Collapse whitespace and shorten text for a menu label."""
    collapsed = " ".join(text.split())
    if len(collapsed) > length:
        collapsed = collapsed[: length - 1].rstrip() + "…"
    return collapsed or "(empty)"


class TrayState(Enum):
    """Tray icon states."""

    IDLE = auto()
    RECORDING = auto()
    PROCESSING = auto()
    ERROR = auto()


class TrayIcon(QSystemTrayIcon):
    """System tray icon with status indicators and context menu."""

    # Signals
    settings_requested = pyqtSignal()
    history_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    toggle_mode = pyqtSignal()
    record_toggled = pyqtSignal(bool)  # True = start, False = stop
    output_selected = pyqtSignal(str)  # Full text of a chosen previous output

    # State colors for icon generation
    STATE_COLORS = {
        TrayState.IDLE: "#888888",  # Gray
        TrayState.RECORDING: "#FF4444",  # Red
        TrayState.PROCESSING: "#FFAA00",  # Yellow/Orange
        TrayState.ERROR: "#FF0000",  # Bright red
    }

    STATE_TOOLTIPS = {
        TrayState.IDLE: "Ready - Hold {hotkey} to record",
        TrayState.RECORDING: "Recording... Release to stop",
        TrayState.PROCESSING: "Transcribing...",
        TrayState.ERROR: "Error - Right-click for options",
    }

    def __init__(self, hotkey: str = "Meta+Shift+Space", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._state = TrayState.IDLE
        self._hotkey = hotkey
        self._mode = "push_to_talk"
        self._status_message = "Ready"

        # Callable returning the recent output texts (newest first).
        self._outputs_provider: Optional[Callable[[], list[str]]] = None

        self._setup_icons()
        self._setup_menu()
        self._update_tooltip()

    def _setup_icons(self) -> None:
        """Create icons for each state."""
        self._icons = {}
        for state in TrayState:
            self._icons[state] = self._create_icon(state)
        self.setIcon(self._icons[TrayState.IDLE])

    def _create_icon(self, state: TrayState) -> QIcon:
        """Create an icon for a state.

        Creates a simple colored circle icon. In production, you'd load
        SVG icons from resources.
        """
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QColor, QPainter, QPixmap

        size = 22
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw microphone-like shape
        color = QColor(self.STATE_COLORS[state])
        painter.setBrush(color)
        painter.setPen(color.darker(120))

        # Microphone body (rounded rectangle)
        painter.drawRoundedRect(6, 2, 10, 12, 3, 3)

        # Microphone stand
        painter.drawRect(9, 14, 4, 2)
        painter.drawRect(7, 16, 8, 2)

        # Recording indicator dot for recording state
        if state == TrayState.RECORDING:
            painter.setBrush(QColor("#FFFFFF"))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawEllipse(8, 5, 6, 6)

        painter.end()
        return QIcon(pixmap)

    def _setup_menu(self) -> None:
        """Create context menu."""
        menu = QMenu()

        # Record button (main action)
        self._record_action = QAction("Start Recording", menu)
        self._record_action.triggered.connect(self._on_record_clicked)
        menu.addAction(self._record_action)

        menu.addSeparator()

        # Status indicator
        self._status_action = QAction("Status: Ready", menu)
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)

        menu.addSeparator()

        # Previous outputs - rebuilt each time the menu opens
        self._outputs_menu = QMenu("Previous Outputs", menu)
        self._outputs_menu.setToolTipsVisible(True)
        self._outputs_menu.aboutToShow.connect(self._populate_outputs_menu)
        menu.addMenu(self._outputs_menu)

        # History
        history_action = QAction("History...", menu)
        history_action.triggered.connect(self.history_requested.emit)
        menu.addAction(history_action)

        # Settings
        settings_action = QAction("Settings...", menu)
        settings_action.triggered.connect(self.settings_requested.emit)
        menu.addAction(settings_action)

        menu.addSeparator()

        # Quit
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

        # Also trigger on left click
        self.activated.connect(self._on_activated)

    def set_outputs_provider(self, provider: Callable[[], list[str]]) -> None:
        """Set the callback used to fetch recent output texts (newest first)."""
        self._outputs_provider = provider

    def _populate_outputs_menu(self) -> None:
        """Rebuild the 'Previous Outputs' submenu from the current outputs."""
        menu = self._outputs_menu
        menu.clear()

        outputs = self._outputs_provider() if self._outputs_provider else []

        if not outputs:
            empty = QAction("No outputs yet", menu)
            empty.setEnabled(False)
            menu.addAction(empty)
            return

        for text in outputs:
            action = QAction(_truncate_output(text), menu)
            action.setToolTip(text)
            # Bind the full text per-action so clicking copies the original.
            action.triggered.connect(
                lambda _checked=False, t=text: self.output_selected.emit(t)
            )
            menu.addAction(action)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation (click)."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Left click - toggle recording
            self._on_record_clicked()

    def _on_record_clicked(self) -> None:
        """Handle record button click."""
        if self._state == TrayState.IDLE:
            self.record_toggled.emit(True)  # Start
        elif self._state == TrayState.RECORDING:
            self.record_toggled.emit(False)  # Stop

    def set_state(self, state: TrayState, message: Optional[str] = None) -> None:
        """Update icon and tooltip based on state.

        Args:
            state: The new state.
            message: Optional status message.
        """
        self._state = state

        # Update icon
        if state in self._icons:
            self.setIcon(self._icons[state])

        # Update status message
        if message:
            self._status_message = message
        else:
            self._status_message = {
                TrayState.IDLE: "Ready",
                TrayState.RECORDING: "Recording",
                TrayState.PROCESSING: "Transcribing",
                TrayState.ERROR: "Error",
            }.get(state, "Unknown")

        # Update menu status
        self._status_action.setText(f"Status: {self._status_message}")

        # Update record action text
        if state == TrayState.RECORDING:
            self._record_action.setText("Stop Recording")
        else:
            self._record_action.setText("Start Recording")

        # Disable record during processing
        self._record_action.setEnabled(state in (TrayState.IDLE, TrayState.RECORDING))

        # Update tooltip
        self._update_tooltip()

        logger.debug(f"Tray state changed to {state.name}: {self._status_message}")

    def _update_tooltip(self) -> None:
        """Update the tooltip text."""
        tooltip = self.STATE_TOOLTIPS.get(self._state, "Typr")
        tooltip = tooltip.format(hotkey=self._hotkey)
        self.setToolTip(tooltip)

    def set_hotkey(self, hotkey: str) -> None:
        """Update the displayed hotkey.

        Args:
            hotkey: The hotkey string to display.
        """
        self._hotkey = hotkey
        self._update_tooltip()

    def set_mode(self, mode: str) -> None:
        """Update the mode display.

        Args:
            mode: Either 'push_to_talk' or 'live'.
        """
        self._mode = mode

    def show_notification(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        duration: int = 3000,
    ) -> None:
        """Show a system notification.

        Args:
            title: Notification title.
            message: Notification message.
            icon: Icon type.
            duration: Display duration in milliseconds.
        """
        self.showMessage(title, message, icon, duration)

    def show_error(self, message: str) -> None:
        """Show an error notification.

        Args:
            message: Error message.
        """
        self.set_state(TrayState.ERROR, message)
        self.show_notification(
            "Typr Error", message, QSystemTrayIcon.MessageIcon.Critical
        )

    def get_state(self) -> TrayState:
        """Get the current state."""
        return self._state
