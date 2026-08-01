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


def _plain_from_html(text: str, max_len: int = 700) -> str:
    """Strip tags / collapse whitespace for AniList & MAL blurbs."""
    if not text:
        return ""
    t = re.sub(r"<br\s*/?>", "\n", str(text), flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(re.sub(r"\s+", " ", t)).strip()
    if max_len and len(t) > max_len:
        return t[: max_len - 1].rstrip() + "…"
    return t

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


def _html_body_text(raw: str, limit: int = 14000) -> str:
    """Turn RSS/HTML fragments into full article text (keep paragraphs)."""
    if not raw:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    # Plain text already
    if "<" not in s:
        text = html.unescape(re.sub(r"\s+", " ", s)).strip()
    else:
        soup = _soup(s)
        for bad in soup(["script", "style", "noscript", "iframe", "svg"]):
            try:
                bad.decompose()
            except Exception:
                pass
        paras: list[str] = []
        for tag in soup.find_all(["p", "h2", "h3", "h4", "li", "blockquote"]):
            t = html.unescape(tag.get_text(" ", strip=True) or "")
            t = re.sub(r"\s+", " ", t).strip()
            if len(t) >= 20:
                paras.append(t)
        if paras:
            text = "\n\n".join(paras)
        else:
            text = soup.get_text("\n", strip=True)
            text = html.unescape(re.sub(r"[ \t]+", " ", text))
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if "\n" not in text:
                text = re.sub(r"\s+", " ", text)
    # Soft-break interview / Q&A walls of text for the reader
    if text.count("\n\n") < 2 and len(text) > 900:
        text = re.sub(
            r"\s+(?=(?:"
            r"Tell me |What |How |Why |Was |Were |Do you |Did you |"
            r"Can you |Could you |Where |When |"
            r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)?\s*:\s"
            r"))",
            "\n\n",
            text,
        )
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
    """Scrape page when RSS is stub/teaser; skip if we already have a full story."""
    d = (desc or "").strip()
    if article.get("body_fetched"):
        if _looks_like_bio(d) or len(d) < 280:
            return True
        return False
    # Truncated teaser (old 1400-cap or feed ellipsis)
    if d.endswith("…") or d.endswith("..."):
        return True
    if _is_stub(d) or _looks_like_bio(d):
        return True
    # Solid content:encoded already (Crunchyroll, many WordPress feeds)
    if len(d) >= 900:
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
    """Prefer full content:encoded / Atom content over short RSS summary."""
    chunks: list[str] = []
    if hasattr(entry, "content") and entry.content:
        for block in entry.content:
            chunks.append(block.get("value", "") or "")
    # Some feeds put the long body in content_encoded
    for key in ("content_encoded", "content:encoded"):
        val = entry.get(key) if hasattr(entry, "get") else None
        if not val:
            val = getattr(entry, key, None)
        if val:
            chunks.append(val if isinstance(val, str) else str(val))
    for key in ("summary", "description", "subtitle"):
        chunks.append(entry.get(key, "") or "")

    best = ""
    for c in chunks:
        if not c:
            continue
        # Always prefer body formatter for long payloads (plain or HTML)
        if len(c) > 400:
            text = _html_body_text(c, 14000)
        else:
            text = _clean_text(c, 14000)
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

    def _anilist_gql(self, query: str, variables: dict | None = None) -> dict:
        """AniList GraphQL (no auth). Returns data dict or {}."""
        try:
            time.sleep(random.uniform(0.15, 0.4))
            r = self.client.post(
                "https://graphql.anilist.co",
                json={"query": query, "variables": variables or {}},
                timeout=20,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            r.raise_for_status()
            payload = r.json()
            if payload.get("errors"):
                return {}
            return payload.get("data") or {}
        except Exception:
            return {}

    def _anilist(self, limit: int = 24) -> list:
        """AniList: new anime/manga + recent community reviews."""
        arts: list[dict] = []
        seen: set[str] = set()

        def _add(item: dict) -> None:
            url = item.get("url") or ""
            if not url or url in seen or len(arts) >= limit:
                return
            seen.add(url)
            arts.append(item)

        media_q = """
        query ($mediaType: MediaType, $page: Int) {
          Page(page: $page, perPage: 10) {
            media(type: $mediaType, sort: ID_DESC) {
              id
              title { romaji english native }
              type
              format
              status
              siteUrl
              description(asHtml: false)
              coverImage { large }
              genres
              startDate { year month day }
            }
          }
        }
        """
        for media_type, label in (("ANIME", "Anime"), ("MANGA", "Manga")):
            data = self._anilist_gql(media_q, {"mediaType": media_type, "page": 1})
            for m in (data.get("Page") or {}).get("media") or []:
                titles = m.get("title") or {}
                name = (
                    titles.get("english")
                    or titles.get("romaji")
                    or titles.get("native")
                    or "Untitled"
                )
                genres = ", ".join((m.get("genres") or [])[:6])
                fmt = m.get("format") or label
                status = m.get("status") or ""
                desc = _plain_from_html(m.get("description") or "")
                bits = [f"New {label.lower()} on AniList ({fmt})."]
                if status:
                    bits.append(f"Status: {status.replace('_', ' ').title()}.")
                if genres:
                    bits.append(f"Genres: {genres}.")
                if desc:
                    bits.append(desc)
                sd = m.get("startDate") or {}
                pub = ""
                if sd.get("year"):
                    pub = f"{sd.get('year')}-{sd.get('month') or 1:02d}-{sd.get('day') or 1:02d}"
                cover = (m.get("coverImage") or {}).get("large") or ""
                _add(
                    {
                        "title": f"{label}: {name}",
                        "source": "AniList",
                        "author": "",
                        "published": pub,
                        "description": " ".join(bits)[:900] or "No description",
                        "url": m.get("siteUrl") or f"https://anilist.co/{label.lower()}/{m.get('id')}",
                        "image_url": cover,
                        "lang": "EN",
                    }
                )

        review_q = """
        query ($page: Int) {
          Page(page: $page, perPage: 10) {
            reviews(sort: CREATED_AT_DESC) {
              id
              summary
              body(asHtml: false)
              score
              siteUrl
              createdAt
              user { name }
              media {
                title { romaji english }
                type
                siteUrl
                coverImage { large }
              }
            }
          }
        }
        """
        data = self._anilist_gql(review_q, {"page": 1})
        for rev in (data.get("Page") or {}).get("reviews") or []:
            media = rev.get("media") or {}
            mt = media.get("title") or {}
            mname = mt.get("english") or mt.get("romaji") or "Untitled"
            score = rev.get("score")
            score_bit = f" — {score}/100" if score is not None else ""
            summary = _plain_from_html(rev.get("summary") or "")
            body = _plain_from_html(rev.get("body") or "")
            desc = summary or body or "AniList community review."
            if body and summary and body != summary:
                desc = f"{summary} {body}"[:900]
            author = ((rev.get("user") or {}).get("name")) or ""
            pub = ""
            try:
                pub = time.strftime("%Y-%m-%d", time.gmtime(int(rev.get("createdAt") or 0)))
            except Exception:
                pub = ""
            cover = (media.get("coverImage") or {}).get("large") or ""
            _add(
                {
                    "title": f"Review · {mname}{score_bit}",
                    "source": "AniList Reviews",
                    "author": author,
                    "published": pub,
                    "description": desc[:900] or "No description",
                    "url": rev.get("siteUrl")
                    or f"https://anilist.co/review/{rev.get('id')}",
                    "image_url": cover,
                    "lang": "EN",
                }
            )

        return arts[:limit]

    def _mal(self, limit: int = 24) -> list:
        """MyAnimeList news RSS + Jikan seasonal/top manga cards."""
        arts: list[dict] = []
        seen: set[str] = set()

        def _add_all(items: list) -> None:
            for a in items:
                url = a.get("url") or ""
                if not url or url in seen:
                    continue
                seen.add(url)
                arts.append(a)
                if len(arts) >= limit:
                    return

        try:
            _add_all(self._rss("https://myanimelist.net/rss/news.xml", "MyAnimeList"))
        except Exception:
            pass
        if len(arts) >= limit:
            return arts[:limit]

        # Jikan (unofficial MAL API) — seasonal anime + top manga
        for endpoint, label in (
            ("https://api.jikan.moe/v4/seasons/now?limit=12", "Airing now"),
            ("https://api.jikan.moe/v4/top/manga?limit=10", "Top manga"),
        ):
            if len(arts) >= limit:
                break
            try:
                time.sleep(random.uniform(0.35, 0.7))  # Jikan rate limit
                r = self.client.get(
                    endpoint,
                    timeout=20,
                    headers={"Accept": "application/json", "User-Agent": "worldnews-cli"},
                )
                r.raise_for_status()
                rows = (r.json() or {}).get("data") or []
            except Exception:
                continue
            for row in rows:
                if len(arts) >= limit:
                    break
                titles = row.get("titles") or []
                name = row.get("title") or ""
                for t in titles:
                    if (t.get("type") or "").lower() == "english" and t.get("title"):
                        name = t["title"]
                        break
                if not name:
                    continue
                url = (row.get("url") or "").strip()
                if not url or url in seen:
                    continue
                synopsis = _plain_from_html(row.get("synopsis") or "")[:700]
                kind = "Manga" if "manga" in endpoint else "Anime"
                score = row.get("score")
                score_bit = f" Score {score}." if score else ""
                genres = ", ".join(
                    g.get("name") for g in (row.get("genres") or [])[:5] if g.get("name")
                )
                desc_bits = [f"{label} on MyAnimeList ({kind}).{score_bit}"]
                if genres:
                    desc_bits.append(f"Genres: {genres}.")
                if synopsis:
                    desc_bits.append(synopsis)
                images = row.get("images") or {}
                jpg = (images.get("jpg") or {}) if isinstance(images, dict) else {}
                img = jpg.get("large_image_url") or jpg.get("image_url") or ""
                pub = ""
                aired = row.get("aired") or row.get("published") or {}
                if isinstance(aired, dict):
                    pub = (aired.get("from") or "")[:10]
                seen.add(url)
                arts.append(
                    {
                        "title": f"{kind}: {name}",
                        "source": "MyAnimeList",
                        "author": "",
                        "published": pub,
                        "description": " ".join(desc_bits)[:900] or "No description",
                        "url": url,
                        "image_url": img,
                        "lang": "EN",
                    }
                )
        return arts[:limit]

    def _hn(self, limit: int = 40) -> list:
        """Hacker News via official RSS, with Firebase API fill for depth."""
        arts: list[dict] = []
        seen: set[str] = set()
        api = "https://hacker-news.firebaseio.com/v0"

        def _add(a: dict) -> None:
            url = a.get("url") or ""
            if not url or url in seen or len(arts) >= limit:
                return
            seen.add(url)
            arts.append(a)

        # Official RSS (hnrss.org often SSL-fails under cloudscraper)
        try:
            for a in self._rss("https://news.ycombinator.com/rss", "Hacker News"):
                _add(a)
                if len(arts) >= limit:
                    return arts[:limit]
        except Exception:
            pass

        need = limit - len(arts)
        if need <= 0:
            return arts[:limit]

        ids: list[int] = []
        for endpoint in ("topstories", "beststories", "newstories"):
            if len(ids) >= need + 10:
                break
            try:
                r = self.client.get(
                    f"{api}/{endpoint}.json",
                    timeout=20,
                    headers={"Accept": "application/json", "User-Agent": "worldnews-cli"},
                )
                r.raise_for_status()
                chunk = r.json() or []
                if isinstance(chunk, list):
                    ids.extend(int(x) for x in chunk[: need + 15] if x is not None)
            except Exception:
                continue

        uniq: list[int] = []
        seen_id: set[int] = set()
        for i in ids:
            if i in seen_id:
                continue
            seen_id.add(i)
            uniq.append(i)

        for item_id in uniq:
            if len(arts) >= limit:
                break
            try:
                r = self.client.get(
                    f"{api}/item/{item_id}.json",
                    timeout=12,
                    headers={"Accept": "application/json", "User-Agent": "worldnews-cli"},
                )
                r.raise_for_status()
                row = r.json() or {}
            except Exception:
                continue
            if not isinstance(row, dict) or row.get("type") not in ("story", "job"):
                continue
            if row.get("dead") or row.get("deleted"):
                continue
            title = html.unescape(str(row.get("title") or "")).strip()
            if _is_junk_headline(title):
                continue
            link = (row.get("url") or "").strip()
            if not link:
                link = f"https://news.ycombinator.com/item?id={item_id}"
            if link in seen:
                continue
            score = row.get("score")
            comments = row.get("descendants")
            by = row.get("by") or ""
            bits = []
            if score is not None:
                bits.append(f"{score} points")
            if comments is not None:
                bits.append(f"{comments} comments")
            bits.append("on Hacker News")
            meta = " · ".join(bits)
            body = _plain_from_html(row.get("text") or "", max_len=1200)
            desc = f"{meta}. {body}".strip() if body else f"{meta}."
            pub = ""
            ts = row.get("time")
            if isinstance(ts, (int, float)) and ts > 0:
                try:
                    pub = time.strftime("%Y-%m-%d", time.gmtime(ts))
                except Exception:
                    pub = ""
            _add(
                {
                    "title": title,
                    "source": "Hacker News",
                    "author": by,
                    "published": pub,
                    "description": desc or "No description",
                    "url": link,
                    "image_url": "",
                    "lang": "EN",
                    "hn_id": item_id,
                    "hn_discussion": f"https://news.ycombinator.com/item?id={item_id}",
                }
            )
        return arts[:limit]

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
        # RSS already has a full story — still try image if missing
        if not need_body and not need_img:
            out["body_fetched"] = True
            return out
        if not need_body and need_img:
            r = self._get(url, timeout=20, delay=delay)
            if r:
                scraped = scrape_article_page(r.content, url)
                if scraped.get("image_url"):
                    out["image_url"] = scraped["image_url"]
            out["body_fetched"] = True
            return out

        r = self._get(url, timeout=25, delay=delay)
        if not r:
            return out  # retry next open — do not mark fetched
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
                # Ignore generic site titles (SPA shells)
                st = scraped["title"].strip().lower()
                if "crunchyroll news" not in st and st not in {
                    "home",
                    "news",
                    "anime news",
                }:
                    out["title"] = scraped["title"]
        if scraped.get("image_url"):
            if need_img or not out.get("image_url"):
                out["image_url"] = scraped["image_url"]
        if need_body:
            body = (scraped.get("description") or "").strip()
            rss = (out.get("description") or "").strip()
            adopted = False
            if body and len(body) > max(200, len(rss)):
                out["description"] = body
                adopted = True
            elif body and (_is_stub(rss) or len(body) > len(rss) + 100):
                out["description"] = body
                adopted = True
            # Mark complete only when we have a real story (page or long RSS)
            final = (out.get("description") or "").strip()
            if adopted or (len(final) >= 800 and not final.endswith("…")):
                out["body_fetched"] = True
                out["lang"] = detect_language(
                    f"{out.get('title', '')} {out.get('description', '')}",
                    out.get("lang", ""),
                )
        return out

    def fetch(self, cat):
        """Fetch category feeds; never abort the whole category on one bad source."""
        sources = NEWS_SOURCES.get(cat, [])
        arts, seen = [], set()
        for s in sources:
            try:
                stype = s.get("type")
                if stype == "ann":
                    items = self._ann(12)
                elif stype == "anilist":
                    items = self._anilist(int(s.get("limit") or 24))
                elif stype == "mal":
                    items = self._mal(int(s.get("limit") or 24))
                elif stype == "hn":
                    items = self._hn(int(s.get("limit") or 40))
                elif stype == "rss":
                    items = self._rss(s.get("url", ""), s.get("name", ""))
                else:
                    items = []
            except Exception:
                items = []
            if not items:
                continue
            for a in items:
                try:
                    url = a.get("url") or ""
                    if not url or url in seen:
                        continue
                    if not _article_matches_category(
                        a, cat, trusted_feed=bool(s.get("trust"))
                    ):
                        continue
                    arts.append(a)
                    seen.add(url)
                except Exception:
                    continue
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


# Category relevance — keep Marvel/Anime/etc. on-topic when feeds mix genres.
# Empty / missing key → no keyword filter (general, sports, …).
CATEGORY_KEYWORDS = {
    "anime": [
        "anime",
        "manga",
        "otaku",
        "seinen",
        "shonen",
        "shoujo",
        "shojo",
        "studio",
        "crunchyroll",
        "funimation",
        "myanimelist",
        "anilist",
        "animenewsnetwork",
        "light novel",
        "cosplay",
        "waifu",
        "isekai",
        "mecha",
        "idol",
        "vocaloid",
        "japanimation",
    ],
    "marvel": [
        "marvel",
        "mcu",
        "avengers",
        "spider-man",
        "spiderman",
        "iron man",
        "ironman",
        "captain america",
        "thor",
        "hulk",
        "black panther",
        "doctor strange",
        "dr strange",
        "x-men",
        "xmen",
        "wolverine",
        "deadpool",
        "guardians of the galaxy",
        "fantastic four",
        "ant-man",
        "antman",
        "scarlet witch",
        "loki",
        "hawkeye",
        "daredevil",
        "punisher",
        "venom",
        "moon knight",
        "she-hulk",
        "ms. marvel",
        "ms marvel",
        "wandavision",
        "multiverse",
        "stan lee",
        "disney+",
        "disney plus",
    ],
    "dc": [
        "dc comics",
        "dc universe",
        "dceu",
        "batman",
        "superman",
        "wonder woman",
        "justice league",
        "joker",
        "aquaman",
        "flash",
        "green lantern",
        "cyborg",
        "harley quinn",
        "suicide squad",
        "shazam",
        "peacemaker",
        "black adam",
        "gotham",
        "metropolis",
        "arkham",
        "james gunn",
        "warner bros",
        "hbo max",
        "max original",
    ],
    "bollywood": [
        "bollywood",
        "hindi film",
        "hindi movie",
        "box office",
        "tollywood",
        "mumbai",
        "filmfare",
        "pinkvilla",
        "hungama",
    ],
    "mollywood": [
        "mollywood",
        "malayalam",
        "kerala",
        "kochi",
        "mammootty",
        "mohanlal",
        "dulquer",
        "prithviraj",
        "fahadh",
        "manorama",
        "onmanorama",
    ],
    "ai": [
        "ai",
        "artificial intelligence",
        "machine learning",
        "llm",
        "chatgpt",
        "openai",
        "gemini",
        "claude",
        "deepseek",
        "anthropic",
        "neural",
        "generative",
        "diffusion",
        "transformer",
        "huggingface",
        "hugging face",
    ],
}

# Negative keywords — drop cross-contamination (e.g. DC stories in Marvel feeds).
CATEGORY_EXCLUDE = {
    "marvel": [
        "dc",
        "dc comics",
        "dceu",
        "dc characters",
        "dc's",
        "dc’s",
        "batman",
        "superman",
        "wonder woman",
        "justice league",
        "joker",
        "aquaman",
        "harley quinn",
        "gotham",
        "mr. freeze",
        "mr freeze",
        "riddler",
        "clayface",
        "green lantern",
        "shazam",
        "peacemaker",
        "black adam",
    ],
    "dc": [
        "marvel",
        "mcu",
        "avengers",
        "spider-man",
        "spiderman",
        "iron man",
        "x-men",
        "wolverine",
        "deadpool",
        "stan lee",
        "doctor doom",
        "fantastic four",
        "guardians of the galaxy",
    ],
}


def _keyword_in(text: str, key: str) -> bool:
    """Substring match; short tokens (ai, dc) use word boundaries."""
    k = (key or "").lower().strip()
    if not k:
        return False
    if len(k) <= 3 or k in {"flash", "thor", "hulk", "loki", "venom"}:
        return re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text) is not None
    return k in text


