"""Clipboard writes that work without a focused window.

On Wayland a client may only set the clipboard while one of its surfaces
has keyboard focus. The tray menu, the copy-last hotkey and background
retries have no focused window, so QClipboard.setText() is silently
ignored there. wl-copy uses the compositor's data-control protocol, which
has no focus requirement, so we prefer it on Wayland and fall back to Qt.
"""

import os
import shutil
import subprocess

from PyQt6.QtGui import QGuiApplication

from typr.utils.logger import logger


def _copy_with_wl_copy(text: str) -> bool:
    wl_copy = shutil.which("wl-copy")
    if not wl_copy:
        return False
    try:
        # wl-copy forks a daemon that serves the selection; the parent exits
        # once it has the data. Detach its output so the daemon cannot hold
        # our pipes open.
        result = subprocess.run(
            [wl_copy],
            input=text.encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.error(f"wl-copy failed: {e}")
        return False
    if result.returncode != 0:
        logger.error(f"wl-copy exited with status {result.returncode}")
        return False
    return True


def copy_text(text: str) -> bool:
    """Put text on the system clipboard. Returns True on success."""
    if os.environ.get("WAYLAND_DISPLAY") and _copy_with_wl_copy(text):
        return True

    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        return False
    clipboard.setText(text)
    return True
