"""Search modal."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList
from textual.widgets.option_list import Option


class SearchScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, history_items: list[str] | None = None) -> None:
        super().__init__()
        self.history_items = history_items or []

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box"):
            yield Label("Search news", classes="modal-title")
            yield Input(placeholder="Keywords…", id="search-input")
            if self.history_items:
                yield Label("Recent")
                yield OptionList(
                    *[Option(h, id=f"hist-{i}") for i, h in enumerate(self.history_items[:8])],
                    id="search-hist",
                )
            with Horizontal():
                yield Button("Search", variant="primary", id="search-go")
                yield Button("Cancel", id="search-cancel")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    @on(Input.Submitted, "#search-input")
    def submitted(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.dismiss(event.value.strip())

    @on(Button.Pressed, "#search-go")
    def go(self) -> None:
        val = self.query_one("#search-input", Input).value.strip()
        if val:
            self.dismiss(val)

    @on(Button.Pressed, "#search-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(OptionList.OptionSelected, "#search-hist")
    def hist(self, event: OptionList.OptionSelected) -> None:
        if event.option and event.option.prompt:
            self.dismiss(str(event.option.prompt))
