"""Shared UI widgets for World News CLI."""

from __future__ import annotations

import re
from textual.app import ComposeResult
from textual.containers import Center, Horizontal, Middle, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView, LoadingIndicator, Static

from worldnews.analysis import SentimentAnalyzer, estimate_reading_time
from worldnews.widgets.splash import AsciiSplash

CATEGORIES = [
    ("general", "General"),
    ("anime", "Anime"),
    ("marvel", "Marvel"),
    ("dc", "DC"),
    ("hollywood", "Hollywood"),
    ("bollywood", "Bollywood"),
    ("mollywood", "Mollywood"),
    ("sports", "Sports"),
    ("gaming", "Gaming"),
    ("tech", "Tech"),
    ("business", "Business"),
    ("science", "Science"),
    ("ai", "AI"),
]

SPECIAL_FEEDS = [
    ("all", "All"),
    ("bookmarks", "Bookmarks"),
    ("trending", "Trending"),
    ("breaking", "Breaking"),
    ("offline", "Offline"),
    ("custom", "My Feeds"),
]

PAGE_SIZE = 50

_sentiment = SentimentAnalyzer()


def make_loading_panel(message: str = "Loading…") -> Widget:
    """Centered spinner + caption used as a Textual loading cover."""
    return Center(
        Middle(
            Vertical(
                LoadingIndicator(),
                Label(message, classes="loading-msg"),
                Label("Usually a few seconds…", classes="loading-hint"),
                classes="loading-panel",
            )
        ),
        classes="loading-cover",
    )


class BusyMixin:
    """Toggle Textual's built-in loading cover with a caption."""

    _loading_msg: str = "Loading…"

    def set_busy(self, busy: bool, message: str = "Loading…") -> None:
        self._loading_msg = message or "Loading…"
        # Refresh cover when message changes while already busy
        if busy and getattr(self, "loading", False):
            self.loading = False
        self.loading = busy

    def get_loading_widget(self) -> Widget:
        return make_loading_panel(getattr(self, "_loading_msg", "Loading…"))


class RowLabel(Label):
    """Label that won't trigger Textual's buggy mouse text-select path."""

    ALLOW_SELECT = False


class ArticleItem(ListItem):
    """List row that holds the source-article index."""

    ALLOW_SELECT = False

    def __init__(
        self, label: Label, article_index: int, *, classes: str | None = None
    ) -> None:
        super().__init__(label, classes=classes)
        self.article_index = article_index


class FeedItem(ListItem):
    """Sidebar feed row — no text selection."""

    ALLOW_SELECT = False


class LoadMoreItem(ListItem):
    """Footer row — highlight/Enter loads the next 50 articles."""

    ALLOW_SELECT = False


def sentiment_glyph(article: dict) -> str:
    label, _, _ = _sentiment.analyze(
        f"{article.get('title', '')} {article.get('description', '')}"
    )
    return {"positive": "↑", "negative": "↓"}.get(label, "→")


def short_time(published: str) -> str:
    """Compact list date — never raw-slice RFC822 into 'Fri, 31 J'."""
    if not published:
        return ""
    s = str(published).strip()
    if not s:
        return ""

    dt = None
    # ISO / date-only
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            from datetime import datetime

            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        except Exception:
            dt = None
    if dt is None:
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(s)
        except Exception:
            dt = None
    if dt is not None:
        try:
            return dt.strftime("%d %b")  # e.g. 31 Jul
        except Exception:
            pass

    # "31 Jul 2026" / "Jul 31, 2026" fragments
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\b", s)
    if m:
        return f"{int(m.group(1)):02d} {m.group(2).title()}"
    m = re.search(r"\b([A-Za-z]{3})\s+(\d{1,2})\b", s)
    if m:
        return f"{int(m.group(2)):02d} {m.group(1).title()}"
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return s[:9].rstrip(", ")


def pretty_time(published: str) -> str:
    """Reader/meta date — readable, not a blind [:22] slice."""
    if not published:
        return ""
    s = str(published).strip()
    if not s:
        return ""
    dt = None
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            from datetime import datetime

            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        except Exception:
            dt = None
    if dt is None:
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(s)
        except Exception:
            dt = None
    if dt is not None:
        try:
            return dt.strftime("%d %b %Y")
        except Exception:
            pass
    return short_time(s) or s[:20]


