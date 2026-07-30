"""News fetching: RSS + ANN with richer descriptions and image URLs."""

from __future__ import annotations

import html
import random
import re
import time
from urllib.parse import urljoin, urlparse

try:
    import cloudscraper
    import feedparser
    from bs4 import BeautifulSoup
except ImportError as exc:
    raise ImportError(
        "Missing dependencies. Run: pip install cloudscraper feedparser beautifulsoup4 lxml Pillow"
    ) from exc

_BS4_PARSER: str | None = None


def _bs4_parser() -> str:
    """Prefer lxml; fall back to html.parser (Termux-friendly)."""
    global _BS4_PARSER
    if _BS4_PARSER is None:
        try:
            import lxml  # noqa: F401

            _BS4_PARSER = "lxml"
        except ImportError:
            _BS4_PARSER = "html.parser"
    return _BS4_PARSER


def _soup(markup, *, features: str | None = None):
    return BeautifulSoup(markup, features or _bs4_parser())

# Stub / useless blurbs we treat as missing
_STUB_DESCS = {
    "",
    "no description",
    "latest anime news",
    "read more",
    "continue reading",
    "click here",
}

_LANG_NAMES = {
    "en": "EN",
    "hi": "HI",
    "ta": "TA",
    "ml": "ML",
    "te": "TE",
    "bn": "BN",
    "mr": "MR",
    "gu": "GU",
    "kn": "KN",
    "ar": "AR",
    "es": "ES",
    "fr": "FR",
    "de": "DE",
    "pt": "PT",
    "ja": "JA",
    "ko": "KO",
    "zh": "ZH",
    "ru": "RU",
    "tr": "TR",
    "it": "IT",
    "nl": "NL",
    "pl": "PL",
    "uk": "UK",
    "fa": "FA",
    "ur": "UR",
    "th": "TH",
    "vi": "VI",
    "id": "ID",
    "ms": "MS",
    "sv": "SV",
    "no": "NO",
    "da": "DA",
    "fi": "FI",
    "el": "EL",
    "he": "HE",
    "cs": "CS",
    "ro": "RO",
    "hu": "HU",
}

_LANG_FULL = {
    "EN": "English",
    "HI": "Hindi",
    "TA": "Tamil",
    "ML": "Malayalam",
    "TE": "Telugu",
    "BN": "Bengali",
    "MR": "Marathi",
    "GU": "Gujarati",
    "KN": "Kannada",
    "AR": "Arabic",
    "ES": "Spanish",
    "FR": "French",
    "DE": "German",
    "PT": "Portuguese",
    "JA": "Japanese",
    "KO": "Korean",
    "ZH": "Chinese",
    "RU": "Russian",
    "TR": "Turkish",
    "IT": "Italian",
    "NL": "Dutch",
    "PL": "Polish",
    "UK": "Ukrainian",
    "FA": "Persian",
    "UR": "Urdu",
    "TH": "Thai",
    "VI": "Vietnamese",
    "ID": "Indonesian",
    "MS": "Malay",
}


def lang_display_name(code: str) -> str:
    c = (code or "").strip().upper()
    if not c:
        return "Unknown"
    full = _LANG_FULL.get(c)
    return f"{full} ({c})" if full else c


def _clean_text(raw: str, limit: int = 1200) -> str:
    if not raw:
        return ""
    text = _soup(raw).get_text(" ", strip=True)
    text = html.unescape(re.sub(r"\s+", " ", text)).strip()
    if len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0] + "…"
    return text


def _is_stub(desc: str) -> bool:
    d = (desc or "").strip().lower()
    return len(d) < 40 or d in _STUB_DESCS


_COMMENT_TITLE_RE = re.compile(
    r"^\d+\s+comments?$",
    re.IGNORECASE,
)


def _is_junk_headline(title: str) -> bool:
    """ANN discuss counters and empty/topic chips are not headlines."""
    t = (title or "").strip()
    if not t or len(t) < 12:
        return True
    if _COMMENT_TITLE_RE.match(t):
        return True
    low = t.lower()
    if low in {"news", "anime", "manga", "review", "interest", "forum"}:
        return True
    return False


def _is_discuss_url(url: str) -> bool:
    u = (url or "").lower()
    return any(
        x in u
        for x in (
            "/cms/discuss",
            "/bbs/",
            "viewtopic",
            "/forum/",
            "phpbb",
        )
    )


def _is_ann_article_url(url: str) -> bool:
    u = (url or "").lower()
    if _is_discuss_url(u):
        return False
    return any(
        x in u
        for x in (
            "/news/",
            "/interest/",
            "/review/",
            "/feature/",
            "/encyclopedia/",
        )
    )


