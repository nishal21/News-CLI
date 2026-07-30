"""Custom feed add / manage modals."""
from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option


class AddFeedScreen(ModalScreen[dict | None]):
    """Add a custom news website or RSS feed (any language)."""

    BINDINGS = [("escape", "dismiss", "Close"), ("q", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="add-feed-box", classes="modal-box"):
            yield Label("Add news website", classes="modal-title")
            yield Static(
                "Paste any news site or RSS/Atom URL.\n"
                "Any language works — we detect it and tag every story\n"
                "(Hindi, Tamil, Japanese, Arabic, …).",
                classes="settings-hint",
            )
            yield Label("Name (optional)")
            yield Input(placeholder="e.g. Manorama / Asahi / El Pais", id="feed-name")
            yield Label("Website or feed URL")
            yield Input(
                placeholder="https://www.example.com  or  …/rss.xml",
                id="feed-url",
            )
            yield Static("", id="feed-status")
            with Horizontal(classes="settings-row"):
                yield Button("Discover & add", variant="primary", id="feed-add")
                yield Button("Cancel", id="feed-cancel")

    def on_mount(self) -> None:
        self.query_one("#feed-url", Input).focus()

    @on(Button.Pressed, "#feed-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#feed-add")
    def add(self) -> None:
        self._do_add()

    @on(Input.Submitted, "#feed-url")
    def submit_url(self) -> None:
        self._do_add()

    def _do_add(self) -> None:
        name = self.query_one("#feed-name", Input).value.strip()
        url = self.query_one("#feed-url", Input).value.strip()
        status = self.query_one("#feed-status", Static)
        if not url:
            status.update("[red]Enter a URL[/]")
            return
        status.update("[cyan]Discovering feed & language…[/]")
        self.query_one("#feed-add", Button).disabled = True
        self._discover(name, url)

    @work(thread=True)
    def _discover(self, name: str, url: str) -> None:
        try:
            from collections import Counter

            from worldnews.scraper import Scraper, lang_display_name

            scraper = Scraper()
            feed_url, suggested = scraper.discover_feed(url)
            sample = scraper._rss(feed_url, name or suggested)
            langs = Counter(
                (a.get("lang") or "EN").upper() for a in sample if a.get("lang")
            )
            lang = langs.most_common(1)[0][0] if langs else "EN"
            result = {
                "name": name or suggested,
                "url": feed_url,
                "lang": lang,
                "count": len(sample),
                "lang_label": lang_display_name(lang),
            }
            self.app.call_from_thread(self.dismiss, result)
        except Exception as exc:
            def _err() -> None:
                self.query_one("#feed-status", Static).update(f"[red]{exc}[/]")
                self.query_one("#feed-add", Button).disabled = False

            self.app.call_from_thread(_err)


class ManageFeedsScreen(ModalScreen[dict | None]):
    """List / add / remove custom news websites."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
        ("a", "add", "Add"),
    ]

    def __init__(self, custom_feeds) -> None:
        super().__init__()
        self.custom_feeds = custom_feeds
        self._id_map: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="manage-feeds-box", classes="modal-box"):
            yield Label("My news websites", classes="modal-title")
            yield Static(
                "Add any site (any language). Open all to read every story.",
                classes="settings-hint",
            )
            yield OptionList(*self._options(), id="feeds-list")
            yield Static(self._summary(), id="feeds-summary")
            with Horizontal(classes="settings-row"):
                yield Button("Add site", variant="primary", id="mf-add")
                yield Button("Remove", id="mf-remove")
                yield Button("Open all", variant="success", id="mf-open")
                yield Button("Done", id="mf-done")

    def _options(self) -> list[Option]:
        from worldnews.scraper import lang_display_name

        self._id_map = {}
        opts = []
        if not self.custom_feeds.feeds:
            opts.append(Option("(none yet — press Add site)", id="empty"))
            return opts
        for i, f in enumerate(self.custom_feeds.feeds):
            oid = f"f-{i}"
            self._id_map[oid] = i
            lang = (f.get("lang") or "?").upper()
            label = (
                f"{f.get('name', 'Feed')}  ·  {lang_display_name(lang)}\n"
                f"   {f.get('url', '')[:70]}"
            )
            opts.append(Option(label, id=oid))
        return opts

    def _summary(self) -> str:
        n = len(self.custom_feeds.feeds)
        if not n:
            return "0 sources — add a newspaper, blog, or RSS URL"
        langs = sorted(
            {(f.get("lang") or "?").upper() for f in self.custom_feeds.feeds}
        )
        plural = "s" if n != 1 else ""
        return f"{n} source{plural} · languages: {', '.join(langs)}"

    def _refresh(self) -> None:
        ol = self.query_one("#feeds-list", OptionList)
        ol.clear_options()
        for opt in self._options():
            ol.add_option(opt)
        self.query_one("#feeds-summary", Static).update(self._summary())

    def action_add(self) -> None:
        self._add()

    @on(Button.Pressed, "#mf-add")
    def _add(self) -> None:
        self.app.push_screen(AddFeedScreen(), self._on_added)

    def _on_added(self, result: dict | None) -> None:
        if not result:
            return
        ok = self.custom_feeds.add(
            result["name"], result["url"], lang=result.get("lang") or ""
        )
        self._refresh()
        if ok:
            label = result.get("lang_label") or result.get("lang") or "?"
            self.query_one("#feeds-summary", Static).update(
                f"Added [b]{result['name']}[/] · {label} · "
                f"{result.get('count', 0)} stories"
            )
        else:
            self.query_one("#feeds-summary", Static).update(
                "[yellow]Already saved[/]"
            )

    @on(Button.Pressed, "#mf-remove")
    def _remove(self) -> None:
        ol = self.query_one("#feeds-list", OptionList)
        if ol.highlighted is None:
            return
        opt = ol.get_option_at_index(ol.highlighted)
        if not opt or not opt.id or opt.id == "empty":
            return
        idx = self._id_map.get(str(opt.id))
        if idx is None:
            return
        self.custom_feeds.remove(idx)
        self._refresh()

    @on(Button.Pressed, "#mf-open")
    def _open(self) -> None:
        self.dismiss({"open": True, "changed": True})

    @on(Button.Pressed, "#mf-done")
    def _done(self) -> None:
        self.dismiss({"changed": True})