class AppHeader(Static):
    """Top chrome: brand · crumbs · status."""

    crumbs = reactive("Home")
    status = reactive("")

    def compose(self) -> ComposeResult:
        with Horizontal(id="app-header"):
            yield Label("WORLD NEWS", id="header-title")
            yield Label(self.crumbs, id="header-crumbs")
            yield Label(self.status, id="header-status")

    def watch_crumbs(self, value: str) -> None:
        try:
            self.query_one("#header-crumbs", Label).update(value)
        except Exception:
            pass

    def watch_status(self, value: str) -> None:
        try:
            self.query_one("#header-status", Label).update(value)
        except Exception:
            pass


class StatusLine(Static):
    """Helix-like status strip."""

    text = reactive("READY")

    def render(self) -> str:
        return self.text


DEFAULT_KEY_HINTS = (
    "[b]keys[/]  j/k move  Enter open  "
    "[b]a[/] Summarize  [b]e[/] Explain  [b]t[/] Speak  "
    "[b]b[/] Save  [b]o[/] Open  [b]s[/] Settings  [b]?[/] Help  [b]q[/] Quit"
)


class KeyHints(Static):
    """Context-aware footer bindings (always visible folio strip)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(DEFAULT_KEY_HINTS, markup=True, *args, **kwargs)

    def on_mount(self) -> None:
        self.update(DEFAULT_KEY_HINTS)

    def set_hints(self, text: str) -> None:
        self.update(text or DEFAULT_KEY_HINTS)


class Toast(Static):
    """Transient flash notification."""

    def on_mount(self) -> None:
        self.set_timer(2.5, self.remove)


class FeedSidebar(Vertical):
    """Category / special feed picker."""

    class FeedSelected(Message):
        def __init__(self, feed_id: str, label: str) -> None:
            self.feed_id = feed_id
            self.label = label
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(" FEEDS", classes="modal-title")
        items = []
        n_custom = 0
        try:
            n_custom = len(self.app.custom_feeds.feeds)
        except Exception:
            pass
        for fid, label in SPECIAL_FEEDS:
            if fid == "custom" and n_custom:
                label = f"My Feeds ({n_custom})"
            items.append(FeedItem(RowLabel(f"  {label}"), id=f"feed-{fid}"))
        for i, (cid, label) in enumerate(CATEGORIES, start=1):
            shortcut = f"{i}" if i <= 9 else " "
            items.append(FeedItem(RowLabel(f" {shortcut} {label}"), id=f"feed-{cid}"))
        yield ListView(*items, id="feed-list")

    def refresh_custom_label(self) -> None:
        """Update My Feeds row after add/remove."""
        try:
            n = len(self.app.custom_feeds.feeds)
            lv = self.query_one("#feed-list", ListView)
            for child in lv.children:
                if child.id == "feed-custom":
                    lab = f"  My Feeds ({n})" if n else "  My Feeds"
                    for sub in child.query(RowLabel):
                        sub.update(lab)
                    break
        except Exception:
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if item and item.id and item.id.startswith("feed-"):
            fid = item.id[5:]
            label = fid.replace("_", " ").title()
            for sid, lab in SPECIAL_FEEDS + CATEGORIES:
                if sid == fid:
                    label = lab
                    break
            self.post_message(self.FeedSelected(fid, label))

    def select_feed(self, feed_id: str) -> None:
        lv = self.query_one("#feed-list", ListView)
        target = f"feed-{feed_id}"
        for i, child in enumerate(lv.children):
            if child.id == target:
                lv.index = i
                break


class ArticleList(BusyMixin, Vertical):
    """Scrollable article list with unread / bookmark markers."""

    class ArticleHighlighted(Message):
        def __init__(self, index: int, article: dict) -> None:
            self.index = index
            self.article = article
            super().__init__()

    class ArticleOpened(Message):
        def __init__(self, index: int, article: dict) -> None:
            self.index = index
            self.article = article
            super().__init__()

    class NearEnd(Message):
        """Fired when highlight is near the bottom — app may load next page."""

        pass

    articles: list[dict] = []
    bookmarks = None
    settings = None
    _has_more: bool = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="filter-bar"):
            yield Input(placeholder="Filter articles…", id="filter-input")
        with Vertical(id="list-stack", classes="fetching"):
            yield ListView(id="article-list")
            yield AsciiSplash(id="fetch-panel", classes="splash-on", feed_label="news")

    def show_fetching(self, label: str = "news") -> None:
        """Big visible fetch panel — never leave the list blank."""
        self.set_busy(False)
        self.articles = []
        self._has_more = False
        lab = (label or "news").strip() or "news"
        try:
            lv = self.query_one("#article-list", ListView)
            lv.clear()
            lv.display = False
        except Exception:
            pass
        try:
            panel = self.query_one("#fetch-panel", AsciiSplash)
            panel.show_for(lab)
        except Exception:
            pass
        try:
            self.query_one("#list-stack").add_class("fetching")
        except Exception:
            pass

    def hide_fetching(self) -> None:
        try:
            panel = self.query_one("#fetch-panel", AsciiSplash)
            panel.stop()
            panel.remove_class("splash-on")
            panel.display = False
            panel.styles.display = "none"
        except Exception:
            pass
        try:
            lv = self.query_one("#article-list", ListView)
            lv.display = True
            lv.styles.display = "block"
        except Exception:
            pass
        try:
            self.query_one("#list-stack").remove_class("fetching")
        except Exception:
            pass

    def _usable_list_cols(self) -> int:
        """Width of the headline pane — not the full terminal (avoids border bleed)."""
        for node_id in ("#article-list", "#list-stack"):
            try:
                w = int(self.query_one(node_id).size.width)
                if w >= 18:
                    return max(18, w - 2)  # ListItem padding
            except Exception:
                pass
        try:
            w = int(self.size.width)
            if w >= 18:
                return max(18, w - 2)
        except Exception:
            pass
        try:
            w = int(self.app.query_one("#article-pane").size.width)
            if w >= 18:
                return max(18, w - 2)
        except Exception:
            pass
        try:
            # sidebar (~22) + reader (~40%) + chrome — rough middle third
            return max(28, int(self.app.size.width) // 3)
        except Exception:
            return 48

    def _row_label(self, a: dict, i: int) -> ArticleItem:
        from worldnews.text_display import (
            ascii_list_headline,
            display_width,
            needs_ascii_list_label,
            normalize_script_mode,
            pad_display,
            truncate_display,
        )

        title = a.get("title", "") or ""
        source = a.get("source", "?") or "?"
        lang = (a.get("lang") or "").strip().upper()
        url = a.get("url", "")
        is_bm = bool(self.bookmarks and self.bookmarks.has(url))
        is_read = bool(self.settings and self.settings.is_read(url))
        # ASCII-width-stable marks (★/● often paint 2 cells → border bleed)
        mark = "*" if is_bm else ("o" if is_read else "+")
        sent = sentiment_glyph(a)
        when = short_time(a.get("published", ""))
        cols = self._usable_list_cols()

        mode = "safe"
        try:
            mode = normalize_script_mode(
                getattr(self.app, "script_mode", None)
                or getattr(self.settings, "script_mode", "safe")
            )
        except Exception:
            mode = "safe"

        if needs_ascii_list_label(title, lang, mode=mode):
            head = ascii_list_headline(title, lang)
        else:
            head = title

        # Dynamic budgets so the single line never exceeds the pane width
        show_when = bool(when) and cols >= 42
        show_src = cols >= 36
        show_lang = bool(lang) and cols >= 56
        when_bit = f"  {when}" if show_when else ""
        lang_bit = f" [{lang}]" if show_lang else ""
        src_w = 10 if cols >= 56 else (8 if cols >= 44 else 6)
        fixed = (
            display_width(f"{mark} {sent}  ")
            + (src_w + 2 if show_src else 0)
            + display_width(lang_bit)
            + display_width(when_bit)
        )
        title_w = max(8, cols - fixed)

        t = truncate_display(head, title_w)
        if show_src:
            # Pad title only when we have room for a source column
            t = pad_display(t, title_w)
            src = pad_display(truncate_display(source, src_w), src_w)
            line = f"{mark} {sent}  {t}  {src}{lang_bit}{when_bit}"
        else:
            line = f"{mark} {sent}  {t}"

        # Final safety clip (ambiguous glyphs / padding drift)
        if display_width(line) > cols:
            line = truncate_display(line, cols)
        return ArticleItem(RowLabel(line), i)

    def set_articles(
        self,
        arts: list[dict],
        filter_text: str = "",
        *,
        has_more: bool = False,
    ) -> None:
        self.set_busy(False)
        self.hide_fetching()
        self.articles = arts
        self._has_more = has_more
        q = (filter_text or "").strip().lower()
        lv = self.query_one("#article-list", ListView)
        lv.clear()
        items: list[ListItem] = []
        for i, a in enumerate(arts):
            title = a.get("title", "")
            source = a.get("source", "?")
            if q and q not in title.lower() and q not in source.lower():
                continue
            items.append(self._row_label(a, i))
        if not items:
            items.append(FeedItem(RowLabel("  (no articles)")))
        elif has_more:
            items.append(
                LoadMoreItem(RowLabel("  ↓  more…  (Enter / PgDn = next 50)"))
            )
        lv.extend(items)
        try:
            if items and isinstance(items[0], ArticleItem):
                lv.index = 0
                lv.focus()
        except Exception:
            pass

    def append_articles(self, arts: list[dict], *, has_more: bool = False) -> None:
        """Append next page without resetting scroll position."""
        if not arts:
            self._has_more = has_more
            return
        start = len(self.articles)
        self.articles = list(self.articles) + list(arts)
        self._has_more = has_more
        lv = self.query_one("#article-list", ListView)
        # Drop trailing "more" hint if present
        children = list(lv.children)
        if children and isinstance(children[-1], LoadMoreItem):
            children[-1].remove()
        items = [self._row_label(a, start + i) for i, a in enumerate(arts)]
        if has_more:
            items.append(
                LoadMoreItem(RowLabel("  ↓  more…  (Enter / PgDn = next 50)"))
            )
        lv.extend(items)

    def show_filter(self, visible: bool = True) -> None:
        bar = self.query_one("#filter-bar")
        bar.set_class(visible, "visible")
        if visible:
            self.query_one("#filter-input", Input).focus()

    def current_article(self) -> tuple[int, dict | None]:
        lv = self.query_one("#article-list", ListView)
        child = lv.highlighted_child
        if isinstance(child, ArticleItem):
            i = child.article_index
            if 0 <= i < len(self.articles):
                return i, self.articles[i]
        return -1, None

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, ArticleItem) and 0 <= item.article_index < len(self.articles):
            i = item.article_index
            self.post_message(self.ArticleHighlighted(i, self.articles[i]))
            # Near end of loaded page → ask app for next 50
            if self._has_more and i >= max(0, len(self.articles) - 5):
                self.post_message(self.NearEnd())
        elif isinstance(item, LoadMoreItem) and self._has_more:
            self.post_message(self.NearEnd())

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, ArticleItem) and 0 <= item.article_index < len(self.articles):
            i = item.article_index
            self.post_message(self.ArticleOpened(i, self.articles[i]))
        elif isinstance(item, LoadMoreItem) and self._has_more:
            self.post_message(self.NearEnd())

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self.set_articles(self.articles, event.value)

    def on_resize(self) -> None:
        """Re-fit row labels when the middle pane width changes."""
        if not self.articles:
            return
        try:
            w = int(self.size.width)
        except Exception:
            return
        prev = getattr(self, "_last_list_w", 0)
        self._last_list_w = w
        if prev and abs(prev - w) < 3:
            return
        try:
            filt = ""
            try:
                filt = self.query_one("#filter-input", Input).value
            except Exception:
                pass
            idx = None
            try:
                idx = self.query_one("#article-list", ListView).index
            except Exception:
                pass
            self.set_articles(self.articles, filt, has_more=self._has_more)
            if idx is not None:
                try:
                    self.query_one("#article-list", ListView).index = idx
                except Exception:
                    pass
        except Exception:
            pass


class ArticleReader(BusyMixin, Vertical):
    """Premium article pane: hero image, title, meta, body, actions."""

    class SummarizePressed(Message):
        pass

    class ExplainPressed(Message):
        pass

    class SpeakPressed(Message):
        pass

    class BookmarkPressed(Message):
        pass

    class BackPressed(Message):
        """Return to headline list on phone / narrow reading layout."""

    bookmarks = None

    def compose(self) -> ComposeResult:
        from textual.widgets import Button

        with Vertical(id="reader-chrome"):
            yield Label("ARTICLE", id="reader-eyebrow")
            with VerticalScroll(id="reader-scroll"):
                with Vertical(id="reader-hero"):
                    yield Static("", id="reader-image")
                yield Static("Select a headline", id="reader-title")
                yield Static(
                    "Pick a story from the list to preview it here.",
                    id="reader-meta",
                )
                yield Static("─" * 40, id="reader-rule")
                # Static (not Markdown) — Markdown reflows on every scroll and flickers
                yield Static(
                    "Use j/k to move, Enter to focus the reader,\n"
                    "or wait for headlines to finish loading.",
                    id="reader-body",
                )
            with Horizontal(id="reader-actions"):
                yield Button("← Back", id="btn-back", classes="phone-back")
                yield Button("Summarize", id="btn-summarize")
                yield Button("Explain", id="btn-explain")
                yield Button("Speak", id="btn-speak")
                yield Button("Save", id="btn-bookmark")
                yield Button("Open", id="btn-open")

    _ACTION_BTNS = {
        "summarize": "btn-summarize",
        "explain": "btn-explain",
        "speak": "btn-speak",
        "save": "btn-bookmark",
        "open": "btn-open",
    }

    def set_active_action(self, action: str | None) -> None:
        """Highlight the reader button for the current activity (Speak / AI / …)."""
        from textual.widgets import Button

        self._active_action = action
        for name, bid in self._ACTION_BTNS.items():
            try:
                btn = self.query_one(f"#{bid}", Button)
            except Exception:
                continue
            on = action is not None and name == action
            btn.set_class(on, "action-active")
            try:
                btn.variant = "primary" if on else "default"
            except Exception:
                pass
            if name == "speak":
                try:
                    btn.label = "Stop" if on else "Speak"
                except Exception:
                    pass
            if on:
                try:
                    btn.focus()
                except Exception:
                    pass

    def on_button_pressed(self, event) -> None:
        bid = event.button.id
        if bid == "btn-back":
            event.stop()
            self.post_message(self.BackPressed())
        elif bid == "btn-summarize":
            event.stop()
            self.post_message(self.SummarizePressed())
        elif bid == "btn-explain":
            event.stop()
            self.post_message(self.ExplainPressed())
        elif bid == "btn-speak":
            event.stop()
            self.post_message(self.SpeakPressed())
        elif bid == "btn-bookmark":
            event.stop()
            self.post_message(self.BookmarkPressed())
        elif bid == "btn-open":
            event.stop()
            self.app.action_open_browser()

    def set_back_visible(self, visible: bool) -> None:
        """Show ← Back only when list is hidden (phone/narrow reading)."""
        try:
            btn = self.query_one("#btn-back")
            btn.display = visible
        except Exception:
            pass

    def show_fetching(self, label: str = "news") -> None:
        """Reader-side fetch placeholder so the pane isn't empty."""
        # Avoid blank loading cover — show copy in the reader itself
        self.set_busy(False)
        lab = (label or "news").strip() or "news"
        try:
            img = self.query_one("#reader-image", Static)
            img.update("")
            img.display = False
            self.query_one("#reader-eyebrow", Label).update("LOADING")
            self.query_one("#reader-title", Static).update(f"Fetching {lab}")
            self.query_one("#reader-meta", Static).update(
                "Gathering headlines from RSS sources…"
            )
            rule = self.query_one("#reader-rule", Static)
            rule.display = True
            rule.update("─" * 40)
            self.query_one("#reader-body", Static).update(
                "Hang tight — stories will fill the list on the left,\n"
                "then the first headline opens here automatically.\n\n"
                "First load can take a few seconds depending on the network.\n\n"
                "····  ····  ····  ····  ····"
            )
            self._shown_url = None
            self._body_plain = ""
        except Exception:
            pass

    def show_article(self, article: dict | None, image_ansi: str = "") -> None:
        self.set_busy(False)
        from rich.markup import escape
        from rich.text import Text

        img = self.query_one("#reader-image", Static)
        title_w = self.query_one("#reader-title", Static)
        meta_w = self.query_one("#reader-meta", Static)
        body_w = self.query_one("#reader-body", Static)
        rule = self.query_one("#reader-rule", Static)
        eye = self.query_one("#reader-eyebrow", Label)

        # Preserve scroll position when refreshing the same article (e.g. image paint)
        scroll = self.query_one("#reader-scroll")
        keep_y = None
        try:
            prev_url = getattr(self, "_shown_url", None)
            if article and article.get("url") and article.get("url") == prev_url:
                keep_y = scroll.scroll_y
        except Exception:
            keep_y = None

        if not article:
            eye.update("ARTICLE")
            img.update("")
            img.display = False
            title_w.update("Select a headline")
            meta_w.update("Pick a story from the list to preview it here.")
            rule.display = False
            body_w.update(
                "Use j/k to move, Enter to focus the reader, "
                "or click Summarize once a story is selected."
            )
            self._shown_url = None
            return

        rule.display = True
        source = article.get("source", "") or "Unknown"
        eye.update(f"ARTICLE  ·  {source.upper()}")

        if image_ansi:
            img.update(Text.from_ansi(image_ansi))
            img.display = True
            try:
                n_lines = max(1, image_ansi.count("\n") + 1)
                img.styles.height = n_lines
                img.styles.min_height = n_lines
                img.styles.width = "100%"
            except Exception:
                pass
        else:
            # Don't clear an existing image on body-only refresh of same article
            if keep_y is None or not img.display:
                img.update("")
                img.display = False
                try:
                    img.styles.height = "auto"
                    img.styles.width = "100%"
                except Exception:
                    pass

        from worldnews.text_display import (
            ascii_list_headline,
            needs_complex_layout,
            normalize_nfc,
            normalize_script_mode,
            script_label,
            should_hide_in_tui,
            soft_wrap_display,
        )

        title = article.get("title", "Untitled") or "Untitled"
        published = article.get("published", "") or ""
        author = article.get("author", "") or ""
        desc = article.get("description", "") or ""
        url = article.get("url", "") or ""
        has_img = bool(article.get("image_url"))
        rt = estimate_reading_time(desc)
        sent = sentiment_glyph(article)
        saved = bool(self.bookmarks and url and self.bookmarks.has(url))
        lang = (article.get("lang") or "").strip().upper()

        try:
            pane_w = max(20, int(self.size.width) - 4)
        except Exception:
            pane_w = 60

        mode = "safe"
        try:
            mode = normalize_script_mode(
                getattr(self.app, "script_mode", None)
                or (
                    getattr(self.app, "settings", None)
                    and getattr(self.app.settings, "script_mode", "safe")
                )
            )
        except Exception:
            mode = "safe"

        sample = f"{title}\n{desc}"
        hide_hostile = should_hide_in_tui(sample, lang, mode)
        complex_body = needs_complex_layout(sample, lang)
        lang_name = script_label(lang, sample)

        if hide_hostile:
            title_w.update(ascii_list_headline(title, lang))
        elif complex_body:
            title_w.update(soft_wrap_display(normalize_nfc(title), pane_w))
        else:
            title_w.update(title)

        bits = []
        if source:
            bits.append(f"[b]{escape(source)}[/]")
        if lang:
            from worldnews.scraper import lang_display_name

            bits.append(f"lang {lang_display_name(lang)}")
        if published:
            bits.append(escape(pretty_time(published)))
        if author:
            bits.append(escape(author))
        bits.append(rt)
        bits.append(f"tone {sent}")
        if saved:
            bits.append("★ saved")
        elif has_img and not image_ansi and keep_y is None:
            bits.append("loading image…")
        if article.get("body_fetched") and len(desc) > 600:
            bits.append("full story")
        if hide_hostile:
            bits.append("t Speak · o browser")
        meta_w.update("  ·  ".join(bits))

        from worldnews.images import format_article_body

        body = format_article_body(desc)
        plain = body.replace("**", "")
        if hide_hostile:
            tip = (
                f"[{ascii_list_headline(title, lang)}]\n\n"
                f"{lang_name} text cannot render cleanly in most terminals "
                "(Windows Terminal included).\n\n"
                "Press t to hear the full story aloud "
                "(works for any language).\n"
                "Press o to open it in your browser.\n"
                "Settings → Scripts → native shows glyphs "
                "(may still overlap).\n"
            )
            display_plain = tip
        elif complex_body:
            display_plain = soft_wrap_display(normalize_nfc(plain), pane_w)
        else:
            display_plain = plain
        if url:
            plain = f"{plain}\n\n↗ {url}"
            display_plain = f"{display_plain}\n\n↗ {url}"
        body_w.update(escape(display_plain))

        try:
            from textual.widgets import Button

            btn = self.query_one("#btn-bookmark", Button)
            btn.label = "Saved ★" if saved else "Save"
        except Exception:
            pass

        self._shown_url = url
        self._body_plain = plain  # unwrapped — used for Speak / TTS (audio)
        self._hide_hostile_display = hide_hostile
        if keep_y is not None:
            try:
                self.call_after_refresh(
                    lambda: scroll.scroll_to(y=keep_y, animate=False)
                )
            except Exception:
                pass

    def update_image_only(self, image_ansi: str) -> None:
        """Swap hero image without resetting scroll or reflowing the body."""
        try:
            scroll = self.query_one("#reader-scroll")
            keep_y = scroll.scroll_y
            img = self.query_one("#reader-image", Static)
            if not image_ansi:
                return
            from rich.text import Text

            img.update(Text.from_ansi(image_ansi))
            img.display = True
            n_lines = max(1, image_ansi.count("\n") + 1)
            img.styles.height = n_lines
            img.styles.min_height = n_lines
            img.styles.width = "100%"
            self.call_after_refresh(
                lambda: scroll.scroll_to(y=keep_y, animate=False)
            )
        except Exception:
            pass

    def body_plain_text(self) -> str:
        """Plain article body currently shown (no URL footer)."""
        plain = getattr(self, "_body_plain", "") or ""
        # Drop link footer from speak/highlight
        if "\n\n↗ " in plain:
            plain = plain.split("\n\n↗ ", 1)[0]
        return plain.strip()

    def set_reading_highlight(self, sentences: list[str], index: int) -> None:
        """Highlight the spoken sentence inside the existing body (no layout swap)."""
        if not sentences:
            return
        # Never paint terminal-hostile glyphs during Speak — they bleed the layout
        if getattr(self, "_hide_hostile_display", False):
            try:
                eye = self.query_one("#reader-eyebrow", Label)
                eye.update(f"SPEAKING  ·  {index + 1}/{len(sentences)}")
                self.set_active_action("speak")
                # Progress-only body — no native glyphs (avoids bleed)
                body_w = self.query_one("#reader-body", Static)
                body_w.update(
                    f"Listening… part {index + 1} of {len(sentences)}\n\n"
                    "Press t again to stop.\n"
                    "Press o to open the story in your browser."
                )
            except Exception:
                pass
            return
        index = max(0, min(index, len(sentences) - 1))
        current = (sentences[index] or "").strip()
        plain = self.body_plain_text()
        if not plain:
            return

        from rich.text import Text
        from worldnews.tts import locate_sentence_in_body

        # Keep Speak button visually active while TTS runs
        try:
            self.set_active_action("speak")
        except Exception:
            pass

        pos, hit = locate_sentence_in_body(plain, current)

        try:
            eye = self.query_one("#reader-eyebrow", Label)
            eye.update(f"SPEAKING  ·  {index + 1}/{len(sentences)}")
            body_w = self.query_one("#reader-body", Static)
            if pos < 0 or not hit:
                # Still show progress even if span match failed
                return
            before = plain[:pos]
            mid = plain[pos : pos + len(hit)]
            after = plain[pos + len(hit) :]
            styled = Text()
            if before:
                styled.append(before, style="dim")
            # Use theme primary if possible; vermillion fallback matches newsroom
            styled.append(mid, style="bold reverse #c45c26")
            if after:
                styled.append(after)
            full = getattr(self, "_body_plain", "") or ""
            if "\n\n↗ " in full:
                styled.append("\n\n↗ " + full.split("\n\n↗ ", 1)[1])
            body_w.update(styled)

            scroll = self.query_one("#reader-scroll")
            frac = pos / max(1, len(plain))
            max_y = getattr(scroll, "max_scroll_y", 0) or 0
            scroll.scroll_to(y=int(frac * max_y), animate=False)
        except Exception:
            pass

    def clear_reading_highlight(self, article: dict | None = None) -> None:
        """Restore normal body after Speak stops."""
        try:
            self.set_active_action(None)
        except Exception:
            pass
        try:
            eye = self.query_one("#reader-eyebrow", Label)
            source = (article or {}).get("source", "") or "Unknown"
            if article:
                eye.update(f"ARTICLE  ·  {source.upper()}")
                # Re-run show_article path so safe/plain stay Latin-only
                self.show_article(article)
            else:
                eye.update("ARTICLE")
        except Exception:
            pass