def _ann_pick_article(item, base: str):
    """From an ANN herald box, pick real news title+url (not 'N comments')."""
    best_titled = None
    best_empty = None
    for a in item.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        abs_url = _abs_url(base, href)
        if not _is_ann_article_url(abs_url):
            continue
        title = html.unescape(a.get_text(" ", strip=True) or "")
        if _is_junk_headline(title):
            if not best_empty:
                best_empty = ("", abs_url)
            continue
        # Prefer longer titled news links
        if best_titled is None or len(title) > len(best_titled[0]):
            best_titled = (title, abs_url)
    picked = best_titled or best_empty
    if not picked or not picked[1]:
        return None
    title, href = picked
    if not title:
        # Thumbnail-only link — try sibling titled link with same article id
        for a in item.select("a[href]"):
            t = html.unescape(a.get_text(" ", strip=True) or "")
            if not _is_junk_headline(t) and not _is_discuss_url(a.get("href") or ""):
                title = t
                break
    if _is_junk_headline(title):
        return None
    desc_el = item.select_one(".snippet, .preview, .excerpt, p")
    desc = desc_el.get_text(" ", strip=True) if desc_el else ""
    # Drop leading "news" category chip noise from text blob
    if desc.lower().startswith("news "):
        desc = desc[5:].strip()
    img = ""
    thumb = item.select_one(".thumbnail.lazyload, .cover-image.lazyload, img")
    if thumb:
        img = _abs_url(
            base,
            thumb.get("data-src")
            or thumb.get("src")
            or "",
        )
    return title, href, desc, img


def _needs_full_body(desc: str, article: dict) -> bool:
    """Scrape until we have a real story (retry if we only got a bio/teaser)."""
    d = (desc or "").strip()
    if article.get("body_fetched"):
        if _looks_like_bio(d) or len(d) < 280:
            return True
        return False
    return True


_SKIP_PHRASES = (
    "cookie",
    "subscribe",
    "sign up",
    "newsletter",
    "advertisement",
    "advertisements",
    "related stories",
    "related articles",
    "read more",
    "share this",
    "follow us",
    "all rights reserved",
    "terms of service",
    "privacy policy",
    "enable javascript",
    "your browser",
    "can be reached at",
    "is a senior",
    "is a reporter",
    "is an editor",
    "contributing writer",
    "staff writer",
)

_BIO_HINTS = (
    "can be reached at",
    "twitter.com/",
    "x.com/",
    "@",
    "is a senior",
    "is a reporter",
    "is an editor",
    "contributing writer",
    "staff writer",
    "covers ",
    "based in ",
)

_BODY_SELECTORS = (
    "[itemprop='articleBody']",
    "article .article-content",
    "article .entry-content",
    "article .post-content",
    "article .story-body",
    "article .story-content",
    ".article-content",
    ".entry-content",
    ".post-content",
    ".story-body",
    ".story-body__inner",
    ".article__body",
    ".article-body",
    ".c-entry-content",
    ".content__article-body",
    "#article-body",
    "#story-body",
    ".js-article-body",
    "article .content",
    "main article",
    "article",
)


