"""XDG-aware paths with legacy ~/.news-cli-* fallbacks (Termux-safe)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def _home() -> Path:
    try:
        h = Path.home()
        if h.exists():
            return h
    except Exception:
        pass
    return Path(tempfile.gettempdir())


def _ensure_writable(base: Path) -> Path:
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return base
    except Exception:
        fallback = Path(tempfile.gettempdir()) / "worldnews"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        return _ensure_writable(Path(xdg) / "worldnews")
    return _ensure_writable(_home() / ".config" / "worldnews")


def cache_dir() -> Path:
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg:
        return _ensure_writable(Path(xdg) / "worldnews")
    # Prefer XDG-style; also accept legacy ~/.news-cli-cache for existing data
    modern = _home() / ".cache" / "worldnews"
    legacy = _home() / ".news-cli-cache"
    if modern.exists() or not legacy.exists():
        return _ensure_writable(modern)
    return _ensure_writable(legacy)


def export_dir() -> Path:
    """Prefer Termux shared downloads when present."""
    termux = _home() / "storage" / "downloads"
    if termux.is_dir():
        return termux
    return _ensure_writable(_home())


def resolve_config_file(name: str, legacy_basename: str) -> Path:
    """Return path for a config JSON file.

    Prefers XDG ``config_dir()/name``. If only a legacy ``~/legacy_basename``
    exists, keep reading/writing that path until the next save migrates.
    """
    modern = config_dir() / name
    if modern.exists():
        return modern
    legacy = _home() / legacy_basename
    if legacy.exists():
        return legacy
    return modern


def chmod_private(path: Path | str) -> None:
    """Best-effort 0600 — no-ops or ignores errors on Windows."""
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def write_json(path: Path | str, data: Any, *, private: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Migrate: if writing and path was legacy, prefer modern location
    text = json.dumps(data, indent=2, ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    if private:
        chmod_private(path)


def migrate_to_modern(path: Path, modern_name: str, *, private: bool = False) -> Path:
    """If ``path`` is a legacy home file, copy content to XDG and return modern path."""
    modern = config_dir() / modern_name
    if path.resolve() == modern.resolve():
        return path
    try:
        if path.exists() and not modern.exists():
            modern.write_bytes(path.read_bytes())
            if private:
                chmod_private(modern)
            return modern
        if modern.exists():
            return modern
    except Exception:
        pass
    return path
