"""Help modal."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
        ("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        from worldnews.terminal_setup import configure_terminal, terminal_hint_label

        try:
            hint = terminal_hint_label(configure_terminal())
        except Exception:
            hint = "Use a UTF-8 terminal and a font that covers your script"

        with Vertical(id="help-box"):
            yield Label("Keyboard shortcuts", classes="modal-title")
            with VerticalScroll(id="help-scroll"):
                yield Static(
                    "[b]Navigation[/]\n"
                    "  j/k · ↑↓     move list\n"
                    "  enter        open / focus reader\n"
                    "  esc / q      back (list) / quit\n"
                    "  [ / ]        prev / next feed\n"
                    "  1–9          jump category\n\n"
                    "[b]Actions[/]\n"
                    "  b            toggle bookmark\n"
                    "  o            open in browser\n"
                    "  a / e        AI summarize / explain\n"
                    "  t            speak article (again to stop)\n"
                    "  s            settings (App · AI · Voice)\n"
                    "  i            toggle auto-images\n"
                    "  /            filter list\n"
                    "  ctrl+p       command palette\n"
                    "  Ctrl+p →     add-feed / my-feeds / ai-provider / voice-setup\n"
                    "  ?            this help\n\n"
                    "[b]Feeds[/]\n"
                    "  Lists load 50 at a time — scroll / j near bottom for +50\n"
                    "  +            manage My Feeds (add websites)\n"
                    "  My Feeds = your websites (any language — tagged)\n\n"
                    "[b]Scripts & fonts[/]\n"
                    f"  Terminal: {hint}\n"
                    "  Windows: Windows Terminal + Nirmala UI / Noto Sans Malayalam\n"
                    "  Termux: install Noto Malayalam font package\n"
                    "  Linux/macOS: UTF-8 locale + Noto / Meera\n"
                    "  Default: no Indic/Arabic glyphs in the TUI (avoids bleed)\n"
                    "  Press t to hear the story · o for browser\n"
                    "  Flags: --plain / --ascii · --native-titles\n"
                    "  Settings → App → Scripts: safe · plain · native\n\n"
                    "[b]Phone / Termux[/]\n"
                    "  Narrow screens hide the feed rail — use [ ] or 1–9\n"
                    "  Enter opens full-width reader · Esc returns to list\n",
                    id="help-body",
                    markup=True,
                )
            yield Button("Close", variant="primary", id="help-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()
