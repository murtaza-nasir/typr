"""Storage for recordings whose transcription failed, so they can be retried."""

import io
import json
import uuid
import wave
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from typr.utils.logger import logger


FAILED_DIR = Path.home() / ".local" / "share" / "typr" / "failed"


@dataclass
class FailedClip:
    """Metadata for one saved recording. Audio lives in <id>.wav beside it."""

    id: str
    timestamp: str  # ISO 8601
    error: str
    duration_s: float = 0.0
    attempts: int = 1

    @property
    def audio_path(self) -> Path:
        return FAILED_DIR / f"{self.id}.wav"

    @property
    def meta_path(self) -> Path:
        return FAILED_DIR / f"{self.id}.json"

    def datetime(self) -> datetime:
        try:
            return datetime.fromisoformat(self.timestamp)
        except ValueError:
            return datetime.now()


def _wav_duration(audio_data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(audio_data), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate() or 1)
    except (wave.Error, EOFError):
        return 0.0


class FailedAudioStore(QObject):
    """Directory-backed store of failed recordings. Newest clips first."""

    clips_changed = pyqtSignal()

    def __init__(self, max_clips: int = 20, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._max_clips = max_clips

    def clips(self) -> list[FailedClip]:
        if not FAILED_DIR.exists():
            return []
        known = {f for f in FailedClip.__dataclass_fields__}
        clips = []
        for meta in FAILED_DIR.glob("*.json"):
            try:
                with open(meta) as f:
                    data = json.load(f)
                clip = FailedClip(**{k: v for k, v in data.items() if k in known})
            except (OSError, json.JSONDecodeError, TypeError) as e:
                logger.error(f"Skipping unreadable failed clip {meta.name}: {e}")
                continue
            if clip.audio_path.exists():
                clips.append(clip)
        clips.sort(key=lambda c: c.timestamp, reverse=True)
        return clips

    def get(self, clip_id: str) -> Optional[FailedClip]:
        for clip in self.clips():
            if clip.id == clip_id:
                return clip
        return None

    def load_audio(self, clip: FailedClip) -> bytes:
        return clip.audio_path.read_bytes()

    def add(self, audio_data: bytes, error: str) -> Optional[FailedClip]:
        clip = FailedClip(
            id=datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6],
            timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
            error=error,
            duration_s=round(_wav_duration(audio_data), 1),
        )
        try:
            FAILED_DIR.mkdir(parents=True, exist_ok=True)
            clip.audio_path.write_bytes(audio_data)
            self._write_meta(clip)
        except OSError as e:
            logger.error(f"Failed to save audio for retry: {e}")
            return None
        logger.info(f"Saved failed recording {clip.id} ({clip.duration_s}s)")
        self._prune()
        self.clips_changed.emit()
        return clip

    def mark_failed_again(self, clip: FailedClip, error: str) -> None:
        clip.error = error
        clip.attempts += 1
        try:
            self._write_meta(clip)
        except OSError as e:
            logger.error(f"Failed to update failed clip {clip.id}: {e}")
        self.clips_changed.emit()

    def delete(self, clip_id: str) -> None:
        for path in (FAILED_DIR / f"{clip_id}.wav", FAILED_DIR / f"{clip_id}.json"):
            path.unlink(missing_ok=True)
        self.clips_changed.emit()

    def clear(self) -> None:
        for clip in self.clips():
            self.delete(clip.id)

    def _write_meta(self, clip: FailedClip) -> None:
        tmp = clip.meta_path.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(asdict(clip), f, indent=2)
        tmp.replace(clip.meta_path)

    def _prune(self) -> None:
        for clip in self.clips()[self._max_clips :]:
            logger.info(f"Pruning old failed recording {clip.id}")
            self.delete(clip.id)
