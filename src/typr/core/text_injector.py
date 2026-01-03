"""Text injection using wtype for Wayland."""

import shutil
import subprocess
from typing import Optional

from typr.utils.logger import logger


class TextInjector:
    """Injects text into focused window using wtype (Wayland)."""

    def __init__(self, typing_delay: int = 0):
        """Initialize text injector.

        Args:
            typing_delay: Delay between keystrokes in milliseconds.
        """
        self.typing_delay = typing_delay
        self._wtype_path: Optional[str] = None
        self._check_wtype()

    def _check_wtype(self) -> None:
        """Check if wtype is installed."""
        self._wtype_path = shutil.which("wtype")
        if not self._wtype_path:
            logger.warning("wtype not found - text injection will not work")
            logger.warning("Install with: sudo pacman -S wtype")

    def is_available(self) -> bool:
        """Check if text injection is available."""
        return self._wtype_path is not None

    def type_text(self, text: str) -> bool:
        """Type text at current cursor position.

        Args:
            text: The text to type.

        Returns:
            True if successful, False otherwise.
        """
        if not text:
            return True

        if not self._wtype_path:
            logger.error("wtype not available")
            return False

        try:
            # Split text by newlines and handle each part
            parts = text.split("\n")
            for i, part in enumerate(parts):
                if part:
                    # Type the text part
                    cmd = [self._wtype_path]
                    if self.typing_delay > 0:
                        cmd.extend(["-d", str(self.typing_delay)])
                    cmd.append(part)

                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=30
                    )
                    if result.returncode != 0:
                        logger.error(f"wtype failed: {result.stderr}")
                        return False

                # Add newline between parts (except after last)
                if i < len(parts) - 1:
                    result = subprocess.run(
                        [self._wtype_path, "-k", "Return"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode != 0:
                        logger.error(f"wtype newline failed: {result.stderr}")
                        return False

            logger.info(f"Typed {len(text)} characters")
            return True

        except subprocess.TimeoutExpired:
            logger.error("wtype timed out")
            return False
        except Exception as e:
            logger.error(f"Text injection failed: {e}")
            return False

    def type_key(self, key: str) -> bool:
        """Press a special key.

        Args:
            key: Key name (e.g., 'Return', 'Tab', 'BackSpace').

        Returns:
            True if successful, False otherwise.
        """
        if not self._wtype_path:
            logger.error("wtype not available")
            return False

        try:
            result = subprocess.run(
                [self._wtype_path, "-k", key],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Key press failed: {e}")
            return False

    def type_with_modifier(self, key: str, modifiers: list[str]) -> bool:
        """Type a key with modifiers.

        Args:
            key: The key to type.
            modifiers: List of modifiers (e.g., ['ctrl', 'shift']).

        Returns:
            True if successful, False otherwise.
        """
        if not self._wtype_path:
            logger.error("wtype not available")
            return False

        try:
            cmd = [self._wtype_path]
            for mod in modifiers:
                cmd.extend(["-M", mod])
            cmd.append(key)
            for mod in modifiers:
                cmd.extend(["-m", mod])

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Modified key press failed: {e}")
            return False

    def set_typing_delay(self, delay: int) -> None:
        """Set typing delay.

        Args:
            delay: Delay between keystrokes in milliseconds.
        """
        self.typing_delay = delay
