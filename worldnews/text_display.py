"""Display-width helpers for multi-script terminal text.

Windows Terminal (and most cell-grid TUIs) mis-measure Indic / Arabic / Thai
etc. — glyphs paint wider than cell_len reports and bleed across panes.
Default ``script_mode=safe`` (and ``plain``) never paints those glyphs in the
TUI — Latin labels + browser tip. ``native`` opts into raw titles/body.
"""

from __future__ import annotations

import re
import unicodedata

from rich.cells import cell_len

try:
    from uniseg.graphemecluster import grapheme_clusters as _grapheme_clusters
except Exception:  # pragma: no cover
    def _grapheme_clusters(text: str):
        yield from text

# Scripts where terminal cell_len undercounts visual width → list bleed / overlap.
_HOSTILE_RE = re.compile(
    "["
    "\u0590-\u05FF"  # Hebrew
    "\u0600-\u06FF"  # Arabic
    "\u0700-\u074F"  # Syriac
    "\u0750-\u077F"  # Arabic Supplement
    "\u08A0-\u08FF"  # Arabic Extended-A
    "\u0870-\u089F"  # Arabic Extended-B
    "\u0900-\u097F"  # Devanagari
    "\u0980-\u09FF"  # Bengali
    "\u0A00-\u0A7F"  # Gurmukhi
    "\u0A80-\u0AFF"  # Gujarati
    "\u0B00-\u0B7F"  # Oriya
    "\u0B80-\u0BFF"  # Tamil
    "\u0C00-\u0C7F"  # Telugu
    "\u0C80-\u0CFF"  # Kannada
    "\u0D00-\u0D7F"  # Malayalam
    "\u0D80-\u0DFF"  # Sinhala
    "\u0E00-\u0E7F"  # Thai
    "\u0E80-\u0EFF"  # Lao
    "\u0F00-\u0FFF"  # Tibetan
    "\u1000-\u109F"  # Myanmar
    "\u10A0-\u10FF"  # Georgian (often OK, but keep for safety in dense rows)
    "\u1200-\u137F"  # Ethiopic
    "\u13A0-\u13FF"  # Cherokee
    "\u1780-\u17FF"  # Khmer
    "\u18A0-\u18AF"  # Mongolian Supplement-ish
    "\uA8E0-\uA8FF"  # Devanagari Extended
    "\uABC0-\uABFF"  # Meetei Mayek
    "\uFB50-\uFDFF"  # Arabic Presentation Forms-A
    "\uFE70-\uFEFF"  # Arabic Presentation Forms-B
    "]"
)

# Language tags that typically need hide+speak (even if sample is short/Latin-mixed).
HOSTILE_LANGS = frozenset(
    {
        "ML",
        "HI",
        "TA",
        "TE",
        "KN",
        "BN",
        "GU",
        "PA",
        "OR",
        "MR",
        "SI",
        "NE",
        "AS",
        "AR",
        "UR",
        "FA",
        "PS",
        "HE",
        "YI",
        "TH",
        "LO",
        "MY",
        "KM",
        "AM",
        "TI",
        "BO",
        "DZ",
        "DV",
    }
)

_CJK_RE = re.compile(
    "["
    "\u3040-\u30FF"
    "\u3400-\u4DBF"
    "\u4E00-\u9FFF"
    "\uAC00-\uD7AF"
    "]"
)

_COMPLEX_RE = re.compile(
    "["
    "\u0590-\u05FF"
    "\u0600-\u06FF"
    "\u0700-\u074F"
    "\u0750-\u077F"
    "\u08A0-\u08FF"
    "\u0900-\u097F"
    "\u0980-\u09FF"
    "\u0A00-\u0A7F"
    "\u0A80-\u0AFF"
    "\u0B00-\u0B7F"
    "\u0B80-\u0BFF"
    "\u0C00-\u0C7F"
    "\u0C80-\u0CFF"
    "\u0D00-\u0D7F"
    "\u0D80-\u0DFF"
    "\u0E00-\u0E7F"
    "\u0E80-\u0EFF"
    "\u0F00-\u0FFF"
    "\u1000-\u109F"
    "\u1200-\u137F"
    "\u1780-\u17FF"
    "\u3040-\u30FF"
    "\u3400-\u4DBF"
    "\u4E00-\u9FFF"
    "\uAC00-\uD7AF"
    "\uFB50-\uFDFF"
    "\uFE70-\uFEFF"
    "]"
)