def _looks_like_bio(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()
    # Short blocks that are mostly author chrome
    hits = sum(1 for h in _BIO_HINTS if h in low)
    if hits >= 2 and len(t) < 900:
        return True
    if "can be reached at" in low and len(t) < 1200:
        return True
    return False


def _para_ok(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 35:
        return False
    low = t.lower()
    if any(s in low for s in _SKIP_PHRASES):
        return False
    if t.count("http") > 2:
        return False
    return True


def _paras_from_node(node, *, mutate: bool = False) -> list[str]:
    """Collect story paragraphs. Default: non-destructive (copy)."""
    if node is None:
        return []
    root = node
    if not mutate:
        try:
            from copy import copy

            root = copy(node)
        except Exception:
            root = node
    if mutate or root is not node:
        for bad in list(
            root.find_all(
                ["script", "style", "noscript", "aside", "nav", "footer", "form"]
            )
        ):
            try:
                bad.decompose()
            except Exception:
                pass
    paras: list[str] = []
    seen: set[str] = set()
    for p in root.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not _para_ok(text):
            continue
        # Skip author-bio paragraphs
        low = text.lower()
        if any(
            h in low
            for h in (
                "can be reached at",
                "is a senior writer",
                "is a senior reporter",
                "staff writer at",
            )
        ):
            continue
        key = text[:90].lower()
        if key in seen:
            continue
        seen.add(key)
        paras.append(text)
        if len(paras) >= 80:
            break
    return paras


def _json_ld_article_body(soup: BeautifulSoup) -> str:
    import json

    best = ""
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop(0)
            if not isinstance(item, dict):
                continue
            body = item.get("articleBody")
            if isinstance(body, str) and len(body.strip()) > 200:
                text = _soup(body).get_text("\n", strip=True)
                text = re.sub(r"\n{3,}", "\n\n", text).strip()
                if len(text) > len(best):
                    best = text
            for key in ("@graph", "hasPart", "mainEntity"):
                child = item.get(key)
                if isinstance(child, list):
                    stack.extend(child)
                elif isinstance(child, dict):
                    stack.append(child)
    return best


def _densest_paragraph_block(soup: BeautifulSoup) -> list[str]:
    """Fallback: pick the element with the most usable <p> text."""
    best: list[str] = []
    best_score = 0
    for tag in soup.find_all(["article", "section", "div"]):
        try:
            classes = " ".join(tag.get("class") or []).lower()
            tid = (tag.get("id") or "").lower()
        except Exception:
            continue
        blob = f"{classes} {tid}"
        if any(
            x in blob
            for x in (
                "nav",
                "menu",
                "footer",
                "header",
                "sidebar",
                "comment",
                "related",
                "promo",
                "share",
                "cookie",
                "author",
                "byline",
                "bio",
            )
        ):
            continue
        paras = _paras_from_node(tag, mutate=False)
        score = sum(len(p) for p in paras)
        if score > best_score and len(paras) >= 2:
            best_score = score
            best = paras
    return best


def _trafilatura_extract(html: bytes | str, url: str = "") -> dict:
    """Primary extractor — works across most news sites."""
    out = {"title": "", "description": "", "image_url": ""}
    try:
        import trafilatura
        from trafilatura import extract, extract_metadata
    except ImportError:
        return out

    try:
        text = extract(
            html,
            url=url or None,
            include_comments=False,
            include_tables=False,
            include_images=False,
            favor_recall=True,
            output_format="txt",
        )
    except Exception:
        text = None
    if text:
        # Normalize to paragraphs
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not parts:
            parts = [ln.strip() for ln in text.splitlines() if ln.strip()]
        joined = "\n\n".join(parts)
        if not _looks_like_bio(joined):
            out["description"] = joined[:14000]

    try:
        meta = extract_metadata(html, default_url=url or None)
    except Exception:
        meta = None
    if meta:
        if getattr(meta, "title", None):
            out["title"] = (meta.title or "").strip()
        img = getattr(meta, "image", None) or ""
        if img:
            out["image_url"] = _abs_url(url, img) if url else img
    return out


def extract_article_body(soup: BeautifulSoup, html: bytes | str = b"", url: str = "") -> str:
    """Pull the main story text from a news HTML page (any major site)."""
    # 1) trafilatura (best general extractor)
    if html:
        traf = _trafilatura_extract(html, url)
        body = traf.get("description") or ""
        if len(body) > 280 and not _looks_like_bio(body):
            return body[:14000]

    # 2) JSON-LD articleBody only (not short description)
    ld = _json_ld_article_body(soup)
    if ld and len(ld) > 400 and not _looks_like_bio(ld):
        return ld[:14000]

    # 3) CSS selectors for common CMS layouts
    best: list[str] = []
    for sel in _BODY_SELECTORS:
        try:
            nodes = soup.select(sel)
        except Exception:
            continue
        for node in nodes[:3]:
            paras = _paras_from_node(node, mutate=False)
            if sum(len(p) for p in paras) > sum(len(p) for p in best):
                best = paras
        if len(best) >= 5 and sum(len(p) for p in best) > 800:
            break

    if sum(len(p) for p in best) < 400:
        dense = _densest_paragraph_block(soup)
        if sum(len(p) for p in dense) > sum(len(p) for p in best):
            best = dense

    text = "\n\n".join(best).strip()
    if text and not _looks_like_bio(text):
        return text[:14000]
    if ld and not _looks_like_bio(ld):
        return ld[:14000]
    # Last resort: trafilatura even if short
    if html:
        traf = _trafilatura_extract(html, url)
        if traf.get("description"):
            return traf["description"][:14000]
    return text[:14000]


def scrape_article_page(html: bytes | str, url: str = "") -> dict:
    """Return title, full description, and image URL from any article page."""
    soup = _soup(html)
    result = {"title": "", "description": "", "image_url": ""}

    traf = _trafilatura_extract(html, url)
    result["title"] = traf.get("title") or ""
    result["description"] = traf.get("description") or ""
    result["image_url"] = traf.get("image_url") or ""

    if len(result["description"]) < 280 or _looks_like_bio(result["description"]):
        body = extract_article_body(soup, html=html, url=url)
        if body and len(body) > len(result["description"]):
            result["description"] = body

    if not result["title"]:
        h1 = soup.find("h1")
        if h1:
            result["title"] = h1.get_text(" ", strip=True)
        if not result["title"] and soup.title:
            result["title"] = soup.title.get_text(" ", strip=True)

    if not result["image_url"]:
        og = soup.find("meta", property="og:image") or soup.find(
            "meta", attrs={"name": "og:image"}
        )
        if og and og.get("content"):
            result["image_url"] = _abs_url(url, og["content"])
        if not result["image_url"]:
            tw = soup.find("meta", attrs={"name": "twitter:image"})
            if tw and tw.get("content"):
                result["image_url"] = _abs_url(url, tw["content"])

    return result


def _abs_url(base: str, src: str) -> str:
    if not src:
        return ""
    src = src.strip()
    if src.startswith("//"):
        return "https:" + src
    return urljoin(base, src)


def _img_from_html(fragment: str, base: str = "") -> str:
    if not fragment:
        return ""
    soup = _soup(fragment)
    for img in soup.find_all("img"):
        src = (
            img.get("src")
            or img.get("data-src")
            or img.get("data-lazy-src")
            or img.get("data-original")
            or ""
        )
        if not src or src.startswith("data:"):
            continue
        w, h = img.get("width"), img.get("height")
        try:
            if w and int(str(w).replace("px", "")) < 40:
                continue
            if h and int(str(h).replace("px", "")) < 40:
                continue
        except ValueError:
            pass
        return _abs_url(base, src)
    return ""


def _img_from_entry(entry, base: str = "") -> str:
    thumbs = getattr(entry, "media_thumbnail", None) or entry.get("media_thumbnail")
    if thumbs:
        url = thumbs[0].get("url", "")
        if url:
            return _abs_url(base, url)
    media = getattr(entry, "media_content", None) or entry.get("media_content")
    if media:
        for m in media:
            if m.get("medium") == "image" or str(m.get("type", "")).startswith("image"):
                url = m.get("url", "")
                if url:
                    return _abs_url(base, url)
        url = media[0].get("url", "")
        if url and any(
            url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")
        ):
            return _abs_url(base, url)
    for enc in getattr(entry, "enclosures", None) or entry.get("enclosures") or []:
        typ = enc.get("type", "")
        href = enc.get("href") or enc.get("url") or ""
        if typ.startswith("image") or any(
            href.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")
        ):
            return _abs_url(base, href)
    for key in ("summary", "description"):
        found = _img_from_html(entry.get(key, "") or "", base)
        if found:
            return found
    if hasattr(entry, "content") and entry.content:
        found = _img_from_html(entry.content[0].get("value", ""), base)
        if found:
            return found
    return ""


def _desc_from_entry(entry) -> str:
    chunks = []
    if hasattr(entry, "content") and entry.content:
        chunks.append(entry.content[0].get("value", ""))
    for key in ("summary", "description", "subtitle"):
        chunks.append(entry.get(key, "") or "")
    best = ""
    for c in chunks:
        text = _clean_text(c, 1400)
        if len(text) > len(best):
            best = text
    return best


def detect_language(text: str, feed_lang: str = "") -> str:
    """Return short language tag (EN, HI, JA…) from feed meta or script heuristics."""
    fl = (feed_lang or "").strip().lower().replace("_", "-")
    if fl:
        code = fl.split("-")[0][:2]
        return _LANG_NAMES.get(code, code.upper())
    sample = text or ""
    if re.search(r"[\u0900-\u097F]", sample):
        return "HI"
    if re.search(r"[\u0B80-\u0BFF]", sample):
        return "TA"
    if re.search(r"[\u0D00-\u0D7F]", sample):
        return "ML"
    if re.search(r"[\u0C00-\u0C7F]", sample):
        return "TE"
    if re.search(r"[\u0980-\u09FF]", sample):
        return "BN"
    if re.search(r"[\u0600-\u06FF]", sample):
        return "AR"
    if re.search(r"[\u3040-\u30FF]", sample):
        return "JA"
    if re.search(r"[\uAC00-\uD7AF]", sample):
        return "KO"
    if re.search(r"[\u4E00-\u9FFF]", sample):
        return "ZH"
    if re.search(r"[\u0400-\u04FF]", sample):
        return "RU"
    return "EN"


class Scraper:
    def __init__(self):
        self.client = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )

    def _get(self, url, timeout=15, delay=True):
        try:
            if delay:
                time.sleep(random.uniform(0.15, 0.45))
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache",
                "Referer": f"{urlparse(url).scheme}://{urlparse(url).netloc}/",
            }
            r = self.client.get(url, timeout=timeout, headers=headers)
            r.raise_for_status()
            return r
        except Exception:
            return None

    def _img(self, url):
        try:
            r = self.client.get(url, timeout=10)
            r.raise_for_status()
            return r.content if len(r.content) > 100 else None
        except Exception:
            return None

    def _rss(self, url, name=""):
        try:
            r = self._get(url)
            if not r:
                return []
            feed = feedparser.parse(r.content)
            feed_link = feed.feed.get("link", url)
            feed_lang = (
                feed.feed.get("language")
                or feed.feed.get("lang")
                or ""
            )
            arts = []
            for e in feed.entries:
                pub = e.get("published", "") or e.get("updated", "")
                if not pub and getattr(e, "published_parsed", None):
                    try:
                        pub = time.strftime("%Y-%m-%d", e.published_parsed)
                    except Exception:
                        pub = ""
                link = e.get("link", "") or ""
                title = html.unescape(e.get("title", "") or "Untitled")
                if _is_junk_headline(title) or _is_discuss_url(link):
                    continue
                desc = _desc_from_entry(e)
                img = _img_from_entry(e, link or feed_link)
                lang = detect_language(f"{title} {desc}", feed_lang)
                arts.append(
                    {
                        "title": title,
                        "source": name or feed.feed.get("title", "Unknown"),
                        "author": e.get("author", "") or "",
                        "published": pub,
                        "description": desc or "No description",
                        "url": link,
                        "image_url": img,
                        "lang": lang,
                    }
                )
            return arts
        except Exception:
            return []

    def discover_feed(self, url: str) -> tuple[str, str]:
        """Resolve a website or RSS URL to (feed_url, suggested_name).

        Accepts direct RSS/Atom links or a homepage — finds <link rel=alternate>.
        """
        url = (url or "").strip()
        if not url:
            raise ValueError("URL is empty")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        # Try as feed first
        r = self._get(url, delay=False)
        if not r:
            raise ValueError(f"Could not fetch URL: {url}")
        ctype = (r.headers.get("Content-Type") or "").lower()
        body = r.content
        looks_feed = (
            "xml" in ctype
            or "rss" in ctype
            or "atom" in ctype
            or body.lstrip()[:200].lower().startswith((b"<?xml", b"<rss", b"<feed", b"<rdf"))
        )
        if looks_feed:
            feed = feedparser.parse(body)
            if feed.entries or feed.feed.get("title"):
                title = feed.feed.get("title") or urlparse(url).netloc or "Custom"
                return url, html.unescape(title).strip()[:80]

        # HTML page — hunt for alternate feed links
        soup = _soup(body)
        candidates = []
        for link in soup.find_all("link"):
            rel = " ".join(link.get("rel") or []).lower()
            typ = (link.get("type") or "").lower()
            href = link.get("href") or ""
            if not href:
                continue
            if "alternate" in rel and any(
                x in typ for x in ("rss", "atom", "xml")
            ):
                candidates.append(_abs_url(url, href))
            elif any(x in href.lower() for x in ("/rss", "/feed", ".rss", "atom.xml")):
                candidates.append(_abs_url(url, href))
        for a in soup.find_all("a", href=True):
            href = a["href"]
            low = href.lower()
            if any(
                x in low
                for x in (
                    "/rss",
                    "/feed",
                    "atom.xml",
                    ".rss",
                    "rss.xml",
                    "index.xml",
                    "feeds/",
                    "?format=rss",
                    "format=xml",
                )
            ):
                candidates.append(_abs_url(url, href))

        # Common feed path guesses from homepage
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for path in (
            "/feed",
            "/rss",
            "/rss.xml",
            "/feed.xml",
            "/atom.xml",
            "/index.xml",
            "/feeds/posts/default",
            "/rss/news",
            "/news/rss",
            "/news/feed",
        ):
            candidates.append(base + path)

        seen = set()
        for cand in candidates:
            if cand in seen:
                continue
            seen.add(cand)
            items = self._rss(cand, "")
            if items:
                name = items[0].get("source") or parsed.netloc or "Custom"
                return cand, name[:80]

        raise ValueError(
            "No RSS/Atom feed found on that page. Paste a direct feed URL "
            "(often ends with /rss, /feed, or .xml)."
        )

    def _ann(self, limit=12):
        """Anime News Network — scrape news heralds (skip comment/discuss links)."""
        arts = []
        base = "https://www.animenewsnetwork.com"
        seen: set[str] = set()
        for path in ["/news", "/news/", "/news/?page=1"]:
            if len(arts) >= limit:
                break
            r = self._get(base + path)
            if not r:
                continue
            soup = _soup(r.content)
            # Prefer real news boxes; skip marquee-only /ads heralds
            items = soup.select(".herald.box.news") or soup.select(
                ".herald.box, .news.herald, .herald"
            )
            for item in items:
                if len(arts) >= limit:
                    break
                picked = _ann_pick_article(item, base)
                if not picked:
                    continue
                title, href, desc, img = picked
                if href in seen:
                    continue
                seen.add(href)
                arts.append(
                    {
                        "title": title,
                        "source": "ANN",
                        "author": "",
                        "published": "",
                        "description": desc or "No description",
                        "url": href,
                        "image_url": img,
                        "lang": "EN",
                    }
                )
        return arts

    def enrich_article(self, article: dict, delay: bool = True) -> dict:
        """Fetch the article URL → title, image, and full story body."""
        out = dict(article)
        url = out.get("url") or ""
        if not url:
            return out
        # Never enrich forum/discuss pages as if they were articles
        if _is_discuss_url(url) or _is_junk_headline(out.get("title", "")):
            return out
        need_body = _needs_full_body(out.get("description", ""), out)
        need_img = not out.get("image_url")
        if not need_body and not need_img:
            return out
        r = self._get(url, timeout=20, delay=delay)
        if not r:
            return out  # retry next open
        scraped = scrape_article_page(r.content, url)
        # Reject phpBB / forum scrapes
        body_probe = (scraped.get("description") or "").lower()
        if "powered by phpbb" in body_probe or "you cannot post new topics" in body_probe:
            return out
        if scraped.get("title") and (
            _is_junk_headline(out.get("title", ""))
            or len(scraped["title"]) > len(out.get("title") or "")
        ):
            if not _is_junk_headline(scraped["title"]):
                out["title"] = scraped["title"]
        if need_img and scraped.get("image_url"):
            out["image_url"] = scraped["image_url"]
        # Always adopt a better image from the page when RSS had none or a weak one
        if scraped.get("image_url") and not out.get("image_url"):
            out["image_url"] = scraped["image_url"]
        if need_body:
            body = scraped.get("description") or ""
            rss = (out.get("description") or "").strip()
            if body and len(body) > max(120, len(rss)):
                out["description"] = body
            elif body and (_is_stub(rss) or len(body) > len(rss)):
                out["description"] = body
            out["body_fetched"] = True
            out["lang"] = detect_language(
                f"{out.get('title', '')} {out.get('description', '')}",
                out.get("lang", ""),
            )
        return out

    def fetch(self, cat):
        sources = NEWS_SOURCES.get(cat, [])
        arts, seen = [], set()
        for s in sources:
            if s["type"] == "ann":
                items = self._ann(12)
            elif s["type"] == "rss":
                items = self._rss(s["url"], s.get("name", ""))
            else:
                items = []
            for a in items:
                if a["url"] and a["url"] not in seen:
                    arts.append(a)
                    seen.add(a["url"])
        return arts

    def search(self, q):
        query = (q or "").strip().lower()
        if not query:
            return []
        tokens = [
            t
            for t in re.findall(r"[a-z0-9]+", query)
            if t not in SEARCH_STOPWORDS and len(t) > 2
        ]
        results = []
        seen = set()
        for c in NEWS_SOURCES:
            for a in self.fetch(c):
                text = f"{a.get('title', '')} {a.get('description', '')}".lower()
                score = 0
                if tokens:
                    for t in tokens:
                        if t in text:
                            score += 1
                elif query in text:
                    score = 1
                if score > 0:
                    url = a.get("url")
                    if url and url not in seen:
                        results.append((score, a))
                        seen.add(url)
        if tokens:
            results.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in results]

    def get_image(self, url):
        return self._img(url) if url else None


