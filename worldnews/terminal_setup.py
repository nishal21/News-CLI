"""Cross-platform terminal bootstrap: UTF-8 + Windows VT mode."""

from __future__ import annotations

import os
import sys


def configure_terminal() -> str:
    """Force UTF-8 I/O and enable Windows virtual terminal processing.

    Returns a short environment hint for Help / docs (e.g. ``windows-terminal``).
    """
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")

    for stream in (sys.stdout, sys.stderr, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    if sys.platform == "win32":
        return _configure_windows()
    return _configure_posix()


def _configure_posix() -> str:
    lang = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
    if "utf-8" in lang or "utf8" in lang:
        return "posix-utf8"
    return "posix"


def _configure_windows() -> str:
    hint = "windows"
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # UTF-8 code pages
        try:
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)
        except Exception:
            pass

        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        ENABLE_PROCESSED_OUTPUT = 0x0001
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            new_mode = mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING | ENABLE_PROCESSED_OUTPUT
            if kernel32.SetConsoleMode(handle, new_mode):
                hint = "windows-vt"
            else:
                hint = "windows-legacy"
        else:
            # No console mode (piped / Windows Terminal sometimes) — assume modern
            hint = "windows-terminal"
    except Exception:
        hint = "windows"

    # WT_SESSION is set inside Windows Terminal
    if os.environ.get("WT_SESSION"):
        hint = "windows-terminal"
    elif os.environ.get("TERM_PROGRAM", "").lower() == "vscode":
        hint = "windows-vscode"
    return hint


def terminal_hint_label(hint: str) -> str:
    """Human-readable terminal tip for Help screen."""
    return {
        "windows-terminal": "Windows Terminal (good) — set font to Nirmala UI / Noto Sans Malayalam",
        "windows-vt": "Windows console with VT — prefer Windows Terminal app over cmd.exe",
        "windows-legacy": "Legacy Windows console — use Windows Terminal; Indic scripts will overlap",
        "windows-vscode": "VS Code terminal — set a font that covers your script",
        "windows": "Windows — use Windows Terminal + Nirmala UI / Noto Sans Malayalam",
        "posix-utf8": "UTF-8 locale OK — install Noto / Meera fonts for Indic scripts",
        "posix": "Set LANG=*.UTF-8 and a font with your script (Noto Sans Malayalam, …)",
    }.get(hint, "Use a UTF-8 terminal and a font that covers your script")
