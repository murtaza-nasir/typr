"""Configuration management for Typr."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AudioConfig:
    """Audio recording configuration."""

    input_device: Optional[str] = None  # None = default device
    sample_rate: int = 16000
    channels: int = 1


@dataclass
class TranscriptionConfig:
    """Transcription settings."""

    model: str = "whisper-1"  # whisper-1, gpt-4o-transcribe, gpt-4o-mini-transcribe
    language: Optional[str] = None  # None = auto-detect
    mode: str = "push_to_talk"  # push_to_talk, live
    prompt: str = ""  # Context prompt for better accuracy


@dataclass
class HotkeyConfig:
    """Hotkey settings."""

    push_to_talk: str = "Meta+Shift+Space"
    cancel_recording: str = "Escape"


@dataclass
class UIConfig:
    """UI settings."""

    show_notifications: bool = True
    notification_duration: int = 3000  # ms
    typing_delay: int = 0  # ms between characters


@dataclass
class AppConfig:
    """Main application configuration."""

    api_key: str = ""
    api_base_url: str = "https://api.openai.com/v1"
    audio: AudioConfig = field(default_factory=AudioConfig)
    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    # Config file location
    CONFIG_DIR: Path = field(default_factory=lambda: Path.home() / ".config" / "typr")
    CONFIG_FILE: Path = field(
        default_factory=lambda: Path.home() / ".config" / "typr" / "config.json"
    )

    def __post_init__(self):
        """Convert dict fields to dataclass instances if needed."""
        if isinstance(self.audio, dict):
            self.audio = AudioConfig(**self.audio)
        if isinstance(self.transcription, dict):
            self.transcription = TranscriptionConfig(**self.transcription)
        if isinstance(self.hotkeys, dict):
            self.hotkeys = HotkeyConfig(**self.hotkeys)
        if isinstance(self.ui, dict):
            self.ui = UIConfig(**self.ui)

    @classmethod
    def load(cls) -> "AppConfig":
        """Load config from file or return defaults."""
        config_file = Path.home() / ".config" / "typr" / "config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = json.load(f)
                # Remove non-serializable fields
                data.pop("CONFIG_DIR", None)
                data.pop("CONFIG_FILE", None)
                return cls(**data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error loading config: {e}, using defaults")
        return cls()

    def save(self) -> None:
        """Save config to file."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Convert to dict, excluding non-serializable fields
        data = self._to_dict()
        data.pop("CONFIG_DIR", None)
        data.pop("CONFIG_FILE", None)

        with open(self.CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

        # Set secure permissions (readable only by owner)
        os.chmod(self.CONFIG_FILE, 0o600)

    def _to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "api_key": self.api_key,
            "api_base_url": self.api_base_url,
            "audio": asdict(self.audio),
            "transcription": asdict(self.transcription),
            "hotkeys": asdict(self.hotkeys),
            "ui": asdict(self.ui),
        }