NEWS_SOURCES = {
    "general": [
        {"type": "rss", "url": "https://feeds.bbci.co.uk/news/rss.xml", "name": "BBC"},
        {"type": "rss", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "name": "BBC World"},
        {"type": "rss", "url": "https://feeds.bbci.co.uk/news/world/asia/india/rss.xml", "name": "BBC India"},
        {"type": "rss", "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml", "name": "NYT"},
        {"type": "rss", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "name": "NYT World"},
        {"type": "rss", "url": "https://www.npr.org/rss/rss.php?id=1001", "name": "NPR"},
        {"type": "rss", "url": "https://www.aljazeera.com/xml/rss/all.xml", "name": "Al Jazeera"},
        {"type": "rss", "url": "https://www.theguardian.com/world/rss", "name": "Guardian World"},
        {"type": "rss", "url": "https://www.theguardian.com/uk/rss", "name": "Guardian UK"},
        {"type": "rss", "url": "https://www.thehindu.com/news/national/feeder/default.rss", "name": "The Hindu"},
        {"type": "rss", "url": "https://www.thehindu.com/news/international/feeder/default.rss", "name": "Hindu Intl"},
        {"type": "rss", "url": "https://indianexpress.com/section/india/feed/", "name": "Indian Express"},
        {"type": "rss", "url": "https://indianexpress.com/section/world/feed/", "name": "IE World"},
        {"type": "rss", "url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml", "name": "Hindustan Times"},
        {"type": "rss", "url": "https://feeds.feedburner.com/ndtvnews-top-stories", "name": "NDTV"},
        {"type": "rss", "url": "https://feeds.feedburner.com/ndtvnews-world-news", "name": "NDTV World"},
        {"type": "rss", "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "name": "Times of India"},
        {"type": "rss", "url": "https://www.france24.com/en/rss", "name": "France 24"},
        {"type": "rss", "url": "https://www.dw.com/en/top-stories/s-9097?maca=en-rss-en-all-1573-rdf", "name": "DW"},
        {"type": "rss", "url": "https://rss.cnn.com/rss/edition.rss", "name": "CNN"},
        {"type": "rss", "url": "https://feeds.bbci.co.uk/news/world/europe/rss.xml", "name": "BBC Europe"},
        {"type": "rss", "url": "https://www.abc.net.au/news/feed/51120/rss.xml", "name": "ABC Australia"},
    ],
    "anime": [
        {"type": "ann"},
        {"type": "rss", "url": "https://www.crunchyroll.com/feed/news", "name": "Crunchyroll"},
        {"type": "rss", "url": "https://www.animenewsnetwork.com/news/rss.xml", "name": "ANN RSS"},
        {"type": "rss", "url": "https://www.animenewsnetwork.com/encyclopedia/rss.xml?id=1422", "name": "ANN Interest"},
        {"type": "rss", "url": "https://www.sbs.com.au/feeds/anime-news", "name": "SBS Anime"},
        {"type": "rss", "url": "https://www.animenewsnetwork.com/news/anime/rss.xml", "name": "ANN Anime"},
        {"type": "rss", "url": "https://www.animenewsnetwork.com/news/manga/rss.xml", "name": "ANN Manga"},
    ],
    "marvel": [
        {"type": "rss", "url": "https://screenrant.com/feed/", "name": "ScreenRant"},
        {"type": "rss", "url": "https://www.cbr.com/feed/", "name": "CBR"},
        {"type": "rss", "url": "https://comicbook.com/marvel/feed/", "name": "ComicBook Marvel"},
        {"type": "rss", "url": "https://www.marvel.com/rss", "name": "Marvel.com"},
        {"type": "rss", "url": "https://www.cbr.com/category/movies/marvel/feed/", "name": "CBR Marvel Movies"},
        {"type": "rss", "url": "https://screenrant.com/tag/marvel/feed/", "name": "ScreenRant Marvel"},
    ],
    "dc": [
        {"type": "rss", "url": "https://comicbook.com/dc/feed/", "name": "ComicBook DC"},
        {"type": "rss", "url": "https://www.cbr.com/category/comics/dc/feed/", "name": "CBR DC"},
        {"type": "rss", "url": "https://screenrant.com/tag/dc/feed/", "name": "ScreenRant DC"},
        {"type": "rss", "url": "https://comicbook.com/feed/", "name": "ComicBook"},
        {"type": "rss", "url": "https://www.cbr.com/category/movies/dc/feed/", "name": "CBR DC Movies"},
    ],
    "hollywood": [
        {"type": "rss", "url": "https://variety.com/feed/", "name": "Variety"},
        {"type": "rss", "url": "https://deadline.com/feed/", "name": "Deadline"},
        {"type": "rss", "url": "https://www.hollywoodreporter.com/feed/", "name": "Hollywood Reporter"},
        {"type": "rss", "url": "https://www.empireonline.com/rss/news/", "name": "Empire"},
        {"type": "rss", "url": "https://www.rollingstone.com/tv-movies/feed/", "name": "Rolling Stone"},
        {"type": "rss", "url": "https://www.indiewire.com/feed/", "name": "IndieWire"},
        {"type": "rss", "url": "https://www.slashfilm.com/feed/", "name": "Slashfilm"},
    ],
    "bollywood": [
        {"type": "rss", "url": "https://www.bollywoodhungama.com/feed/", "name": "Bollywood Hungama"},
        {"type": "rss", "url": "https://indianexpress.com/section/entertainment/bollywood/feed/", "name": "IE Bollywood"},
        {"type": "rss", "url": "https://www.filmfare.com/feeds/feeds_filmfare.xml", "name": "Filmfare"},
        {"type": "rss", "url": "https://www.hindustantimes.com/feeds/rss/entertainment/bollywood/rssfeed.xml", "name": "HT Bollywood"},
        {"type": "rss", "url": "https://timesofindia.indiatimes.com/rssfeeds/1081479906.cms", "name": "TOI Entertainment"},
        {"type": "rss", "url": "https://www.pinkvilla.com/rss.xml", "name": "Pinkvilla"},
    ],
    "mollywood": [
        {"type": "rss", "url": "https://www.newindianexpress.com/rss/movies/malayalam", "name": "TNIE Malayalam"},
        {"type": "rss", "url": "https://www.thehindu.com/entertainment/movies/feeder/default.rss", "name": "Hindu Movies"},
        {"type": "rss", "url": "https://indianexpress.com/section/entertainment/malayalam/feed/", "name": "IE Malayalam"},
        {"type": "rss", "url": "https://www.manoramaonline.com/entertainment.feeds.rss.news.xml", "name": "Manorama Ent"},
        {"type": "rss", "url": "https://www.onmanorama.com/entertainment.feeds.rss.news.xml", "name": "Onmanorama"},
    ],
    "sports": [
        {"type": "rss", "url": "https://www.espn.com/espn/rss/news", "name": "ESPN"},
        {"type": "rss", "url": "https://www.cbssports.com/rss/headlines", "name": "CBS Sports"},
        {"type": "rss", "url": "https://sports.yahoo.com/rss/", "name": "Yahoo Sports"},
        {"type": "rss", "url": "https://www.espncricinfo.com/rss/news", "name": "ESPN Cricinfo"},
        {"type": "rss", "url": "https://feeds.bbci.co.uk/sport/rss.xml", "name": "BBC Sport"},
        {"type": "rss", "url": "https://feeds.bbci.co.uk/sport/cricket/rss.xml", "name": "BBC Cricket"},
        {"type": "rss", "url": "https://www.skysports.com/rss/12040", "name": "Sky Sports"},
        {"type": "rss", "url": "https://www.theguardian.com/sport/rss", "name": "Guardian Sport"},
        {"type": "rss", "url": "https://www.sportstar.thehindu.com/rss/", "name": "Sportstar"},
        {"type": "rss", "url": "https://www.espn.in/espn/rss/news", "name": "ESPN India"},
        {"type": "rss", "url": "https://www.goal.com/feeds/news", "name": "Goal"},
    ],
    "gaming": [
        {"type": "rss", "url": "https://www.pcgamer.com/rss/", "name": "PC Gamer"},
        {"type": "rss", "url": "https://www.polygon.com/rss/index.xml", "name": "Polygon"},
        {"type": "rss", "url": "https://www.ign.com/rss/articles/", "name": "IGN"},
        {"type": "rss", "url": "https://kotaku.com/rss", "name": "Kotaku"},
        {"type": "rss", "url": "https://www.eurogamer.net/feed", "name": "Eurogamer"},
        {"type": "rss", "url": "https://www.rockpapershotgun.com/feed", "name": "RPS"},
        {"type": "rss", "url": "https://www.gamespot.com/feeds/news/", "name": "GameSpot"},
        {"type": "rss", "url": "https://www.destructoid.com/feed/", "name": "Destructoid"},
    ],
    "tech": [
        {"type": "rss", "url": "https://www.theverge.com/rss/index.xml", "name": "The Verge"},
        {"type": "rss", "url": "https://techcrunch.com/feed/", "name": "TechCrunch"},
        {"type": "rss", "url": "https://www.wired.com/feed/rss", "name": "Wired"},
        {"type": "rss", "url": "https://arstechnica.com/feed/", "name": "Ars Technica"},
        {"type": "rss", "url": "https://www.engadget.com/rss.xml", "name": "Engadget"},
        {"type": "rss", "url": "https://feeds.bbci.co.uk/news/technology/rss.xml", "name": "BBC Tech"},
        {"type": "rss", "url": "https://www.thehindu.com/sci-tech/technology/feeder/default.rss", "name": "Hindu Tech"},
        {"type": "rss", "url": "https://www.zdnet.com/news/rss.xml", "name": "ZDNet"},
        {"type": "rss", "url": "https://www.technologyreview.com/feed/", "name": "MIT Tech Review"},
        {"type": "rss", "url": "https://9to5mac.com/feed/", "name": "9to5Mac"},
    ],
    "business": [
        {"type": "rss", "url": "https://feeds.bbci.co.uk/news/business/rss.xml", "name": "BBC Business"},
        {"type": "rss", "url": "https://www.cnbc.com/id/10001147/device/rss/rss.html", "name": "CNBC"},
        {"type": "rss", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml", "name": "WSJ World"},
        {"type": "rss", "url": "https://www.forbes.com/business/feed/", "name": "Forbes"},
        {"type": "rss", "url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms", "name": "ET"},
        {"type": "rss", "url": "https://www.business-standard.com/rss/home_page_top_stories.rss", "name": "Business Standard"},
        {"type": "rss", "url": "https://www.ft.com/?format=rss", "name": "Financial Times"},
        {"type": "rss", "url": "https://www.livemint.com/rss/news", "name": "Mint"},
        {"type": "rss", "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", "name": "Reuters Biz"},
    ],
    "science": [
        {"type": "rss", "url": "https://www.space.com/feeds/all", "name": "Space.com"},
        {"type": "rss", "url": "https://www.livescience.com/feeds/all", "name": "Live Science"},
        {"type": "rss", "url": "https://www.sciencedaily.com/rss/all.xml", "name": "ScienceDaily"},
        {"type": "rss", "url": "https://www.nature.com/nature.rss", "name": "Nature"},
        {"type": "rss", "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss", "name": "NASA"},
        {"type": "rss", "url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "name": "BBC Science"},
        {"type": "rss", "url": "https://www.scientificamerican.com/feed/", "name": "Scientific American"},
        {"type": "rss", "url": "https://www.newscientist.com/feed/home/", "name": "New Scientist"},
        {"type": "rss", "url": "https://phys.org/rss-feed/", "name": "Phys.org"},
    ],
    "ai": [
        {"type": "rss", "url": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml", "name": "Verge AI"},
        {"type": "rss", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "name": "TechCrunch AI"},
        {"type": "rss", "url": "https://arstechnica.com/tag/artificial-intelligence/feed/", "name": "Ars AI"},
        {"type": "rss", "url": "https://www.wired.com/feed/tag/ai/latest/rss", "name": "Wired AI"},
        {"type": "rss", "url": "https://openai.com/blog/rss.xml", "name": "OpenAI Blog"},
        {"type": "rss", "url": "https://blog.google/technology/ai/rss/", "name": "Google AI Blog"},
        {"type": "rss", "url": "https://huggingface.co/blog/feed.xml", "name": "Hugging Face"},
        {"type": "rss", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "name": "MIT AI"},
        {"type": "rss", "url": "https://venturebeat.com/category/ai/feed/", "name": "VentureBeat AI"},
    ],
}

SEARCH_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "is", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "shall", "can", "this", "that", "these", "those", "it",
    "its", "not", "no", "so", "than", "too", "very", "just", "about", "up",
    "out", "if", "when", "where", "who", "which", "what", "from", "as",
    "into", "like", "through", "after", "before", "between", "under", "again",
    "further", "then", "once", "here", "there", "all", "each", "every", "both",
    "few", "more", "most", "other", "some", "such", "only", "own", "same",
    "new", "says", "said", "latest", "news", "today", "description", "images",
    "image", "photo", "video", "read", "also", "their", "they", "them", "his",
    "her", "our", "your", "over", "into", "than", "first", "last", "next",
    "year", "years", "time", "week", "month", "day", "days", "best", "during",
    "against", "while", "still", "even", "much", "many", "how", "why", "been",
}