def _article_matches_category(
    article: dict, cat: str, *, trusted_feed: bool = False
) -> bool:
    """True if article belongs in ``cat`` (keyword allow + exclude lists)."""
    keys = CATEGORY_KEYWORDS.get(cat)
    if not keys:
        return True
    title_desc = (
        f"{article.get('title', '')} {article.get('description', '')} "
        f"{article.get('url', '')}"
    ).lower()
    full = f"{title_desc} {article.get('source', '')}".lower()
    # Exclude uses title/body/url only — source names like "ScreenRant Marvel"
    # would otherwise cancel DC/Marvel cross-contamination checks.
    for bad in CATEGORY_EXCLUDE.get(cat, ()):
        if _keyword_in(title_desc, bad):
            if not any(_keyword_in(title_desc, k) for k in keys[:8]):
                return False
    if trusted_feed:
        return True
    return any(_keyword_in(full, k) for k in keys)


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
        {"type": "ann", "trust": True},
        {"type": "anilist", "trust": True, "limit": 28},
        {"type": "mal", "trust": True, "limit": 28},
        {
            "type": "rss",
            "url": "https://www.animenewsnetwork.com/all/rss.xml?ann-edition=us",
            "name": "ANN All",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.animenewsnetwork.com/news/rss.xml?ann-edition=us",
            "name": "ANN News",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.animenewsnetwork.com/interest/rss.xml?ann-edition=us",
            "name": "ANN Interest",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.animenewsnetwork.com/review/rss.xml?ann-edition=us",
            "name": "ANN Reviews",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss",
            "name": "Crunchyroll",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.animeuknews.net/feed/",
            "name": "Anime UK News",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://comicbook.com/anime/feed/",
            "name": "ComicBook Anime",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.cbr.com/category/anime/feed/",
            "name": "CBR Anime",
        },
        {
            "type": "rss",
            "url": "https://screenrant.com/tag/anime/feed/",
            "name": "ScreenRant Anime",
        },
        {
            "type": "rss",
            "url": "https://www.animenewsnetwork.com/news/rss.xml?ann-edition=uk",
            "name": "ANN UK",
            "trust": True,
        },
    ],
    "marvel": [
        {
            "type": "rss",
            "url": "https://comicbook.com/tag/marvel/feed/",
            "name": "ComicBook Marvel",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://comicbook.com/marvel/feed/",
            "name": "ComicBook Marvel Sec",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.cbr.com/tag/marvel/feed/",
            "name": "CBR Marvel",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.cbr.com/category/movies/marvel/feed/",
            "name": "CBR Marvel Movies",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://screenrant.com/tag/marvel/feed/",
            "name": "ScreenRant Marvel",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.cbr.com/tag/mcu/feed/",
            "name": "CBR MCU",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://screenrant.com/tag/mcu/feed/",
            "name": "ScreenRant MCU",
            "trust": True,
        },
    ],
    "dc": [
        {
            "type": "rss",
            "url": "https://comicbook.com/tag/dc/feed/",
            "name": "ComicBook DC",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://comicbook.com/dc/feed/",
            "name": "ComicBook DC Sec",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.cbr.com/category/comics/dc/feed/",
            "name": "CBR DC",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.cbr.com/category/movies/dc/feed/",
            "name": "CBR DC Movies",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://screenrant.com/tag/dc/feed/",
            "name": "ScreenRant DC",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://www.cbr.com/tag/batman/feed/",
            "name": "CBR Batman",
            "trust": True,
        },
        {
            "type": "rss",
            "url": "https://screenrant.com/tag/batman/feed/",
            "name": "ScreenRant Batman",
            "trust": True,
        },
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
    "hn": [
        {"type": "hn", "trust": True, "limit": 40},
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