LATIN_LANGS = frozenset(
    {
        "EN",
        "ES",
        "FR",
        "DE",
        "IT",
        "PT",
        "NL",
        "SV",
        "PL",
        "TR",
        "ID",
        "VI",
        "RO",
        "CS",
        "HU",
        "FI",
        "DA",
        "NO",
        "NB",
        "NN",
        "CA",
        "HR",
        "SK",
        "SL",
        "LT",
        "LV",
        "ET",
        "SQ",
        "AF",
        "SW",
        "TL",
        "MS",
        "FIL",
    }
)

_LANG_SHORT = {
    "ML": "Malayalam",
    "HI": "Hindi",
    "TA": "Tamil",
    "TE": "Telugu",
    "KN": "Kannada",
    "BN": "Bengali",
    "GU": "Gujarati",
    "PA": "Punjabi",
    "OR": "Odia",
    "MR": "Marathi",
    "SI": "Sinhala",
    "NE": "Nepali",
    "AS": "Assamese",
    "AR": "Arabic",
    "UR": "Urdu",
    "FA": "Persian",
    "PS": "Pashto",
    "HE": "Hebrew",
    "YI": "Yiddish",
    "TH": "Thai",
    "LO": "Lao",
    "MY": "Myanmar",
    "KM": "Khmer",
    "AM": "Amharic",
    "TI": "Tigrinya",
    "BO": "Tibetan",
    "JA": "Japanese",
    "KO": "Korean",
    "ZH": "Chinese",
}


def script_label(lang: str = "", text: str = "") -> str:
    """Human language name for tips (any hostile / tagged script)."""
    code = _lang_code(lang)
    if code and code in _LANG_SHORT:
        return _LANG_SHORT[code]
    if is_terminal_hostile(text or ""):
        return "Non-Latin"
    if code:
        return code
    return "Non-Latin"

SCRIPT_MODES = ("safe", "plain", "native")


def normalize_script_mode(mode: str | None) -> str:
    m = (mode or "safe").strip().lower()
    if m in ("ascii", "plain"):
        return "plain"
    if m in ("native", "native-titles", "raw"):
        return "native"
    return "safe"


def graphemes(text: str) -> list[str]:
    """Unicode grapheme clusters (uniseg), NFC-normalized."""
    if not text:
        return []
    text = unicodedata.normalize("NFC", text)
    try:
        return list(_grapheme_clusters(text))
    except Exception:
        return list(text)


def display_width(text: str) -> int:
    if not text:
        return 0
    try:
        return int(cell_len(text))
    except Exception:
        return len(text)


def _cluster_width(cluster: str, *, inflate_hostile: bool) -> int:
    if not cluster:
        return 0
    if cluster.isspace():
        return 1
    if inflate_hostile and _HOSTILE_RE.search(cluster):
        # Base letter in hostile script → treat as ~2 cells
        return 2
    try:
        w = int(cell_len(cluster))
        return max(0, w)
    except Exception:
        return 1


def inflated_width(text: str) -> int:
    """Width estimate that over-allocates for terminal-hostile scripts."""
    if not text:
        return 0
    if not is_terminal_hostile(text):
        return display_width(text)
    return sum(_cluster_width(g, inflate_hostile=True) for g in graphemes(text))


def truncate_display(text: str, max_cols: int, ellipsis: str = "…") -> str:
    if max_cols <= 0 or not text:
        return ""
    hostile = is_terminal_hostile(text)
    measure = inflated_width if hostile else display_width
    if measure(text) <= max_cols:
        return text
    ell_w = display_width(ellipsis)
    budget = max(1, max_cols - ell_w)
    out: list[str] = []
    used = 0
    for g in graphemes(text):
        w = _cluster_width(g, inflate_hostile=hostile)
        if used + w > budget:
            break
        out.append(g)
        used += w
    return "".join(out) + ellipsis


