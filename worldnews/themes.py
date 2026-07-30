"""Hallmark-tuned theme packs for World News CLI (terminal newsroom).

/* Hallmark · macrostructure: Workbench · genre: editorial · theme: newsroom
 * tone: editorial-newsroom · anchor hue: warm-ink (~35°)
 * medium: Textual TUI · axes: dark / grotesk-density / warm
 * pre-emit critique: P5 H5 E4 S4 R5 V4
 */
"""

from textual.theme import Theme

THEMES = {
    # Default — ink on charcoal, single warm accent (anti-purple / anti-slop)
    "newsroom": Theme(
        name="newsroom",
        primary="#e8d5b5",  # warm paper highlight
        secondary="#a89984",
        accent="#c45c26",  # ink-vermillion <5% usage
        foreground="#e6e1d6",
        background="#12110f",
        surface="#1a1916",
        panel="#26241f",
        success="#7d9b6a",
        warning="#d4a017",
        error="#c23b22",
        dark=True,
    ),
    # Phosphor terminal — cool green mono news desk
    "phosphor": Theme(
        name="phosphor",
        primary="#33ff66",
        secondary="#1a9940",
        accent="#a8ffb0",
        foreground="#c8f5d0",
        background="#0a120c",
        surface="#0f1a12",
        panel="#152018",
        success="#33ff66",
        warning="#c8e06a",
        error="#ff5555",
        dark=True,
    ),
    # Broadsheet light — rare light TUI (Newsprint cousin)
    "broadsheet": Theme(
        name="broadsheet",
        primary="#1a1a1a",
        secondary="#4a4a4a",
        accent="#8b1e1e",
        foreground="#1a1a1a",
        background="#f4efe6",
        surface="#ebe4d6",
        panel="#ddd4c4",
        success="#2d5a27",
        warning="#8a6d00",
        error="#8b1e1e",
        dark=False,
    ),
    "nord": Theme(
        name="nord",
        primary="#88c0d0",
        secondary="#81a1c1",
        accent="#8fbcbb",
        foreground="#eceff4",
        background="#2e3440",
        surface="#3b4252",
        panel="#434c5e",
        success="#a3be8c",
        warning="#ebcb8b",
        error="#bf616a",
        dark=True,
    ),
    "github-dark": Theme(
        name="github-dark",
        primary="#58a6ff",
        secondary="#8b949e",
        accent="#3fb950",
        foreground="#e6edf3",
        background="#0d1117",
        surface="#161b22",
        panel="#21262d",
        success="#3fb950",
        warning="#d29922",
        error="#f85149",
        dark=True,
    ),
    "high-contrast": Theme(
        name="high-contrast",
        primary="#ffffff",
        secondary="#aaaaaa",
        accent="#ffff00",
        foreground="#ffffff",
        background="#000000",
        surface="#0a0a0a",
        panel="#1a1a1a",
        success="#00ff00",
        warning="#ffff00",
        error="#ff0000",
        dark=True,
    ),
}

DEFAULT_THEME = "newsroom"

# Stable cycle order (Hallmark rotation: newsroom → phosphor → broadsheet → …)
THEME_CYCLE = (
    "newsroom",
    "phosphor",
    "broadsheet",
    "nord",
    "github-dark",
    "high-contrast",
)


def register_themes(app) -> None:
    for theme in THEMES.values():
        app.register_theme(theme)
