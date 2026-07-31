"""Extended persistent settings for World News CLI."""

import json
import os
from datetime import datetime

from worldnews.paths import (
    cache_dir,
    export_dir,
    migrate_to_modern,
    resolve_config_file,
    write_json,
)


class Bookmarks:
    def __init__(self):
        self.path = str(
            resolve_config_file("bookmarks.json", ".news-cli-bookmarks.json")
        )
        self.data = []
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                pass

    def save(self):
        self.path = str(
            migrate_to_modern(
                __import__("pathlib").Path(self.path), "bookmarks.json"
            )
        )
        write_json(self.path, self.data)

    def add(self, article):
        if not any(x.get("url") == article.get("url") for x in self.data):
            entry = dict(article)
            entry["bookmarked_at"] = datetime.now().strftime("%Y-%m-%d")
            self.data.insert(0, entry)
            self.save()

    def remove(self, url):
        self.data = [x for x in self.data if x.get("url") != url]
        self.save()

    def has(self, url):
        return any(x.get("url") == url for x in self.data)

    def toggle(self, article):
        url = article.get("url")
        if not url:
            return False
        if self.has(url):
            self.remove(url)
            return False
        self.add(article)
        return True


class Settings:
    DEFAULTS = {
        "auto_images": True,
        "theme": "newsroom",
        "density": "normal",
        "show_sidebar": True,
        "script_mode": "safe",
    }

    def __init__(self):
        self.path = str(
            resolve_config_file("settings.json", ".news-cli-settings.json")
        )
        self.auto_images = True
        self.theme = "newsroom"
        self.density = "normal"
        self.show_sidebar = True
        self.script_mode = "safe"
        self.read_urls = set()
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
            self.auto_images = d.get("auto_images", True)
            self.theme = d.get("theme", "newsroom")
            # Migrate retired / Hallmark-slop themes → newsroom
            if self.theme not in (
                "newsroom",
                "phosphor",
                "broadsheet",
                "nord",
                "github-dark",
                "high-contrast",
            ):
                self.theme = "newsroom"
            self.density = d.get("density", "normal")
            self.show_sidebar = d.get("show_sidebar", True)
            mode = (d.get("script_mode") or "safe").strip().lower()
            if mode in ("ascii", "plain"):
                self.script_mode = "plain"
            elif mode in ("native", "native-titles", "raw"):
                self.script_mode = "native"
            else:
                self.script_mode = "safe"
            self.read_urls = set(d.get("read_urls", []))
        except Exception:
            pass

    def save(self):
        from pathlib import Path

        self.path = str(migrate_to_modern(Path(self.path), "settings.json"))
        write_json(
            self.path,
            {
                "auto_images": self.auto_images,
                "theme": self.theme,
                "density": self.density,
                "show_sidebar": self.show_sidebar,
                "script_mode": self.script_mode,
                "read_urls": list(self.read_urls)[-500:],
            },
        )

    def toggle_auto_images(self):
        self.auto_images = not self.auto_images
        self.save()

    def set_theme(self, theme: str):
        self.theme = theme
        self.save()

    def set_density(self, density: str):
        self.density = density
        self.save()

    def set_show_sidebar(self, show: bool):
        self.show_sidebar = bool(show)
        self.save()

    def set_script_mode(self, mode: str):
        mode = (mode or "safe").strip().lower()
        if mode in ("ascii", "plain"):
            self.script_mode = "plain"
        elif mode in ("native", "native-titles", "raw"):
            self.script_mode = "native"
        else:
            self.script_mode = "safe"
        self.save()

    def mark_read(self, url: str):
        if url:
            self.read_urls.add(url)
            self.save()

    def is_read(self, url: str) -> bool:
        return url in self.read_urls


class SearchHistory:
    def __init__(self):
        self.path = str(
            resolve_config_file(
                "search-history.json", ".news-cli-search-history.json"
            )
        )
        self.data = []
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                pass

    def save(self):
        from pathlib import Path

        self.path = str(
            migrate_to_modern(Path(self.path), "search-history.json")
        )
        write_json(self.path, self.data[-100:])

    def add(self, q):
        entry = {
            "query": q,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "count": 1,
        }
        for i, old in enumerate(self.data):
            if old["query"].lower() == q.lower():
                old["count"] += 1
                old["time"] = entry["time"]
                self.data.pop(i)
                self.data.insert(0, old)
                self.save()
                return
        self.data.insert(0, entry)
        self.save()

    def clear(self):
        self.data = []
        self.save()


