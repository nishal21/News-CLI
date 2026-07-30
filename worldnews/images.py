"""Terminal half-block image rendering — fills the reader width."""

from __future__ import annotations

import io
from typing import Optional

HAS_TEXTUAL_IMAGE = False
try:
    import textual_image.renderable  # noqa: F401
    from textual_image.widget import Image as TerminalImage

    HAS_TEXTUAL_IMAGE = True
except Exception:
    TerminalImage = None  # type: ignore


def bytes_to_halfblock(data: bytes, max_width: int = 72, max_height: int = 40) -> str:
    """Render image stretched to full terminal width (no side letterboxing)."""
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    except ImportError:
        return "[image: install Pillow]"

    try:
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        if im.width < 480:
            im = im.resize((im.width * 2, im.height * 2), Image.Resampling.LANCZOS)
        im = im.filter(ImageFilter.DETAIL)
        im = ImageEnhance.Contrast(im).enhance(1.12)
        im = ImageEnhance.Color(im).enhance(1.06)
        im = ImageEnhance.Sharpness(im).enhance(1.15)
    except Exception:
        return "[image: failed to decode]"

    box_w = max(24, int(max_width))
    max_h_px = max(12, int(max_height) * 2)
    if max_h_px % 2:
        max_h_px += 1

    # Scale to exact width first — fills the reader pane edge-to-edge
    scale = box_w / float(im.width)
    new_h = max(2, int(round(im.height * scale)))
    if new_h % 2:
        new_h += 1
    im = im.resize((box_w, new_h), Image.Resampling.LANCZOS)

    # Cap tall images: crop vertically (keep upper portion for faces/headlines)
    if im.height > max_h_px:
        top = int((im.height - max_h_px) * 0.25)
        im = im.crop((0, top, box_w, top + max_h_px))

    w, h = im.size
    pixels = im.load()
    lines = []
    for y in range(0, h, 2):
        parts = []
        for x in range(w):
            r1, g1, b1 = pixels[x, y]
            if y + 1 < h:
                r2, g2, b2 = pixels[x, y + 1]
            else:
                r2, g2, b2 = 18, 17, 15
            parts.append(
                f"\033[38;2;{r1};{g1};{b1}m\033[48;2;{r2};{g2};{b2}m▀\033[0m"
            )
        lines.append("".join(parts))
    return "\n".join(lines)


def optional_render(data: Optional[bytes], width: int = 72, height: int = 40) -> str:
    if not data:
        return ""
    return bytes_to_halfblock(data, max_width=width, max_height=height)


def pil_from_bytes(data: bytes):
    from PIL import Image, ImageOps

    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)
    return im.convert("RGB")


def format_article_body(desc: str) -> str:
    """Turn feed blurbs / scraped pages into readable markdown paragraphs."""
    raw = (desc or "").strip()
    if not raw:
        return "_No preview yet — loading full story from the article page…_"

    # Scraper already returns paragraph-separated text — keep it
    if "\n\n" in raw:
        paras = [p.strip() for p in raw.split("\n\n") if p.strip()]
        return "\n\n".join(paras[:50])

    if "\n" in raw and raw.count("\n") >= 2:
        paras = [p.strip() for p in raw.split("\n") if p.strip()]
        if len(paras) >= 3:
            return "\n\n".join(paras[:50])

    chunks = [c.strip() for c in re_split_paras(raw)]
    text = " ".join(chunks)
    text = re_sub_space(text)

    sentences = split_sentences(text)
    if not sentences:
        return text

    paras = []
    buf: list[str] = []
    for s in sentences:
        buf.append(s)
        joined = " ".join(buf)
        if len(buf) >= 3 or len(joined) >= 280:
            paras.append(joined)
            buf = []
    if buf:
        paras.append(" ".join(buf))
    return "\n\n".join(paras[:40])


def re_split_paras(raw: str) -> list[str]:
    import re

    parts = re.split(r"\n\s*\n", raw)
    out = []
    for p in parts:
        out.extend(x.strip() for x in p.split("\n") if x.strip())
    return out or [raw]


def re_sub_space(text: str) -> str:
    import re

    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    import re

    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", text)
    return [p.strip() for p in parts if p.strip()]
