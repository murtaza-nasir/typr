"""Main application controller for Typr."""

from enum import Enum, auto
from typing import Optional

from PyQt6.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication

from typr.config import AppConfig
from typr.core.audio_recorder import AudioRecorder
from typr.core.history import HistoryEntry, HistoryManager
from typr.core.hotkey_manager import HotkeyManager
from typr.core.text_injector import TextInjector
from typr.core.transcriber import WhisperTranscriber
from typr.ui.tray_icon import TrayIcon, TrayState
from typr.utils.logger import logger


class TypingWorker(QThread):
    """Injects transcribed text off the GUI thread.

    type_text() sleeps between keystrokes, so running it on the Qt main
    thread freezes the tray UI for the duration of a long transcription.
    The keyboard grab is owned by the app state machine (armed when recording
    stops, released when we return to IDLE/ERROR), so this worker only resets
    any latched modifiers and types.
    """

    finished = pyqtSignal(bool)  # success

    def __init__(self, injector, text: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._injector = injector
        self._text = text

    def run(self) -> None:
        success = False
        try:
            self._injector.reset_modifiers()
            success = self._injector.type_text(self._text)
        except Exception as e:
            logger.error(f"Text injection failed: {e}")
        self.finished.emit(success)


class AppState(Enum):
    """Application states."""

    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    TYPING = auto()
    ERROR = auto()


class TyprApp(QObject):
    """Main application controller.

    Coordinates all components and manages application state.
    """

    state_changed = pyqtSignal(AppState)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # Load configuration
        self.config = AppConfig.load()
        logger.info("Configuration loaded")

        # Initialize state
        self._state = AppState.IDLE

        # Initialize components
        self._init_components()

        # Connect signals
        self._connect_signals()

    def _init_components(self) -> None:
        """Initialize all application components."""
        # Core components
        self.audio_recorder = AudioRecorder(self.config.audio)
        self.transcriber = WhisperTranscriber(
            api_key=self.config.api_key,
            api_base_url=self.config.api_base_url,
            model=self.config.transcription.model,
        )
        self.transcriber.language = self.config.transcription.language
        self.transcriber.prompt = self.config.transcription.prompt

        self.text_injector = TextInjector(self.config.ui.typing_delay)
        self.hotkey_manager = HotkeyManager(self.config.hotkeys)

        # History
        self.history = HistoryManager(self.config.history.max_entries)

        # UI components
        self.tray_icon = TrayIcon(self.config.hotkeys.push_to_talk)
        self.tray_icon.set_mode(self.config.transcription.mode)

        # Dialogs (lazy loaded)
        self._settings_dialog: Optional["SettingsDialog"] = None
        self._history_dialog: Optional["HistoryDialog"] = None

        # Background text-injection worker
        self._typing_worker: Optional[TypingWorker] = None
        self._typing_text: str = ""

        # Safety watchdog: force-release the keyboard grab if it is ever held
        # too long (e.g. a hung transcription), so the keyboard can never get
        # stuck grabbed. Generous interval; normal flow ungrabs well before.
        self._grab_watchdog = QTimer(self)
        self._grab_watchdog.setSingleShot(True)
        self._grab_watchdog.setInterval(30000)
        self._grab_watchdog.timeout.connect(self._on_grab_watchdog)

    def _connect_signals(self) -> None:
        """Connect all component signals."""
        # Hotkey -> Recording
        self.hotkey_manager.recording_started.connect(self._on_recording_start)
        self.hotkey_manager.recording_stopped.connect(self._on_recording_stop)
        self.hotkey_manager.hotkey_error.connect(self._on_hotkey_error)

        # Audio -> Transcription
        self.audio_recorder.audio_ready.connect(self._on_audio_ready)
        self.audio_recorder.recording_error.connect(self._on_error)

        # Transcription -> Text injection
        self.transcriber.transcription_complete.connect(self._on_transcription_complete)
        self.transcriber.transcription_error.connect(self._on_error)

        # UI
        self.tray_icon.settings_requested.connect(self._show_settings)
        self.tray_icon.history_requested.connect(self._show_history)
        self.tray_icon.quit_requested.connect(self._quit)
        self.tray_icon.record_toggled.connect(self._on_record_toggled)

    @pyqtSlot(bool)
    def _on_record_toggled(self, start: bool) -> None:
        """Handle manual record toggle from tray icon."""
        if start:
            self._on_recording_start()
        else:
            self._on_recording_stop()

    def start(self) -> None:
        """Start the application."""
        logger.info("Starting Typr")

        # Check for API key
        if not self.config.api_key:
            logger.warning("No API key configured")
            self.tray_icon.show_notification(
                "Typr",
                "Please configure your API key in Settings",
                self.tray_icon.MessageIcon.Warning,
            )

        # Check for wtype
        if not self.text_injector.is_available():
            self.tray_icon.show_notification(
                "Typr",
                "wtype not found. Install with: sudo pacman -S wtype",
                self.tray_icon.MessageIcon.Warning,
            )

        # Initialize hotkeys
        if not self.hotkey_manager.initialize():
            self.tray_icon.show_notification(
                "Typr",
                "Could not register hotkey. Check Settings for manual configuration.",
                self.tray_icon.MessageIcon.Warning,
            )

        # Show tray icon
        self.tray_icon.show()
        self.tray_icon.show_notification(
            "Typr Started",
            f"Hold {self.config.hotkeys.push_to_talk} to record",
            self.tray_icon.MessageIcon.Information,
            2000,
        )

    @pyqtSlot()
    def _on_recording_start(self) -> None:
        """Handle recording start from hotkey."""
        if self._state != AppState.IDLE:
            logger.debug(f"Cannot start recording in state {self._state}")
            return

        self._set_state(AppState.RECORDING)
        if not self.audio_recorder.start_recording():
            self._set_state(AppState.ERROR, "Failed to start recording")

    @pyqtSlot()
    def _on_recording_stop(self) -> None:
        """Handle recording stop from hotkey."""
        if self._state != AppState.RECORDING:
            logger.debug(f"Cannot stop recording in state {self._state}")
            return

        self._set_state(AppState.TRANSCRIBING)
        self.audio_recorder.stop_recording()

    @pyqtSlot(bytes)
    def _on_audio_ready(self, audio_data: bytes) -> None:
        """Handle completed audio recording."""
        if not audio_data:
            self._set_state(AppState.IDLE, "No audio recorded")
            return

        logger.info(f"Audio ready: {len(audio_data)} bytes")
        self.transcriber.transcribe(audio_data)

    @pyqtSlot(str)
    def _on_transcription_complete(self, text: str) -> None:
        """Handle completed transcription."""
        if not text or not text.strip():
            logger.info("Empty transcription result")
            self._set_state(AppState.IDLE)
            return

        logger.info(f"Transcription: {text[:50]}...")
        self._record_history(text)
        self._set_state(AppState.TYPING)

        # Type the text on a background thread so the GUI stays responsive.
        # The keyboard is already grabbed (armed when recording stopped); the
        # grab is released when we return to IDLE/ERROR in _set_state.
        self._typing_text = text
        self._typing_worker = TypingWorker(self.text_injector, text)
        self._typing_worker.finished.connect(self._on_typing_finished)
        self._typing_worker.start()

    @pyqtSlot(bool)
    def _on_typing_finished(self, success: bool) -> None:
        """Handle completion of background text injection."""
        if success:
            if self.config.ui.show_notifications:
                text = self._typing_text
                self.tray_icon.show_notification(
                    "Transcription Complete",
                    text[:100] + ("..." if len(text) > 100 else ""),
                    self.tray_icon.MessageIcon.Information,
                    self.config.ui.notification_duration,
                )
            self._set_state(AppState.IDLE)
        else:
            self._set_state(AppState.ERROR, "Failed to type text")

        self._cleanup_typing_worker()

    def _cleanup_typing_worker(self) -> None:
        """Clean up the background typing worker."""
        if self._typing_worker:
            self._typing_worker.deleteLater()
            self._typing_worker = None

    def _record_history(self, text: str) -> None:
        """Persist a completed transcription to history if enabled."""
        if not self.config.history.enabled:
            return

        self.history.add(
            HistoryEntry.create(
                text=text,
                model=self.config.transcription.model,
                language=self.config.transcription.language,
            )
        )

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        """Handle errors from components."""
        self._set_state(AppState.ERROR, message)

    @pyqtSlot(str)
    def _on_hotkey_error(self, message: str) -> None:
        """Handle hotkey registration errors."""
        logger.error(f"Hotkey error: {message}")
        # Don't change state, just notify
        self.tray_icon.show_notification(
            "Hotkey Error",
            message,
            self.tray_icon.MessageIcon.Warning,
        )

    def _set_state(self, state: AppState, message: Optional[str] = None) -> None:
        """Set application state.

        Args:
            state: New state.
            message: Optional status message.
        """
        old_state = self._state
        self._state = state

        logger.debug(f"State: {old_state.name} -> {state.name}")

        # Keyboard grab lifecycle. Arm the grab the moment recording stops so
        # the whole vulnerable window (transcription wait + injection) is
        # protected, but arm_grab() defers the actual grab until the hotkey is
        # fully released so its modifiers can't get stranded. Release on any
        # return to IDLE/ERROR, and run a watchdog so it can never stick.
        if state == AppState.TRANSCRIBING and old_state != AppState.TRANSCRIBING:
            self.hotkey_manager.arm_grab()
            self._grab_watchdog.start()
        elif state in (AppState.IDLE, AppState.ERROR):
            self._grab_watchdog.stop()
            self.hotkey_manager.ungrab_all()

        # Map to tray states
        tray_state = {
            AppState.IDLE: TrayState.IDLE,
            AppState.RECORDING: TrayState.RECORDING,
            AppState.TRANSCRIBING: TrayState.PROCESSING,
            AppState.TYPING: TrayState.PROCESSING,
            AppState.ERROR: TrayState.ERROR,
        }.get(state, TrayState.IDLE)

        self.tray_icon.set_state(tray_state, message)
        self.state_changed.emit(state)

        # Auto-recover from error state
        if state == AppState.ERROR:
            if message:
                self.tray_icon.show_error(message)
            QTimer.singleShot(3000, self._recover_from_error)

    @pyqtSlot()
    def _on_grab_watchdog(self) -> None:
        """Force-release the keyboard grab if it was held too long."""
        logger.warning("Grab watchdog fired - force-releasing keyboard")
        self.hotkey_manager.ungrab_all()

    @pyqtSlot()
    def _recover_from_error(self) -> None:
        """Recover from error state."""
        if self._state == AppState.ERROR:
            self._set_state(AppState.IDLE)

    @pyqtSlot()
    def _show_settings(self) -> None:
        """Show settings dialog."""
        from typr.ui.settings_dialog import SettingsDialog

        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self.config)
            self._settings_dialog.settings_saved.connect(self._on_settings_saved)

        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    @pyqtSlot()
    def _show_history(self) -> None:
        """Show transcription history dialog."""
        from typr.ui.history_dialog import HistoryDialog

        if self._history_dialog is None:
            self._history_dialog = HistoryDialog(self.history)

        self._history_dialog.show()
        self._history_dialog.raise_()
        self._history_dialog.activateWindow()

    @pyqtSlot()
    def _on_settings_saved(self) -> None:
        """Handle settings saved."""
        logger.info("Settings saved, reloading")

        # Update components with new settings
        self.transcriber.update_settings(
            api_key=self.config.api_key,
            api_base_url=self.config.api_base_url,
            model=self.config.transcription.model,
            language=self.config.transcription.language,
            prompt=self.config.transcription.prompt,
        )
        self.text_injector.set_typing_delay(self.config.ui.typing_delay)
        self.tray_icon.set_hotkey(self.config.hotkeys.push_to_talk)
        self.tray_icon.set_mode(self.config.transcription.mode)
        self.history.set_max_entries(self.config.history.max_entries)

        # Re-register hotkey if changed
        self.hotkey_manager.update_shortcut(self.config.hotkeys.push_to_talk)

    @pyqtSlot()
    def _quit(self) -> None:
        """Quit the application."""
        logger.info("Quitting Typr")

        # Cancel any ongoing recording
        if self._state == AppState.RECORDING:
            self.audio_recorder.cancel_recording()

        # Let any in-flight injection finish so it ungrabs the keyboard
        if self._typing_worker and self._typing_worker.isRunning():
            self._typing_worker.wait(2000)

        # Save config
        self.config.save()

        # Cleanup
        self.audio_recorder.cleanup()
        self.hotkey_manager.cleanup()
        self.text_injector.cleanup()

        # Quit application
        QApplication.quit()

    def get_state(self) -> AppState:
        """Get current application state."""
        return self._state
