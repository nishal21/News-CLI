"""Animated ASCII loading splash (textual-pyfiglet)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.timer import Timer
from textual.widgets import LoadingIndicator, Static

from worldnews import __version__

_STATUS_CYCLE = (
    "Contacting sources…",
    "Parsing feeds…",
    "Sorting headlines…",
    "Almost there…",
)

_SPIN = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


def _make_figlet(text: str, font: str):
    """Build FigletWidget when textual-pyfiglet is available."""
    from textual_pyfiglet import FigletWidget

    return FigletWidget(
        text,
        font=font,
        justify="center",
        colors=["$accent", "$primary", "$secondary"],
        animate=True,
        animation_type="smooth_strobe",
        fps=10,
        id="splash-figlet-widget",
        classes="splash-figlet-widget",
    )


class AsciiSplash(Vertical):
    """Full-pane centered WORLD NEWS figlet + cycling status."""

    DEFAULT_CSS = """
    AsciiSplash {
        width: 100%;
        height: 100%;
        background: $surface;
        align: center middle;
        overflow: hidden;
    }

    AsciiSplash > .splash-stage {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 2;
    }

    AsciiSplash .splash-figlet-widget,
    AsciiSplash .splash-figlet {
        width: 100%;
        height: auto;
        content-align: center middle;
        text-align: center;
        color: $accent;
        margin: 0 0 1 0;
    }

    AsciiSplash .splash-rule,
    AsciiSplash .splash-tagline,
    AsciiSplash .splash-subtitle,
    AsciiSplash .splash-status {
        width: 100%;
        height: 1;
        text-align: center;
        content-align: center middle;
    }

    AsciiSplash .splash-rule {
        color: $panel;
        margin: 0 0 1 0;
    }

    AsciiSplash .splash-tagline {
        color: $secondary;
        margin: 0 0 1 0;
    }

    AsciiSplash .splash-subtitle {
        color: $primary;
        text-style: bold;
        margin: 0 0 1 0;
    }

    AsciiSplash #splash-spinner {
        width: 100%;
        height: 1;
        content-align: center middle;
        color: $accent;
        margin: 0 0 1 0;
    }

    AsciiSplash .splash-status {
        color: $secondary;
    }
    """

    def __init__(
        self,
        *args,
        feed_label: str = "news",
        boot: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._feed_label = (feed_label or "news").strip() or "news"
        self._boot = boot
        self._running = False
        self._status_i = 0
        self._spin_i = 0
        self._tick: Timer | None = None
        self._has_figlet = False
        self.add_class("ascii-splash")
        if boot:
            self.add_class("boot-mode")

    def compose(self) -> ComposeResult:
        text, font = "WORLD NEWS", "slant"
        with Vertical(classes="splash-stage"):
            try:
                yield _make_figlet(text, font)
                self._has_figlet = True
            except Exception:
                yield Static(
                    f"[bold #c45c26]═══ {text} ═══[/]",
                    id="splash-figlet",
                    classes="splash-figlet",
                    markup=True,
                )
            yield Static("─" * 40, id="splash-rule", classes="splash-rule")
            yield Static(
                f"terminal newsroom · v{__version__}",
                id="splash-tagline",
                classes="splash-tagline",
            )
            yield Static("", id="splash-subtitle", classes="splash-subtitle")
            yield LoadingIndicator(id="splash-spinner")
            yield Static("", id="splash-status", classes="splash-status")

    def on_mount(self) -> None:
        self._paint_banner()
        self._paint_subtitle()
        if self.has_class("splash-on") or self._boot:
            self.start()

    def on_resize(self) -> None:
        if self._running or self.display:
            self._paint_banner()

    def show_for(self, label: str = "news") -> None:
        """Update feed label and start animation."""
        self._feed_label = (label or "news").strip() or "news"
        self._paint_subtitle()
        self.add_class("splash-on")
        self.display = True
        try:
            self.styles.display = "block"
        except Exception:
            pass
        self.start()

    def set_status(self, text: str) -> None:
        try:
            self.query_one("#splash-status", Static).update(text)
        except Exception:
            pass

    def start(self) -> None:
        if self._running:
            self._paint_status()
            self._set_figlet_animated(True)
            return
        self._running = True
        self._status_i = 0
        self._spin_i = 0
        self._paint_banner()
        self._paint_subtitle()
        self._paint_status()
        self._set_figlet_animated(True)
        try:
            if self._tick is not None:
                self._tick.stop()
        except Exception:
            pass
        self._tick = self.set_interval(0.12, self._on_tick)

    def stop(self) -> None:
        self._running = False
        try:
            if self._tick is not None:
                self._tick.stop()
                self._tick = None
        except Exception:
            pass
        self._set_figlet_animated(False)

    def _cols(self) -> int:
        try:
            return int(self.app.size.width)
        except Exception:
            return 80

    def _banner_spec(self) -> tuple[str, str]:
        """Return (text, font) — boot always prefers full WORLD NEWS, centered."""
        cols = self._cols()
        if self._boot:
            # Opening splash: keep the brand big and centered
            if cols < 52:
                return "WN", "small"
            if cols < 78:
                return "NEWS", "slant"
            return "WORLD NEWS", "slant"
        if cols < 48:
            return "WN", "small"
        if cols < 72:
            return "NEWS", "small"
        return "WORLD NEWS", "slant"

    def _paint_banner(self) -> None:
        text, font = self._banner_spec()
        if self._has_figlet:
            try:
                from textual_pyfiglet import FigletWidget

                fw = self.query_one("#splash-figlet-widget", FigletWidget)
                fw.set_font(font)
                fw.update(text)
                return
            except Exception:
                pass
        try:
            self.query_one("#splash-figlet", Static).update(
                f"[bold #c45c26]═══ {text} ═══[/]"
            )
        except Exception:
            pass

    def _set_figlet_animated(self, on: bool) -> None:
        if not self._has_figlet:
            return
        try:
            from textual_pyfiglet import FigletWidget

            self.query_one("#splash-figlet-widget", FigletWidget).animated = on
        except Exception:
            pass

    def _paint_subtitle(self) -> None:
        lab = self._feed_label
        if self._boot:
            msg = "Opening World News…"
        else:
            msg = f"Fetching {lab}"
        try:
            self.query_one("#splash-subtitle", Static).update(msg)
        except Exception:
            pass

    def _paint_status(self) -> None:
        spin = _SPIN[self._spin_i % len(_SPIN)]
        msg = _STATUS_CYCLE[self._status_i % len(_STATUS_CYCLE)]
        self.set_status(f"{spin}  {msg}")

    def _on_tick(self) -> None:
        if not self._running:
            return
        self._spin_i += 1
        if self._spin_i % 6 == 0:
            self._status_i += 1
        self._paint_status()
