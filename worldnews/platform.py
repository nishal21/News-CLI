"""Cross-platform helpers (desktop + Termux)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser
from typing import Tuple


def open_url(url: str) -> Tuple[bool, str]:
    """Open a URL in the system browser / Termux intent.

    Returns (ok, message).
    """
    if not url:
        return False, "No URL"

    candidates: list[list[str]] = []
    if shutil.which("termux-open-url"):
        candidates.append(["termux-open-url", url])
    if shutil.which("xdg-open"):
        candidates.append(["xdg-open", url])
    if sys.platform == "darwin" and shutil.which("open"):
        candidates.append(["open", url])

    for cmd in candidates:
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, "Opened"
        except Exception:
            continue

    try:
        opened = bool(webbrowser.open(url))
        if opened:
            return True, "Opened in browser"
    except Exception:
        opened = False

    if sys.platform == "win32":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return True, "Opened"
        except Exception:
            pass

    if shutil.which("termux-clipboard-set"):
        try:
            subprocess.run(
                ["termux-clipboard-set"],
                input=url.encode("utf-8"),
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return False, "Copied URL to clipboard (browser open failed)"
        except Exception:
            pass

    return False, "Could not open URL — copy it from the article"


def which_player_hint() -> str:
    """Short install hint when no audio player works."""
    home = os.environ.get("HOME", "")
    prefix = os.environ.get("PREFIX", "")
    if "com.termux" in home or "com.termux" in prefix or shutil.which(
        "termux-media-player"
    ):
        return "Install: pkg install termux-api ffmpeg"
    return "Install ffmpeg (ffplay) or mpg123 for TTS playback"