class CustomFeeds:
    def __init__(self):
        self.path = str(
            resolve_config_file("custom-feeds.json", ".news-cli-custom-feeds.json")
        )
        self.feeds = []
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.feeds = json.load(f)
            except Exception:
                pass

    def save(self):
        from pathlib import Path

        self.path = str(
            migrate_to_modern(Path(self.path), "custom-feeds.json")
        )
        write_json(self.path, self.feeds)

    def add(self, name, url, lang: str = ""):
        if not any(f["url"] == url for f in self.feeds):
            entry = {
                "name": name,
                "url": url,
                "added": datetime.now().strftime("%Y-%m-%d"),
            }
            if lang:
                entry["lang"] = lang
            self.feeds.append(entry)
            self.save()
            return True
        return False

    def remove(self, idx):
        if 0 <= idx < len(self.feeds):
            self.feeds.pop(idx)
            self.save()

    def fetch(self, scraper):
        """Fetch every article from every saved source (any language)."""
        arts = []
        seen = set()
        for f in self.feeds:
            chunk = scraper._rss(f["url"], f["name"])
            feed_lang = (f.get("lang") or "").strip()
            for a in chunk:
                url = a.get("url") or ""
                if url and url in seen:
                    continue
                if url:
                    seen.add(url)
                art_lang = (a.get("lang") or "").strip()
                if feed_lang and (not art_lang or art_lang.upper() == "EN"):
                    if feed_lang.upper() != "EN" or not art_lang:
                        a["lang"] = feed_lang
                a["custom"] = True
                arts.append(a)

        def _key(a):
            return (a.get("published") or "", a.get("title") or "")

        arts.sort(key=_key, reverse=True)
        return arts

    def count(self) -> int:
        return len(self.feeds)


class Cache:
    def __init__(self, ttl=600):
        self.dir = str(cache_dir())
        os.makedirs(self.dir, exist_ok=True)
        self.ttl = ttl

    def get(self, key):
        p = os.path.join(self.dir, key.replace("/", "_") + ".json")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
                if (
                    datetime.now() - datetime.fromisoformat(d["t"])
                ).total_seconds() < self.ttl:
                    return d["a"]
            except Exception:
                pass
        return None

    def set(self, key, arts):
        p = os.path.join(self.dir, key.replace("/", "_") + ".json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"t": datetime.now().isoformat(), "a": arts}, f)

    def get_stale(self, key):
        """Return cached data ignoring TTL (for offline mode)."""
        p = os.path.join(self.dir, key.replace("/", "_") + ".json")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
                return d.get("a")
            except Exception:
                pass
        return None

    def keys(self):
        out = []
        for name in os.listdir(self.dir):
            if name.endswith(".json"):
                out.append(name[:-5].replace("_", "/"))
        return out


class Exporter:
    @staticmethod
    def export_markdown(arts, filename=None):
        if not filename:
            filename = os.path.join(
                str(export_dir()),
                f"news-export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md",
            )
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"# News Export - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            for i, a in enumerate(arts, 1):
                f.write(f"## {i}. {a['title']}\n\n")
                f.write(f"**Source:** {a['source']}  \n")
                if a.get("published"):
                    f.write(f"**Date:** {a['published'][:10]}  \n")
                f.write(f"**URL:** {a['url']}\n\n")
                f.write(f"{a['description']}\n\n")
                f.write("---\n\n")
        return filename

    @staticmethod
    def export_pdf(arts, filename=None):
        if not filename:
            filename = os.path.join(
                str(export_dir()),
                f"news-export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf",
            )
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import (
                HRFlowable,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
            )

            doc = SimpleDocTemplate(filename, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []
            story.append(
                Paragraph(
                    f"<b>News Export - {datetime.now().strftime('%Y-%m-%d %H:%M')}</b>",
                    styles["Title"],
                )
            )
            story.append(Spacer(1, 20))
            for i, a in enumerate(arts, 1):
                story.append(Paragraph(f"<b>{i}. {a['title']}</b>", styles["Heading2"]))
                story.append(Paragraph(f"<i>Source: {a['source']}</i>", styles["Normal"]))
                if a.get("published"):
                    story.append(
                        Paragraph(f"<i>Date: {a['published'][:10]}</i>", styles["Normal"])
                    )
                story.append(
                    Paragraph(f"<link href='{a['url']}'>{a['url']}</link>", styles["Normal"])
                )
                story.append(Spacer(1, 6))
                story.append(Paragraph(a["description"][:500], styles["Normal"]))
                story.append(HRFlowable(width="100%", thickness=1, color="gray"))
                story.append(Spacer(1, 10))
            doc.build(story)
            return filename
        except ImportError:
            return None