def pad_display(text: str, width: int, align: str = "left") -> str:
    text = text or ""
    cur = inflated_width(text) if is_terminal_hostile(text) else display_width(text)
    if cur >= width:
        return truncate_display(text, width) if cur > width else text
    pad = " " * (width - cur)
    if align == "right":
        return pad + text
    return text + pad


def is_terminal_hostile(text: str) -> bool:
    """Indic / Arabic / Thai / … — do not put raw glyphs in tight list columns."""
    return bool(text and _HOSTILE_RE.search(text))


def is_complex_script(text: str) -> bool:
    return bool(text and _COMPLEX_RE.search(text))


def is_cjk(text: str) -> bool:
    return bool(text and _CJK_RE.search(text))


def _lang_code(lang: str) -> str:
    code = (lang or "").strip().upper()
    if not code:
        return ""
    code = re.split(r"[^A-Z]+", code)[0] if code else ""
    if len(code) > 3:
        code = code[:2]
    return code


def needs_complex_layout(text: str, lang: str = "") -> bool:
    if is_complex_script(text or "") or is_terminal_hostile(text or ""):
        return True
    code = _lang_code(lang)
    if not code or code in LATIN_LANGS:
        return False
    return True


def needs_ascii_list_label(
    text: str, lang: str = "", mode: str = "safe"
) -> bool:
    """True when list row must not contain raw hostile script."""
    return should_hide_in_tui(text or "", lang, mode)


def should_hide_in_tui(text: str, lang: str = "", mode: str = "safe") -> bool:
    """Hide complex-script glyphs in the TUI (safe/plain); native shows them.

    Uses Unicode script detection **and** language tags so Hindi/Arabic/etc.
    feeds stay safe even when a title is mostly Latin.
    """
    mode = normalize_script_mode(mode)
    if mode == "native":
        return False
    if is_terminal_hostile(text or ""):
        return True
    code = _lang_code(lang)
    return bool(code and code in HOSTILE_LANGS)


def article_needs_audio_fallback(article: dict | None, mode: str = "safe") -> bool:
    """True when Speak should use full article audio (not on-screen tip text)."""
    if not article:
        return False
    title = article.get("title") or ""
    desc = article.get("description") or ""
    lang = article.get("lang") or ""
    return should_hide_in_tui(f"{title}\n{desc}", lang, mode)


def ascii_list_headline(title: str, lang: str = "") -> str:
    """Latin-safe headline for list rows (no Indic/Arabic glyphs)."""
    code = _lang_code(lang)
    ascii_bits = re.sub(r"[^\x20-\x7E]+", " ", title or "")
    ascii_bits = re.sub(r"\s+", " ", ascii_bits).strip(" -_|")
    if len(ascii_bits) >= 6:
        return ascii_bits
    name = _LANG_SHORT.get(code, "")
    if name:
        return f"{name} article"
    if code:
        return f"[{code}] article"
    return "Non-Latin article"


def soft_wrap_display(text: str, width: int) -> str:
    """NFC + wrap on grapheme clusters; inflated width for hostile scripts."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    if width < 8:
        width = 8
    hostile = is_terminal_hostile(text)
    if hostile:
        width = max(8, width // 2)

    measure = inflated_width if hostile else display_width

    lines_out: list[str] = []
    for para in text.split("\n"):
        if not para:
            lines_out.append("")
            continue
        if measure(para) <= width:
            lines_out.append(para)
            continue
        if " " in para or "\u00a0" in para:
            words = re.split(r"(\s+)", para)
            buf = ""
            for part in words:
                trial = buf + part
                if buf and measure(trial) > width:
                    lines_out.append(buf.rstrip())
                    buf = part.lstrip() if part.strip() else ""
                else:
                    buf = trial
            if buf:
                lines_out.append(buf.rstrip())
            continue
        buf = ""
        used = 0
        for g in graphemes(para):
            w = _cluster_width(g, inflate_hostile=hostile) or 1
            if used + w > width and buf:
                lines_out.append(buf)
                buf = g
                used = w
            else:
                buf += g
                used += w
        if buf:
            lines_out.append(buf)
    return "\n".join(lines_out)


def normalize_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")
