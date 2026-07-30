"""World News CLI — Textual application."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from textual.widgets import Input, ListView
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical

from worldnews import __version__
from worldnews.ai import ai
from worldnews.analysis import SentimentAnalyzer
from worldnews.images import optional_render
from worldnews.scraper import NEWS_SOURCES, Scraper
from worldnews.screens import (
    AIChatScreen,
    AIProviderScreen,
    AIResultModal,
    AddFeedScreen,
    CommandPaletteScreen,
    CompareScreen,
    HelpScreen,
    ManageFeedsScreen,
    SearchScreen,
    SettingsScreen,
    SummaryScreen,
    TrendingScreen,
    VoiceSetupScreen,
)
from worldnews.storage import Bookmarks, Cache, CustomFeeds, Exporter, SearchHistory, Settings
from worldnews.themes import DEFAULT_THEME, THEMES, register_themes
from worldnews.tts import (
    article_speech_sentences,
    article_speech_text,
    tts_engine,
    voice_cfg,
)
from worldnews.widgets import (
    CATEGORIES,
    PAGE_SIZE,
    SPECIAL_FEEDS,
    AppHeader,
    ArticleList,
    ArticleReader,
    DEFAULT_KEY_HINTS,
    FeedSidebar,
    KeyHints,
    StatusLine,
    Toast,
)
from worldnews.platform import open_url

CSS_PATH = Path(__file__).parent / "styles" / "app.tcss"

STOP = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "is", "are", "was", "were", "be", "been", "from", "as", "that",
    "this", "it", "its", "into", "over", "after", "before", "about", "news",
    "have", "has", "had", "will", "would", "could", "should", "may", "might",
    "can", "shall", "not", "no", "so", "than", "too", "very", "just", "up",
    "out", "if", "when", "where", "who", "which", "what", "how", "why",
    "here", "there", "all", "each", "every", "both", "few", "more", "most",
    "other", "some", "such", "only", "own", "same", "new", "says", "said",
    "latest", "today", "description", "images", "image", "photo", "video",
    "read", "also", "their", "they", "them", "his", "her", "our", "your",
    "first", "last", "next", "year", "years", "time", "week", "month", "day",
    "days", "best", "during", "against", "while", "still", "even", "much",
    "many", "being", "does", "did", "done", "get", "got", "make", "made",
    "take", "taken", "come", "came", "go", "goes", "went", "one", "two",
    "three", "via", "per", "amid", "among", "across", "under", "above",
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday",
}


class WorldNewsApp(App):
    """Full-screen news reader TUI."""

    CSS_PATH = CSS_PATH
    TITLE = "World News CLI"
    # Avoid Textual mouse text-select crash on orphan Label parents in ListView.
    ALLOW_SELECT = False
    BINDINGS = [
        Binding("q", "quit_or_back", "Quit", show=False),
        Binding("j", "move_down", "Down", show=False),
        Binding("k", "move_up", "Up", show=False),
        Binding("t", "speak", "Speak", show=False, priority=True),
        Binding("s", "settings", "Settings", show=False, priority=True),
        Binding("question_mark", "help", "Help", show=False, priority=True),
        Binding("ctrl+p", "palette", "Palette", show=False, priority=True),
        Binding("slash", "filter", "Filter", show=False),
        Binding("b", "bookmark", "Bookmark", show=False),
        Binding("o", "open_browser", "Open", show=False),
        Binding("a", "ai_summarize", "Summarize", show=False),
        Binding("e", "ai_explain", "Explain", show=False),
        Binding("plus", "manage_feeds", "Feeds", show=False),
        Binding("equals", "manage_feeds", "Feeds", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("i", "toggle_images", "Images", show=False),
        Binding("left_square_bracket", "prev_feed", "Prev", show=False),
        Binding("right_square_bracket", "next_feed", "Next", show=False),
        Binding("escape", "clear_filter", "Esc", show=False),
        Binding("pagedown", "load_more", "More", show=False),
        Binding("n", "load_more", "More", show=False),
        *[Binding(str(n), f"jump_cat_{n}", show=False) for n in range(1, 10)],
    ]

    def __init__(
        self,
        start_feed: str | None = None,
        start_mode: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.scraper = Scraper()
        self.cache = Cache()
        self.bookmarks = Bookmarks()
        self.settings = Settings()
        self.search_history = SearchHistory()
        self.custom_feeds = CustomFeeds()
        self.sentiment = SentimentAnalyzer()
        self.current_feed = start_feed or "general"
        self.current_label = "General"
        for sid, lab in SPECIAL_FEEDS + CATEGORIES:
            if sid == self.current_feed:
                self.current_label = lab
                break
        self.articles: list[dict] = []
        self._pool: list[dict] = []  # full fetched list (for paging)
        self._visible_count = 0
        self._loading_more = False
        self.selected: dict | None = None
        self.busy = False
        self.start_mode = start_mode
        self._feed_order = [f[0] for f in SPECIAL_FEEDS] + [c[0] for c in CATEGORIES]
        self._image_bytes: bytes | None = None
        self._image_url: str = ""
        self._speak_sentences: list | None = None

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Horizontal(id="body"):
            yield FeedSidebar(id="sidebar")
            with Vertical(id="article-pane"):
                yield ArticleList(id="articles")
            with Vertical(id="reader-pane"):
                yield ArticleReader(id="reader")
        with Vertical(id="folio"):
            yield StatusLine(id="statusline")
            yield KeyHints(id="keyhints")

    def on_mount(self) -> None:
        register_themes(self)
        # Always re-register so custom themes stay available after CSS reloads
        theme = self.settings.theme if self.settings.theme in THEMES else DEFAULT_THEME
        if theme not in self.available_themes:
            register_themes(self)
        self.theme = theme
        al = self.query_one(ArticleList)
        al.bookmarks = self.bookmarks
        al.settings = self.settings
        reader = self.query_one(ArticleReader)
        reader.bookmarks = self.bookmarks
        self._apply_density()
        self._set_status(f"v{__version__} · ready")
        self.query_one(FeedSidebar).select_feed(self.current_feed)
        self.load_feed(self.current_feed, self.current_label)
        if self.start_mode == "chat":
            self.push_screen(AIChatScreen())
        elif self.start_mode == "summary":
            self.call_after_refresh(self.action_summary)
        elif self.start_mode == "offline":
            self.load_feed("offline", "Offline")
        self.set_interval(1.0, self._layout_adapt)

    def _layout_adapt(self) -> None:
        """Responsive workbench for desktop → Termux phone widths."""
        try:
            width = int(self.size.width)
            height = int(self.size.height)
            body = self.query_one("#body")
            sidebar = self.query_one("#sidebar")
            reader = self.query_one("#reader-pane")
            articles = self.query_one("#article-pane")
            hints = self.query_one(KeyHints)
            header = self.query_one(AppHeader)
        except Exception:
            return

        # Breakpoints tuned for Termux / JuiceSSH / a-Shell (~40–80 cols)
        narrow = width < 100  # dual-pane cramped → list-first
        phone = width < 84  # hide sidebar; single-column
        tiny = width < 56  # ultra-narrow
        short = height < 22

        for cls, on in (
            ("narrow", narrow),
            ("phone", phone),
            ("tiny", tiny),
            ("short", short),
        ):
            # #body drives workbench layout; App.* drives modal CSS (no @media in TCSS)
            body.set_class(on, cls)
            self.set_class(on, cls)

        reading = "reading" in body.classes
        # Sidebar: hidden on phone / compact density / user preference
        want_compact = (
            self.settings.density == "compact"
            or phone
            or not getattr(self.settings, "show_sidebar", True)
        )
        has_compact = "compact" in sidebar.classes
        if want_compact and not has_compact:
            sidebar.add_class("compact")
        elif not want_compact and has_compact:
            sidebar.remove_class("compact")

        # Single-column phone: either LIST or READER, never both
        if phone:
            if reading and self.selected:
                if "hidden-narrow" not in articles.classes:
                    articles.add_class("hidden-narrow")
                if "hidden-narrow" in reader.classes:
                    reader.remove_class("hidden-narrow")
            else:
                if "hidden-narrow" in articles.classes:
                    articles.remove_class("hidden-narrow")
                if "hidden-narrow" not in reader.classes:
                    reader.add_class("hidden-narrow")
        elif narrow:
            if "hidden-narrow" in articles.classes:
                articles.remove_class("hidden-narrow")
            if self.selected:
                if "hidden-narrow" in reader.classes:
                    reader.remove_class("hidden-narrow")
            else:
                if "hidden-narrow" not in reader.classes:
                    reader.add_class("hidden-narrow")
        else:
            if "hidden-narrow" in articles.classes:
                articles.remove_class("hidden-narrow")
            if "hidden-narrow" in reader.classes:
                reader.remove_class("hidden-narrow")
            if reading:
                body.remove_class("reading")

        # Header / keyhints scale with chrome budget
        try:
            if phone:
                header.crumbs = self.current_label
            elif not getattr(header, "crumbs", "").startswith("World"):
                header.crumbs = f"World › {self.current_label}"
        except Exception:
            pass

        if tiny:
            short_hints = "[b]j/k[/] [b]Enter[/] [b]Esc/Back[/] [b][/]/] [b]s[/] [b]?[/]"
        elif phone:
            short_hints = (
                "[b]keys[/] j/k  Enter open  Esc/Back=list  "
                "[ ] feed  a AI  t Speak  s Set  ?"
            )
        elif narrow and reading:
            short_hints = (
                "[b]keys[/] j/k  Enter open  Esc/Back=list  "
                "a Summarize  t Speak  s Settings  ?"
            )
        else:
            short_hints = DEFAULT_KEY_HINTS
        try:
            if getattr(hints, "_last_adapt", None) != short_hints:
                hints.set_hints(short_hints)
                hints._last_adapt = short_hints  # type: ignore[attr-defined]
        except Exception:
            pass

        # ← Back when in reading mode (list replaced by full reader)
        try:
            self.query_one(ArticleReader).set_back_visible(reading)
        except Exception:
            pass

        # One-shot tip the first time we detect phone width
        if phone and not getattr(self, "_phone_tip_shown", False):
            self._phone_tip_shown = True
            try:
                self.toast(
                    "Phone layout: Enter=read · Esc/Back=list · [ ]=feeds",
                    "info",
                )
            except Exception:
                pass

    def _enter_reading_mode(self) -> None:
        """Phone/narrow: full-width reader."""
        try:
            body = self.query_one("#body")
            if int(self.size.width) < 100:
                body.add_class("reading")
                self._layout_adapt()
        except Exception:
            pass

    def _exit_reading_mode(self) -> None:
        try:
            body = self.query_one("#body")
            if "reading" in body.classes:
                body.remove_class("reading")
            self._layout_adapt()
            try:
                self.query_one("#article-list", ListView).focus()
            except Exception:
                pass
        except Exception:
            pass

    def _apply_density(self) -> None:
        self._layout_adapt()

    def _set_status(self, text: str) -> None:
        self.query_one(StatusLine).text = text

    def _set_crumbs(self, text: str) -> None:
        self.query_one(AppHeader).crumbs = text

    def _set_header_status(self, text: str) -> None:
        self.query_one(AppHeader).status = text

    def _hints(self, text: str) -> None:
        self.query_one(KeyHints).set_hints(text)

    def toast(self, message: str, kind: str = "info") -> None:
        t = Toast(message)
        t.add_class(f"toast-{kind}")
        self.mount(t)

    def _busy_list(self, on: bool, message: str = "Loading…") -> None:
        try:
            self.query_one(ArticleList).set_busy(on, message)
        except Exception:
            pass

    def _busy_reader(self, on: bool, message: str = "Loading…") -> None:
        try:
            self.query_one(ArticleReader).set_busy(on, message)
        except Exception:
            pass

    def _show_fetching(self, label: str) -> None:
        """Visible fetch state in list + reader (not a blank screen)."""
        self.selected = None
        try:
            self.query_one("#body").remove_class("reading")
        except Exception:
            pass
        # Clear any leftover loading overlays first
        self._busy_list(False)
        self._busy_reader(False)
        try:
            self.query_one(ArticleList).show_fetching(label)
        except Exception:
            pass
        try:
            self.query_one(ArticleReader).show_fetching(label)
        except Exception:
            pass
        self._set_status(f"FETCHING · {label}…")
        self._set_header_status("fetching…")
        try:
            self._layout_adapt()
            self.refresh()
        except Exception:
            pass

    # ── data loading ──────────────────────────────────────────────

    def load_feed(self, feed_id: str, label: str) -> None:
        self.current_feed = feed_id
        self.current_label = label
        self._set_crumbs(f"World › {label}")
        self._hints(DEFAULT_KEY_HINTS)
        if feed_id == "bookmarks":
            self._busy_list(False)
            self._busy_reader(False)
            self.articles = list(self.bookmarks.data)
            self._apply_articles(cached=True)
            return
        if feed_id == "custom":
            self._show_fetching("My Feeds")
            self._fetch_custom()
            return
        if feed_id == "offline":
            self._show_fetching("Offline")
            self._load_offline()
            return
        if feed_id == "trending":
            self._show_fetching("Trending")
            self.action_trending()
            return
        if feed_id == "breaking":
            self._show_fetching(label)
            self._fetch_breaking()
            return
        self._show_fetching(label)
        self._fetch_feed(feed_id, label)

    @work(exclusive=True, thread=True)
    def _fetch_feed(self, feed_id: str, label: str) -> None:
        self.call_from_thread(self._set_status, f"FETCHING · {label}…")
        self.call_from_thread(self._set_header_status, "fetching…")
        arts: list[dict] = []
        cached = False
        try:
            if feed_id == "all":
                for c in ("general", "anime", "marvel", "tech", "sports", "science", "gaming", "ai"):
                    chunk = self.cache.get(c)
                    if chunk is None:
                        chunk = self.scraper.fetch(c)
                        self.cache.set(c, chunk)
                    arts.extend(chunk[:3])
                if self.custom_feeds.feeds:
                    # Include ALL custom stories in All (any language)
                    arts.extend(self.custom_feeds.fetch(self.scraper))
            else:
                arts = self.cache.get(feed_id) or []
                if arts:
                    cached = True
                else:
                    arts = self.scraper.fetch(feed_id)
                    self.cache.set(feed_id, arts)
        except Exception as exc:
            self.call_from_thread(self.toast, f"Fetch error: {exc}", "error")
            arts = self.cache.get_stale(feed_id) or []
            cached = True
        self.articles = arts
        self.call_from_thread(self._apply_articles, cached)

    @work(exclusive=True, thread=True)
    def _fetch_custom(self) -> None:
        self.call_from_thread(self._set_status, "FETCHING · My Feeds…")
        if not self.custom_feeds.feeds:
            self.articles = []
            self.call_from_thread(self._apply_articles, True)
            self.call_from_thread(
                self.toast,
                "No custom feeds yet — Ctrl+P → add-feed",
                "warning",
            )
            return
        try:
            arts = self.custom_feeds.fetch(self.scraper)
        except Exception as exc:
            self.call_from_thread(self.toast, f"My Feeds error: {exc}", "error")
            arts = []
        self.articles = arts
        self.call_from_thread(self._apply_articles, False)

    def _apply_articles(self, cached: bool = False) -> None:
        self._busy_list(False)
        self._busy_reader(False)
        self._pool = list(self.articles)
        self._visible_count = min(PAGE_SIZE, len(self._pool))
        self._loading_more = False
        visible = self._pool[: self._visible_count]
        self.articles = visible
        al = self.query_one(ArticleList)
        has_more = self._visible_count < len(self._pool)
        al.set_articles(visible, has_more=has_more)
        tag = "cache" if cached else "live"
        shown = f"{self._visible_count}/{len(self._pool)}" if has_more else str(len(self._pool))
        self._set_status(
            f"LIST · {self.current_label} · {shown} arts · {tag}"
        )
        self._set_header_status(
            f"{shown} articles" + (" · scroll for more" if has_more else "")
        )
        if visible:
            self.selected = visible[0]
            self.query_one(ArticleReader).show_article(self.selected)
            self._busy_reader(True, "Loading story…")
            self._enrich_and_image(self.selected, 0)
        else:
            self.selected = None
            self.query_one(ArticleReader).show_article(None)

    def load_more_articles(self) -> None:
        """Append next PAGE_SIZE from pool (infinite scroll)."""
        if self._loading_more:
            return
        if self._visible_count >= len(self._pool):
            return
        self._loading_more = True
        start = self._visible_count
        self._visible_count = min(start + PAGE_SIZE, len(self._pool))
        chunk = self._pool[start : self._visible_count]
        has_more = self._visible_count < len(self._pool)
        al = self.query_one(ArticleList)
        al.append_articles(chunk, has_more=has_more)
        self.articles = self._pool[: self._visible_count]
        shown = f"{self._visible_count}/{len(self._pool)}"
        self._set_status(f"LIST · {self.current_label} · {shown} arts")
        self._set_header_status(
            f"{shown} articles" + (" · scroll for more" if has_more else "")
        )
        self._loading_more = False

    def _load_offline(self) -> None:
        arts: list[dict] = []
        for key in self.cache.keys():
            chunk = self.cache.get_stale(key) or []
            arts.extend(chunk)
        # also bookmarks
        arts.extend(self.bookmarks.data)
        seen = set()
        uniq = []
        for a in arts:
            u = a.get("url")
            if u and u not in seen:
                seen.add(u)
                uniq.append(a)
        self.articles = uniq
        self._apply_articles(cached=True)
        self.toast(f"Offline: {len(uniq)} articles", "success")

    @work(exclusive=True, thread=True)
    def _fetch_breaking(self) -> None:
        self.call_from_thread(self._set_status, "FETCHING · Breaking…")
        arts = self.cache.get("general") or self.scraper.fetch("general")
        self.cache.set("general", arts)
        # Prefer recent-ish items (first half of feed = "breaking" heuristic)
        self.articles = arts[:15]
        self.call_from_thread(self._apply_articles, False)
        self.call_from_thread(self.toast, "Breaking headlines loaded", "success")

    # ── events ────────────────────────────────────────────────────

    @on(FeedSidebar.FeedSelected)
    def on_feed(self, event: FeedSidebar.FeedSelected) -> None:
        self.load_feed(event.feed_id, event.label)

    @on(ArticleList.NearEnd)
    def on_near_end(self, _event: ArticleList.NearEnd) -> None:
        self.load_more_articles()

    def action_load_more(self) -> None:
        """PgDn / n — load next 50 headlines."""
        self.load_more_articles()

    @on(ArticleList.ArticleHighlighted)
    def on_highlight(self, event: ArticleList.ArticleHighlighted) -> None:
        self.selected = event.article
        if self.size.width >= 100:
            reader = self.query_one(ArticleReader)
            reader.show_article(event.article)
            # Soft spinner: keep title visible under a light cover for enrich/image
            self._busy_reader(True, "Fetching full story…")
            self._enrich_and_image(event.article, event.index)

    @on(ArticleList.ArticleOpened)
    def on_opened(self, event: ArticleList.ArticleOpened) -> None:
        self.selected = event.article
        url = event.article.get("url", "")
        self.settings.mark_read(url)
        reader = self.query_one(ArticleReader)
        reader.show_article(event.article)
        self._busy_reader(True, "Fetching full story…")
        self._enrich_and_image(event.article, event.index)
        self._enter_reading_mode()
        try:
            reader.focus()
        except Exception:
            pass

    def _reader_image_size(self) -> tuple[int, int]:
        """Columns × lines for a full-bleed article hero (after layout)."""
        w = 0
        for sel in ("#reader-scroll", "#reader-pane", "#reader"):
            try:
                w = int(self.query_one(sel).size.width)
                if w >= 20:
                    break
            except Exception:
                continue
        term_w = int(self.size.width)
        term_h = int(self.size.height)
        if w < 20:
            w = max(24, term_w - (0 if term_w < 84 else 22))
        # Phone: use almost full width, shorter hero
        if term_w < 84:
            exact_w = max(18, min(w - 1, term_w - 2))
            max_lines = max(6, min(14, int(term_h * 0.28)))
        else:
            exact_w = max(40, w - 2)
            max_lines = max(14, min(32, int(term_h * 0.38)))
        return exact_w, max_lines

    def _paint_selected_image(self, article: dict | None = None) -> None:
        """Render cached image bytes to the current reader width (scroll-safe)."""
        article = article or self.selected
        if not article:
            return
        ansi = ""
        exact_w, max_lines = self._reader_image_size()
        # Skip re-render if width barely changed (avoids flicker while reading)
        prev_w = getattr(self, "_image_paint_w", 0)
        if (
            self._image_bytes
            and prev_w
            and abs(prev_w - exact_w) < 3
            and getattr(self, "_image_painted_url", "") == (article.get("url") or "")
        ):
            return
        if self._image_bytes:
            ansi = optional_render(
                self._image_bytes, width=exact_w, height=max_lines
            )
            self._image_paint_w = exact_w
            self._image_painted_url = article.get("url") or ""
        try:
            reader = self.query_one(ArticleReader)
            if ansi and getattr(reader, "_shown_url", None) == article.get("url"):
                reader.update_image_only(ansi)
            else:
                reader.show_article(article, image_ansi=ansi)
        except Exception:
            pass

    def on_resize(self, event) -> None:
        """Re-bleed hero image only on real terminal resizes — not while scrolling."""
        if not (self._image_bytes and self.selected):
            return
        try:
            w = int(self.size.width)
            prev = getattr(self, "_last_term_w", 0)
            self._last_term_w = w
            if prev and abs(prev - w) < 2:
                return
            self.set_timer(0.25, self._paint_selected_image)
        except Exception:
            pass

    def _enrich_and_image(self, article: dict, index: int = -1) -> None:
        """Background: expand short body + load thumbnail."""
        self._enrich_worker(article, index)

    @work(group="enrich", exclusive=True, thread=True)
    def _enrich_worker(self, article: dict, index: int) -> None:
        url = article.get("url", "")
        self.call_from_thread(self._set_header_status, "loading…")
        enriched = article
        try:
            enriched = self.scraper.enrich_article(article, delay=False)
        except Exception:
            enriched = article
        if url:
            for i, a in enumerate(self.articles):
                if a.get("url") == url:
                    self.articles[i] = enriched
                    break
            if 0 <= index < len(self.articles):
                self.articles[index] = enriched

        image_bytes = None
        if self.settings.auto_images and enriched.get("image_url"):
            try:
                image_bytes = self.scraper.get_image(enriched["image_url"])
            except Exception:
                image_bytes = None

        def _apply() -> None:
            if not (self.selected and self.selected.get("url") == url):
                self._busy_reader(False)
                self._set_header_status(f"{len(self.articles)} articles")
                return
            self.selected = enriched
            self._image_bytes = image_bytes
            self._image_url = url or ""
            self._image_paint_w = 0  # allow hero re-paint for this story
            self._busy_reader(False)
            speaking = bool(getattr(self, "_speak_sentences", None)) and (
                tts_engine.is_playing
            )
            if speaking:
                # Don't rebuild body mid-speak — that wipes sentence highlight
                self._set_header_status(
                    f"Speaking · {voice_cfg.get_provider()}"
                )
            else:
                self._set_header_status(f"{len(self.articles)} articles")
                try:
                    self.query_one(ArticleReader).show_article(enriched)
                except Exception:
                    pass
            if image_bytes and not speaking:
                self.call_after_refresh(lambda: self._paint_selected_image(enriched))
            elif image_bytes and speaking:
                # Image-only paint keeps body/highlight intact
                self.call_after_refresh(
                    lambda: self._paint_selected_image(enriched)
                )

        self.call_from_thread(_apply)

    # ── actions ───────────────────────────────────────────────────

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Let filter / text inputs receive j and k as characters
        if action in ("move_down", "move_up") and isinstance(self.focused, Input):
            return False
        return True

    def _nav_list(self) -> ListView | None:
        """List under focus (feeds or articles), else the article list."""
        w = self.focused
        while w is not None:
            if isinstance(w, ListView):
                return w
            w = w.parent
        try:
            return self.query_one("#article-list", ListView)
        except Exception:
            return None

    def action_move_down(self) -> None:
        if isinstance(self.focused, Input):
            return
        lv = self._nav_list()
        if lv is None:
            return
        try:
            if self.focused is not lv:
                lv.focus()
        except Exception:
            pass
        lv.action_cursor_down()

    def action_move_up(self) -> None:
        if isinstance(self.focused, Input):
            return
        lv = self._nav_list()
        if lv is None:
            return
        try:
            if self.focused is not lv:
                lv.focus()
        except Exception:
            pass
        lv.action_cursor_up()

    def action_quit_or_back(self) -> None:
        if len(self.screen_stack) > 1:
            self.pop_screen()
            return
        al = self.query_one(ArticleList)
        bar = al.query_one("#filter-bar")
        if "visible" in bar.classes:
            al.show_filter(False)
            return
        # Phone reading mode → back to list (don't quit)
        try:
            if "reading" in self.query_one("#body").classes:
                self._exit_reading_mode()
                self.toast("Back to list", "info")
                return
        except Exception:
            pass
        tts_engine.stop()
        self.exit()

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_filter(self) -> None:
        self.query_one(ArticleList).show_filter(True)

    def action_clear_filter(self) -> None:
        al = self.query_one(ArticleList)
        bar = al.query_one("#filter-bar")
        if "visible" in bar.classes:
            al.show_filter(False)
            from textual.widgets import Input

            al.query_one("#filter-input", Input).value = ""
            al.set_articles(self.articles)
            return
        # Esc: exit phone reader, or hide dual-pane reader
        try:
            if "reading" in self.query_one("#body").classes:
                self._exit_reading_mode()
                return
        except Exception:
            pass
        if self.size.width < 100:
            self.query_one("#reader-pane").add_class("hidden-narrow")
            try:
                self.query_one("#article-list", ListView).focus()
            except Exception:
                pass

    def action_palette(self) -> None:
        self.push_screen(CommandPaletteScreen(), self._on_palette)

    def _on_palette(self, cmd: str | None) -> None:
        if not cmd:
            return
        dispatch = {
            "refresh": self.action_refresh,
            "search": self.action_search,
            "bookmarks": lambda: self.load_feed("bookmarks", "Bookmarks"),
            "trending": self.action_trending,
            "breaking": lambda: self.load_feed("breaking", "Breaking"),
            "summary": self.action_summary,
            "compare": self.action_compare,
            "offline": lambda: self.load_feed("offline", "Offline"),
            "settings": self.action_settings,
            "add-feed": self.action_manage_feeds,
            "my-feeds": lambda: self.load_feed("custom", "My Feeds"),
            "manage-feeds": self.action_manage_feeds,
            "ai-chat": self.action_ai_chat,
            "ai-provider": self.action_ai_provider,
            "voice-setup": self.action_voice_setup,
            "speak": self.action_speak,
            "theme": self.action_cycle_theme,
            "export": self.action_export,
            "help": self.action_help,
            "quit": self.exit,
        }
        fn = dispatch.get(cmd)
        if fn:
            fn()

    def action_bookmark(self) -> None:
        article = self.selected
        if not article:
            _, article = self.query_one(ArticleList).current_article()
        if not article:
            return
        self.selected = article
        added = self.bookmarks.toggle(article)
        self.query_one(ArticleList).set_articles(self.articles)
        self.toast("Bookmarked" if added else "Bookmark removed", "success")

    def action_open_browser(self) -> None:
        if self.selected and self.selected.get("url"):
            ok, msg = open_url(self.selected["url"])
            self.toast(msg, "success" if ok else "warning")

    def action_refresh(self) -> None:
        # Bust cache so new providers / removed cricket show up
        if self.current_feed in NEWS_SOURCES or self.current_feed == "all":
            import os

            cats = (
                list(NEWS_SOURCES.keys())
                if self.current_feed == "all"
                else [self.current_feed]
            )
            for c in cats:
                fp = os.path.join(self.cache.dir, c.replace("/", "_") + ".json")
                if os.path.exists(fp):
                    os.remove(fp)
            # Drop stale cricket cache if any
            old = os.path.join(self.cache.dir, "cricket.json")
            if os.path.exists(old):
                os.remove(old)
        self.load_feed(self.current_feed, self.current_label)
        self.toast("Refreshed", "success")

    def action_toggle_images(self) -> None:
        self.settings.toggle_auto_images()
        on = self.settings.auto_images
        self.toast(f"Auto images {'on' if on else 'off'}", "success")
        if on and self.selected:
            self._enrich_and_image(self.selected)

    def action_settings(self) -> None:
        self.push_screen(SettingsScreen(self.settings), self._on_settings)

    def _on_settings(self, result: dict | None) -> None:
        if not result:
            self.toast("Settings closed", "info")
            return
        if "theme" in result:
            self.theme = result["theme"]
            self.toast(f"Theme: {result['theme']}", "success")
        if "density" in result:
            self._apply_density()
            self.toast(f"Density: {result['density']}", "success")
        if "images" in result:
            self.toast(
                f"Auto images {'on' if result['images'] else 'off'}",
                "success",
            )
        if result.get("ai"):
            self.toast(f"AI: {ai.get_provider()} / {ai.get_model()}", "success")
            self._set_header_status(f"AI · {ai.get_provider()}")
        if result.get("voice"):
            self.toast(f"Voice: {voice_cfg.get_provider()}", "success")
            self._set_header_status(f"Voice · {voice_cfg.get_provider()}")
        if result.get("feeds"):
            try:
                self.query_one(FeedSidebar).refresh_custom_label()
            except Exception:
                pass
        if result.get("open_custom"):
            self.load_feed("custom", "My Feeds")
    def action_cycle_theme(self) -> None:
        from worldnews.themes import THEME_CYCLE

        keys = list(THEME_CYCLE)
        try:
            i = keys.index(self.theme)
        except ValueError:
            i = -1
        nxt = keys[(i + 1) % len(keys)]
        self.settings.set_theme(nxt)
        self.theme = nxt
        self.toast(f"Theme: {nxt}", "success")

    def action_search(self) -> None:
        hist = [h["query"] for h in self.search_history.data]
        self.push_screen(SearchScreen(hist), self._on_search)

    @work(exclusive=True, thread=True)
    def _run_search(self, query: str) -> None:
        self.call_from_thread(self._busy_list, True, f"Searching “{query}”…")
        self.call_from_thread(self._busy_reader, True, "Searching…")
        self.call_from_thread(self._set_status, f"SEARCH · {query}…")
        try:
            results = self.scraper.search(query)
        except Exception as exc:
            self.call_from_thread(self.toast, f"Search failed: {exc}", "error")
            results = []
        self.articles = results
        self.current_feed = "search"
        self.current_label = f"Search: {query}"
        self.call_from_thread(self._set_crumbs, f"World › Search › {query}")
        self.call_from_thread(self._apply_articles, False)

    def _on_search(self, query: str | None) -> None:
        if not query:
            return
        self.search_history.add(query)
        self._show_fetching(f"Search: {query}")
        self._run_search(query)

    def action_summary(self) -> None:
        arts = self.articles or self.cache.get("general") or []
        self.push_screen(SummaryScreen(arts))

    def action_compare(self) -> None:
        self._run_compare()

    @work(exclusive=True, thread=True)
    def _run_compare(self) -> None:
        self.call_from_thread(self._set_status, "COMPARE · fetching…")
        data = {}
        for cat in ("general", "tech", "sports", "science", "ai"):
            chunk = self.cache.get(cat)
            if chunk is None:
                chunk = self.scraper.fetch(cat)
                self.cache.set(cat, chunk)
            data[cat] = chunk
        def _show() -> None:
            self.push_screen(CompareScreen(data))

        self.call_from_thread(_show)

    def action_trending(self) -> None:
        self._run_trending()

    @work(exclusive=True, thread=True)
    def _run_trending(self) -> None:
        self.call_from_thread(self._set_status, "TRENDING · scanning…")
        words: Counter = Counter()
        for cat in ("general", "tech", "sports", "ai", "business", "science"):
            arts = self.cache.get(cat)
            if arts is None:
                arts = self.scraper.fetch(cat)
                self.cache.set(cat, arts)
            for a in arts:
                # Titles only — descriptions inflate stopwords like "description"
                text = (a.get("title", "") or "").lower()
                for w in re.findall(r"[a-z]{4,}", text):
                    if w not in STOP:
                        words[w] += 1
        top = words.most_common(40)

        def _show() -> None:
            self._busy_list(False)
            self._busy_reader(False)
            self.push_screen(TrendingScreen(top))

        self.call_from_thread(_show)

    def action_add_feed(self) -> None:
        self.action_manage_feeds()

    def action_manage_feeds(self) -> None:
        self.push_screen(
            ManageFeedsScreen(self.custom_feeds), self._on_manage_feeds
        )

    def _on_manage_feeds(self, result: dict | None) -> None:
        try:
            self.query_one(FeedSidebar).refresh_custom_label()
        except Exception:
            pass
        if not result:
            return
        if result.get("open"):
            self.load_feed("custom", "My Feeds")
            return
        if result.get("changed") and self.current_feed == "custom":
            self.load_feed("custom", "My Feeds")

    def _on_add_feed(self, result: dict | None) -> None:
        if not result:
            return
        ok = self.custom_feeds.add(
            result["name"], result["url"], lang=result.get("lang") or ""
        )
        try:
            self.query_one(FeedSidebar).refresh_custom_label()
        except Exception:
            pass
        if not ok:
            self.toast("Feed already saved", "warning")
            return
        lang = result.get("lang_label") or result.get("lang") or "?"
        n = result.get("count", 0)
        self.toast(
            f"Added {result['name']} · {lang} · {n} stories",
            "success",
        )
        self.load_feed("custom", "My Feeds")

    def action_ai_chat(self) -> None:
        self.push_screen(AIChatScreen())

    def action_ai_provider(self) -> None:
        self.push_screen(AIProviderScreen(), self._on_provider)

    def action_voice_setup(self) -> None:
        self.push_screen(VoiceSetupScreen(), self._on_voice_setup)

    def _on_voice_setup(self, result) -> None:
        if result and result.get("saved"):
            self.toast(f"Voice: {voice_cfg.get_status()}", "success")
            self._set_header_status(f"Voice · {voice_cfg.get_provider()}")

    def action_speak(self) -> None:
        if tts_engine.is_playing:
            tts_engine.stop()
            self._clear_speak_highlight()
            self.toast("Stopped speaking", "info")
            self._set_header_status("")
            return
        article = self.selected
        if not article:
            _, article = self.query_one(ArticleList).current_article()
            self.selected = article
        if not article:
            self.toast("Select an article first", "warning")
            return
        # Speak the on-screen body only (not a rebuilt title+full dump)
        from worldnews.tts import split_body_sentences

        reader = self.query_one(ArticleReader)
        plain = reader.body_plain_text()
        if len(plain) < 40:
            plain = (article.get("description") or article.get("title") or "").strip()
        # Per-paragraph split so each sentence still appears in the reader body
        sentences = split_body_sentences(plain)
        if not sentences:
            sentences = article_speech_sentences(article)
        text = " ".join(sentences) or article_speech_text(article)
        self._speak_sentences = sentences
        try:
            reader.set_active_action("speak")
        except Exception:
            pass
        self.toast(f"Speaking · {voice_cfg.get_provider()}…", "info")
        self._set_header_status(f"Speaking · preparing…")
        # Don't highlight until audio for that sentence actually starts (callback)
        self._speak_worker(text, sentences)

    def action_speak_test(self) -> None:
        if tts_engine.is_playing:
            tts_engine.stop()
            self._clear_speak_highlight()
        sample = (
            "Hello from World News. This is a test of your selected voice provider. "
            "The current sentence should highlight as it is read aloud."
        )
        from worldnews.tts import split_speech_sentences

        sentences = split_speech_sentences(sample)
        self._speak_sentences = sentences
        self.toast(f"Voice test · {voice_cfg.get_provider()}…", "info")
        self._set_header_status("Speaking · preparing…")
        self._speak_worker(sample, sentences)

    def _on_speak_sentence(self, index: int, _sentence: str, sentences: list) -> None:
        try:
            self.query_one(ArticleReader).set_reading_highlight(sentences, index)
            self._set_header_status(
                f"Speaking · {index + 1}/{len(sentences)} · {voice_cfg.get_provider()}"
            )
        except Exception:
            pass

    def _clear_speak_highlight(self) -> None:
        try:
            self.query_one(ArticleReader).clear_reading_highlight(self.selected)
        except Exception:
            pass
        self._speak_sentences = None

    @work(group="tts", exclusive=True, thread=True)
    def _speak_worker(self, text: str, sentences: list | None = None) -> None:
        def on_sentence(i: int, s: str, all_s: list) -> None:
            self.call_from_thread(self._on_speak_sentence, i, s, all_s)

        try:
            msg = tts_engine.speak(
                text,
                on_sentence=on_sentence if sentences else None,
                sentences=sentences,
            )
            play_err = getattr(tts_engine, "last_play_error", None)
            if play_err:
                msg = f"TTS synthesized but no player: {play_err}"
            err = (
                msg.startswith("TTS failed")
                or msg.startswith("Nothing")
                or bool(play_err)
            )
            self.call_from_thread(
                self.toast, msg, "error" if err else "success"
            )
        except Exception as exc:
            self.call_from_thread(self.toast, f"TTS error: {exc}", "error")
        finally:
            self.call_from_thread(self._clear_speak_highlight)
            self.call_from_thread(self._set_header_status, "")

    def _on_provider(self, result) -> None:
        if not result:
            return
        if isinstance(result, str):
            ai.set_provider(result)
            self.toast(f"AI: {result}", "success")
            return
        if isinstance(result, dict) and result.get("saved"):
            self.toast(
                f"AI: {ai.get_provider()} / {ai.get_model()}",
                "success",
            )
            self._set_header_status(f"AI · {ai.get_provider()}")

    def action_ai_summarize(self) -> None:
        article = self.selected
        if not article:
            _, article = self.query_one(ArticleList).current_article()
            self.selected = article
        if not article:
            self.toast("Select an article first", "warning")
            return
        self._start_ai("summarize", article)

    def action_ai_explain(self) -> None:
        article = self.selected
        if not article:
            _, article = self.query_one(ArticleList).current_article()
            self.selected = article
        if not article:
            self.toast("Select an article first", "warning")
            return
        self._start_ai("explain", article)

    @on(ArticleReader.BackPressed)
    def on_back_btn(self) -> None:
        self._exit_reading_mode()
        self.toast("Back to list", "info")

    @on(ArticleReader.SummarizePressed)
    def on_summarize_btn(self) -> None:
        self.action_ai_summarize()

    @on(ArticleReader.ExplainPressed)
    def on_explain_btn(self) -> None:
        self.action_ai_explain()

    @on(ArticleReader.SpeakPressed)
    def on_speak_btn(self) -> None:
        self.action_speak()

    @on(ArticleReader.BookmarkPressed)
    def on_bookmark_btn(self) -> None:
        self.action_bookmark()
        if self.selected:
            self.query_one(ArticleReader).show_article(self.selected)

    def _start_ai(self, mode: str, article: dict) -> None:
        """Push loading modal immediately, then run AI in background."""
        title = "AI Summary" if mode == "summarize" else "AI Explain"
        try:
            self.query_one(ArticleReader).set_active_action(
                "summarize" if mode == "summarize" else "explain"
            )
        except Exception:
            pass
        modal = AIResultModal(title, working=True)
        self.push_screen(modal)
        self._set_status(f"AI · {mode}…")
        self._set_header_status("AI working…")
        self.toast(f"{title} — working…", "info")
        self._ai_worker(mode, article)

    @work(group="ai", exclusive=True, thread=True)
    def _ai_worker(self, mode: str, article: dict) -> None:
        try:
            if mode == "summarize":
                text = ai.summarize_article(
                    article.get("title", ""),
                    article.get("description", ""),
                    article.get("source", ""),
                )
                title = "AI Summary"
            else:
                text = ai.explain_article(
                    article.get("title", ""),
                    article.get("description", ""),
                    "Explain the context and why this matters.",
                )
                title = "AI Explain"
            err = bool(text and str(text).startswith("Error:"))
            body = text or "_No response from provider._"
        except Exception as exc:
            title = "AI Error"
            body = f"**Request failed**\n\n```\n{exc}\n```"
            err = True

        def _done() -> None:
            try:
                self.query_one(ArticleReader).set_active_action(None)
            except Exception:
                pass
            # Update the topmost AI modal if still open
            for screen in reversed(self.screen_stack):
                if isinstance(screen, AIResultModal):
                    screen.set_result(title, body, error=err)
                    break
            else:
                # Modal was closed — show a fresh one with the result
                self.push_screen(AIResultModal(title, body, working=False))
            self._set_status("READY" if not err else "AI · error")
            self._set_header_status(f"{len(self.articles)} articles")
            if err:
                self.toast("AI failed — see modal", "error")
            else:
                self.toast("AI done", "success")

        self.call_from_thread(_done)

    def action_export(self) -> None:
        if not self.articles:
            self.toast("Nothing to export", "warning")
            return
        path = Exporter.export_markdown(self.articles)
        self.toast(f"Exported: {path}", "success")

    def action_prev_feed(self) -> None:
        self._shift_feed(-1)

    def action_next_feed(self) -> None:
        self._shift_feed(1)

    def _shift_feed(self, delta: int) -> None:
        try:
            i = self._feed_order.index(self.current_feed)
        except ValueError:
            i = 0
        nxt = self._feed_order[(i + delta) % len(self._feed_order)]
        label = nxt.title()
        for sid, lab in SPECIAL_FEEDS + CATEGORIES:
            if sid == nxt:
                label = lab
                break
        self.query_one(FeedSidebar).select_feed(nxt)
        self.load_feed(nxt, label)

    def action_jump_cat_1(self) -> None:
        self._jump(1)

    def action_jump_cat_2(self) -> None:
        self._jump(2)

    def action_jump_cat_3(self) -> None:
        self._jump(3)

    def action_jump_cat_4(self) -> None:
        self._jump(4)

    def action_jump_cat_5(self) -> None:
        self._jump(5)

    def action_jump_cat_6(self) -> None:
        self._jump(6)

    def action_jump_cat_7(self) -> None:
        self._jump(7)

    def action_jump_cat_8(self) -> None:
        self._jump(8)

    def action_jump_cat_9(self) -> None:
        self._jump(9)

    def _jump(self, n: int) -> None:
        if 1 <= n <= len(CATEGORIES):
            cid, label = CATEGORIES[n - 1]
            self.query_one(FeedSidebar).select_feed(cid)
            self.load_feed(cid, label)


def run_app(
    start_feed: str | None = None,
    start_mode: str | None = None,
) -> None:
    WorldNewsApp(start_feed=start_feed, start_mode=start_mode).run()
