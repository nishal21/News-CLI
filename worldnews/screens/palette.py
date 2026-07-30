"""Command palette modal."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option


class CommandPaletteScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    COMMANDS = [
        ("refresh", "Refresh current feed"),
        ("search", "Search all news"),
        ("bookmarks", "Show bookmarks"),
        ("trending", "Trending keywords"),
        ("breaking", "Breaking news"),
        ("summary", "Summary digest"),
        ("compare", "Compare categories"),
        ("offline", "Offline cache"),
        ("settings", "Settings"),
        ("add-feed", "Add / manage news websites (any language)"),
        ("manage-feeds", "Manage My Feeds — add, remove, open all"),
        ("my-feeds", "Open My Feeds (all custom stories)"),
        ("ai-chat", "AI chat"),
        ("ai-provider", "Choose AI provider"),
        ("voice-setup", "Voice / TTS provider & API keys"),
        ("speak", "Speak current article"),
        ("theme", "Cycle theme"),
        ("export", "Export list as Markdown"),
        ("help", "Show help"),
        ("quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="palette-box"):
            yield Label("Command palette", classes="modal-title")
            yield Input(placeholder="Type a command…", id="palette-input")
            yield OptionList(
                *[Option(f"{cid} — {desc}", id=cid) for cid, desc in self.COMMANDS],
                id="palette-list",
            )

    def on_mount(self) -> None:
        self.query_one("#palette-input", Input).focus()

    @on(Input.Changed, "#palette-input")
    def filter_commands(self, event: Input.Changed) -> None:
        q = event.value.strip().lower()
        ol = self.query_one("#palette-list", OptionList)
        ol.clear_options()
        for cid, desc in self.COMMANDS:
            if not q or q in cid or q in desc.lower():
                ol.add_option(Option(f"{cid} — {desc}", id=cid))

    @on(OptionList.OptionSelected, "#palette-list")
    def pick(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self.dismiss(str(event.option_id))

    @on(Input.Submitted, "#palette-input")
    def submit(self, event: Input.Submitted) -> None:
        ol = self.query_one("#palette-list", OptionList)
        if ol.option_count:
            opt = ol.get_option_at_index(ol.highlighted or 0)
            if opt and opt.id:
                self.dismiss(str(opt.id))
