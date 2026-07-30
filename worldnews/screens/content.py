"""Summary / compare / trending modals."""
from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Markdown, Static


class SummaryScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    def __init__(self, articles: list[dict]) -> None:
        super().__init__()
        self.articles = articles

    def compose(self) -> ComposeResult:
        lines = ["# Summary digest\n"]
        by_src: dict[str, list] = {}
        for a in self.articles[:40]:
            by_src.setdefault(a.get("source", "?"), []).append(a)
        for src, items in sorted(by_src.items(), key=lambda x: -len(x[1])):
            lines.append(f"## {src} ({len(items)})\n")
            for a in items[:5]:
                lines.append(f"- **{a.get('title', '')}**")
            lines.append("")
        with Vertical(classes="modal-box"):
            yield Label("Summary", classes="modal-title")
            with VerticalScroll():
                yield Markdown("\n".join(lines))
            yield Button("Close", variant="primary", id="sum-close")

    @on(Button.Pressed, "#sum-close")
    def close(self) -> None:
        self.dismiss()


class CompareScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    def __init__(self, comparison: dict[str, list[dict]]) -> None:
        super().__init__()
        self.comparison = comparison

    def compose(self) -> ComposeResult:
        lines = ["# Category comparison\n"]
        for cat, arts in self.comparison.items():
            lines.append(f"## {cat.title()} — {len(arts)} articles\n")
            for a in arts[:4]:
                lines.append(f"- {a.get('title', '')} _({a.get('source', '')})_")
            lines.append("")
        with Vertical(classes="modal-box"):
            yield Label("Compare", classes="modal-title")
            with VerticalScroll():
                yield Markdown("\n".join(lines))
            yield Button("Close", variant="primary", id="cmp-close")

    @on(Button.Pressed, "#cmp-close")
    def close(self) -> None:
        self.dismiss()


class TrendingScreen(ModalScreen[None]):
    """Clean ranked keyword list — no Markdown tag-cloud (that overlapped)."""

    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    def __init__(self, keywords: list[tuple[str, int]]) -> None:
        super().__init__()
        self.keywords = keywords

    def compose(self) -> ComposeResult:
        max_c = max((c for _, c in self.keywords[:40]), default=1) or 1
        lines = []
        for i, (word, count) in enumerate(self.keywords[:40], 1):
            width = max(1, int(24 * count / max_c))
            bar = "█" * width
            lines.append(f"{i:>2}.  {word:<18}  ×{count:<5}  {bar}")
        body = "\n".join(lines) if lines else "No trending keywords yet.\nRefresh feeds and try again."
        with Vertical(id="trending-box", classes="modal-box"):
            yield Label("Trending keywords", classes="modal-title")
            yield Static(
                "Ranked from headlines (stopwords filtered).",
                classes="settings-hint",
            )
            with VerticalScroll(id="trending-scroll"):
                yield Static(body, id="trending-list")
            yield Button("Close", variant="primary", id="tr-close")

    @on(Button.Pressed, "#tr-close")
    def close(self) -> None:
        self.dismiss()
