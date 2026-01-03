"""Settings dialog for Typr."""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from typr.config import AppConfig
from typr.utils.logger import logger


class SettingsDialog(QDialog):
    """Settings dialog with tabs for configuration."""

    settings_saved = pyqtSignal()

    # Available Whisper models
    MODELS = [
        ("whisper-1", "Whisper 1 (Standard)"),
        ("gpt-4o-transcribe", "GPT-4o Transcribe (Better accuracy)"),
        ("gpt-4o-mini-transcribe", "GPT-4o Mini Transcribe (Faster)"),
    ]

    # Common languages
    LANGUAGES = [
        (None, "Auto-detect"),
        ("en", "English"),
        ("es", "Spanish"),
        ("fr", "French"),
        ("de", "German"),
        ("it", "Italian"),
        ("pt", "Portuguese"),
        ("ru", "Russian"),
        ("ja", "Japanese"),
        ("ko", "Korean"),
        ("zh", "Chinese"),
        ("ar", "Arabic"),
        ("hi", "Hindi"),
    ]

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Typr Settings")
        self.setMinimumSize(500, 450)

        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()
        tabs.addTab(self._create_general_tab(), "General")
        tabs.addTab(self._create_api_tab(), "API")
        tabs.addTab(self._create_hotkeys_tab(), "Hotkeys")
        tabs.addTab(self._create_audio_tab(), "Audio")
        tabs.addTab(self._create_about_tab(), "About")
        layout.addWidget(tabs)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn:
            apply_btn.clicked.connect(self._apply)
        layout.addWidget(buttons)

    def _create_general_tab(self) -> QWidget:
        """Create the General settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Transcription settings
        trans_group = QGroupBox("Transcription")
        trans_layout = QFormLayout(trans_group)

        # Model selection
        self._model_combo = QComboBox()
        for model_id, model_name in self.MODELS:
            self._model_combo.addItem(model_name, model_id)
        trans_layout.addRow("Model:", self._model_combo)

        # Language selection
        self._language_combo = QComboBox()
        for lang_code, lang_name in self.LANGUAGES:
            self._language_combo.addItem(lang_name, lang_code)
        trans_layout.addRow("Language:", self._language_combo)

        # Context prompt
        self._prompt_edit = QTextEdit()
        self._prompt_edit.setMaximumHeight(80)
        self._prompt_edit.setPlaceholderText(
            "Optional context to improve accuracy (e.g., technical terms, names)"
        )
        trans_layout.addRow("Context:", self._prompt_edit)

        layout.addWidget(trans_group)

        # UI settings
        ui_group = QGroupBox("User Interface")
        ui_layout = QFormLayout(ui_group)

        # Notifications
        self._notifications_check = QCheckBox("Show notifications")
        ui_layout.addRow(self._notifications_check)

        # Notification duration
        self._notif_duration_spin = QSpinBox()
        self._notif_duration_spin.setRange(1000, 10000)
        self._notif_duration_spin.setSingleStep(500)
        self._notif_duration_spin.setSuffix(" ms")
        ui_layout.addRow("Notification duration:", self._notif_duration_spin)

        # Typing delay
        self._typing_delay_spin = QSpinBox()
        self._typing_delay_spin.setRange(0, 100)
        self._typing_delay_spin.setSuffix(" ms")
        self._typing_delay_spin.setToolTip("Delay between keystrokes (0 = no delay)")
        ui_layout.addRow("Typing delay:", self._typing_delay_spin)

        layout.addWidget(ui_group)
        layout.addStretch()

        return widget

    def _create_api_tab(self) -> QWidget:
        """Create the API settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # API settings
        api_group = QGroupBox("OpenAI API")
        api_layout = QFormLayout(api_group)

        # API key
        self._api_key_edit = QLineEdit()
        self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_edit.setPlaceholderText("sk-...")
        api_layout.addRow("API Key:", self._api_key_edit)

        # Show/hide API key button
        key_layout = QHBoxLayout()
        self._show_key_btn = QPushButton("Show")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.toggled.connect(self._toggle_api_key_visibility)
        key_layout.addWidget(self._api_key_edit)
        key_layout.addWidget(self._show_key_btn)
        api_layout.addRow("API Key:", key_layout)

        # API base URL
        self._api_base_edit = QLineEdit()
        self._api_base_edit.setPlaceholderText("https://api.openai.com/v1")
        api_layout.addRow("Base URL:", self._api_base_edit)

        # Test connection button
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection)
        api_layout.addRow("", test_btn)

        layout.addWidget(api_group)

        # Info
        info_label = QLabel(
            "Get your API key from <a href='https://platform.openai.com/api-keys'>OpenAI Platform</a>"
        )
        info_label.setOpenExternalLinks(True)
        layout.addWidget(info_label)

        layout.addStretch()

        return widget

    def _create_hotkeys_tab(self) -> QWidget:
        """Create the Hotkeys settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Hotkey settings
        hotkey_group = QGroupBox("Keyboard Shortcuts")
        hotkey_layout = QFormLayout(hotkey_group)

        # Push-to-talk hotkey
        self._ptt_hotkey_edit = QKeySequenceEdit()
        hotkey_layout.addRow("Push-to-Talk:", self._ptt_hotkey_edit)

        # Cancel hotkey
        self._cancel_hotkey_edit = QKeySequenceEdit()
        hotkey_layout.addRow("Cancel Recording:", self._cancel_hotkey_edit)

        layout.addWidget(hotkey_group)

        # Info
        info_label = QLabel(
            "Note: Hotkeys are registered with KDE's global shortcut system. "
            "You can also configure them in System Settings > Shortcuts."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        return widget

    def _create_audio_tab(self) -> QWidget:
        """Create the Audio settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Audio settings
        audio_group = QGroupBox("Audio Input")
        audio_layout = QFormLayout(audio_group)

        # Input device
        self._device_combo = QComboBox()
        self._device_combo.addItem("Default", None)
        audio_layout.addRow("Input Device:", self._device_combo)

        # Refresh devices button
        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.clicked.connect(self._refresh_devices)
        audio_layout.addRow("", refresh_btn)

        # Sample rate (read-only info)
        sample_info = QLabel("16000 Hz (optimal for Whisper)")
        audio_layout.addRow("Sample Rate:", sample_info)

        layout.addWidget(audio_group)

        # Test recording
        test_group = QGroupBox("Test Recording")
        test_layout = QVBoxLayout(test_group)

        test_btn = QPushButton("Test Microphone")
        test_btn.clicked.connect(self._test_microphone)
        test_layout.addWidget(test_btn)

        self._test_status = QLabel("")
        test_layout.addWidget(self._test_status)

        layout.addWidget(test_group)
        layout.addStretch()

        # Populate devices
        self._refresh_devices()

        return widget

    def _create_about_tab(self) -> QWidget:
        """Create the About tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # App info
        title = QLabel("<h2>Typr</h2>")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version = QLabel("Version 0.1.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        desc = QLabel("Speech-to-text for Linux using OpenAI Whisper")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        layout.addStretch()

        # Links
        links = QLabel(
            '<a href="https://github.com/yourname/typr">GitHub</a> | '
            '<a href="https://platform.openai.com/docs/guides/speech-to-text">Whisper API Docs</a>'
        )
        links.setOpenExternalLinks(True)
        links.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(links)

        return widget

    def _load_settings(self) -> None:
        """Load current settings into UI."""
        # API
        self._api_key_edit.setText(self.config.api_key)
        self._api_base_edit.setText(self.config.api_base_url)

        # Transcription
        model_index = self._model_combo.findData(self.config.transcription.model)
        if model_index >= 0:
            self._model_combo.setCurrentIndex(model_index)

        lang_index = self._language_combo.findData(self.config.transcription.language)
        if lang_index >= 0:
            self._language_combo.setCurrentIndex(lang_index)

        self._prompt_edit.setPlainText(self.config.transcription.prompt)

        # UI
        self._notifications_check.setChecked(self.config.ui.show_notifications)
        self._notif_duration_spin.setValue(self.config.ui.notification_duration)
        self._typing_delay_spin.setValue(self.config.ui.typing_delay)

        # Hotkeys
        self._ptt_hotkey_edit.setKeySequence(
            QKeySequence.fromString(self.config.hotkeys.push_to_talk)
        )
        self._cancel_hotkey_edit.setKeySequence(
            QKeySequence.fromString(self.config.hotkeys.cancel_recording)
        )

        # Audio device
        device_index = self._device_combo.findData(self.config.audio.input_device)
        if device_index >= 0:
            self._device_combo.setCurrentIndex(device_index)

    def _save_settings(self) -> None:
        """Save settings from UI to config."""
        # API
        self.config.api_key = self._api_key_edit.text()
        self.config.api_base_url = self._api_base_edit.text() or "https://api.openai.com/v1"

        # Transcription
        self.config.transcription.model = self._model_combo.currentData()
        self.config.transcription.language = self._language_combo.currentData()
        self.config.transcription.prompt = self._prompt_edit.toPlainText()

        # UI
        self.config.ui.show_notifications = self._notifications_check.isChecked()
        self.config.ui.notification_duration = self._notif_duration_spin.value()
        self.config.ui.typing_delay = self._typing_delay_spin.value()

        # Hotkeys
        ptt_seq = self._ptt_hotkey_edit.keySequence()
        if not ptt_seq.isEmpty():
            self.config.hotkeys.push_to_talk = ptt_seq.toString()

        cancel_seq = self._cancel_hotkey_edit.keySequence()
        if not cancel_seq.isEmpty():
            self.config.hotkeys.cancel_recording = cancel_seq.toString()

        # Audio
        self.config.audio.input_device = self._device_combo.currentData()

        # Save to file
        self.config.save()
        logger.info("Settings saved")

    def _apply(self) -> None:
        """Apply settings without closing."""
        self._save_settings()
        self.settings_saved.emit()

    def _save_and_close(self) -> None:
        """Save settings and close dialog."""
        self._save_settings()
        self.settings_saved.emit()
        self.accept()

    def _toggle_api_key_visibility(self, show: bool) -> None:
        """Toggle API key visibility."""
        if show:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._show_key_btn.setText("Hide")
        else:
            self._api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._show_key_btn.setText("Show")

    def _test_connection(self) -> None:
        """Test API connection."""
        api_key = self._api_key_edit.text()
        base_url = self._api_base_edit.text() or "https://api.openai.com/v1"

        if not api_key:
            QMessageBox.warning(self, "Error", "Please enter an API key")
            return

        try:
            import httpx

            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                response.raise_for_status()

            QMessageBox.information(self, "Success", "Connection successful!")

        except httpx.HTTPStatusError as e:
            QMessageBox.warning(
                self, "Error", f"API error: {e.response.status_code}\n{e.response.text[:200]}"
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Connection failed: {e}")

    def _refresh_devices(self) -> None:
        """Refresh audio device list."""
        current_device = self._device_combo.currentData()
        self._device_combo.clear()
        self._device_combo.addItem("Default", None)

        try:
            from typr.core.audio_recorder import AudioRecorder

            recorder = AudioRecorder()
            devices = recorder.get_devices()
            recorder.cleanup()

            for device in devices:
                self._device_combo.addItem(device["name"], device["name"])

            # Restore selection
            if current_device:
                index = self._device_combo.findData(current_device)
                if index >= 0:
                    self._device_combo.setCurrentIndex(index)

        except Exception as e:
            logger.error(f"Failed to get devices: {e}")

    def _test_microphone(self) -> None:
        """Test microphone recording."""
        self._test_status.setText("Recording for 2 seconds...")

        try:
            from PyQt6.QtCore import QTimer

            from typr.core.audio_recorder import AudioRecorder

            recorder = AudioRecorder()
            recorder.start_recording()

            def stop_recording():
                audio_data = recorder.stop_recording()
                recorder.cleanup()

                if audio_data and len(audio_data) > 1000:
                    self._test_status.setText(
                        f"Success! Recorded {len(audio_data)} bytes"
                    )
                else:
                    self._test_status.setText("Recording too short or empty")

            QTimer.singleShot(2000, stop_recording)

        except Exception as e:
            self._test_status.setText(f"Error: {e}")
