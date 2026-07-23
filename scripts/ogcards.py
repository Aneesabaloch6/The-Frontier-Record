#!/usr/bin/env python3
"""
ogcards.py — generates the "placard" images shown when a link is shared on
X, WhatsApp, Facebook, LinkedIn, Signal, etc.

Each article gets a 1200x630 PNG at  dist/og/<slug>.png  carrying the site
brand, the headline, and the date/location line. A generic  dist/og/default.png
is also produced for the home page, archive, and topic pages.

This module is DELIBERATELY FAIL-SAFE. If Pillow isn't installed or no usable
font is found, every function returns None and the build continues normally —
pages then fall back to /static/og-default.png. A missing share image must never
break publishing.

Headlines are rendered in English. Urdu (Nastaliq) needs complex text shaping
that Pillow can't do reliably, so Urdu titles are not drawn onto cards.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

W, H = 1200, 630
BG = (12, 14, 17)
AMBER = (242, 167, 59)
TEXT = (233, 231, 226)
FAINT = (140, 135, 126)

# Font lookup order: bundled first, then common system fonts.
BOLD_CANDIDATES = [
    HERE / "fonts" / "SpaceGrotesk-Bold.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/Library/Fonts/Arial Bold.ttf"),
    Path("C:/Windows/Fonts/arialbd.ttf"),
]
MED_CANDIDATES = [
    HERE / "fonts" / "SpaceGrotesk-Medium.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
]


def _find(cands):
    for p in cands:
        if p.exists():
            return str(p)
    return None


def _fonts():
    """Return (ImageFont module, bold_path, medium_path) or None if unusable."""
    try:
        from PIL import ImageFont  # noqa
    except Exception:
        return None
    b, m = _find(BOLD_CANDIDATES), _find(MED_CANDIDATES)
    if not b or not m:
        return None
    return b, m


def available() -> bool:
    """True if cards can actually be generated in this environment."""
    try:
        import PIL  # noqa
    except Exception:
        return False
    return _fonts() is not None


def _wrap(draw, text, font, max_w, max_lines):
    """Greedy word-wrap; appends an ellipsis if it has to truncate."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    # If words remain unplaced, mark truncation on the final line.
    placed = sum(len(l.split()) for l in lines)
    if placed < len(words) and lines:
        last = lines[-1]
        while last and draw.textlength(last + "\u2026", font=font) > max_w:
            last = " ".join(last.split()[:-1]) if " " in last else last[:-1]
        lines[-1] = last + "\u2026"
    return lines


def _emblem(draw, x, y, s):
    """The 'F' mark, drawn to match static/mark.svg."""
    def r(x0, y0, x1, y1):
        draw.rectangle([x + x0 * s, y + y0 * s, x + x1 * s, y + y1 * s], fill=AMBER)
    draw.rounded_rectangle([x, y, x + 100 * s, y + 100 * s], radius=16 * s,
                           outline=AMBER, width=max(1, int(5 * s)))
    r(30, 26, 70, 36)
    r(30, 26, 40, 76)
    r(30, 45, 58, 54)
    cx, cy, rr = x + 69 * s, y + 67 * s, 5.5 * s
    draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=AMBER)


def _card(title: str, meta: str, site_title: str, out: Path) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return False
    f = _fonts()
    if not f:
        return False
    bold_path, med_path = f

    try:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)

        # top accent bar
        d.rectangle([0, 0, W, 10], fill=AMBER)

        pad = 72
        # ---- brand row ----
        _emblem(d, pad, 62, 0.42)
        brand_f = ImageFont.truetype(bold_path, 27)
        bx, by = pad + 56, 74
        head, tail = site_title.rsplit(" ", 1) if " " in site_title else (site_title, "")
        d.text((bx, by), head.upper() + " ", font=brand_f, fill=TEXT)
        d.text((bx + d.textlength(head.upper() + " ", font=brand_f), by),
               tail.upper(), font=brand_f, fill=AMBER)

        # ---- headline ----
        size = 62
        while size >= 34:
            title_f = ImageFont.truetype(bold_path, size)
            lines = _wrap(d, title, title_f, W - pad * 2, 5)
            lh = int(size * 1.17)
            if len(lines) * lh <= 300:
                break
            size -= 4
        y = 178
        for ln in lines:
            d.text((pad, y), ln, font=title_f, fill=TEXT)
            y += lh

        # ---- rule + meta ----
        ry = min(max(y + 26, 470), H - 118)
        d.rectangle([pad, ry, pad + 92, ry + 5], fill=AMBER)
        if meta:
            meta_f = ImageFont.truetype(med_path, 24)
            d.text((pad, ry + 30), meta.upper(), font=meta_f, fill=FAINT)

        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, "PNG", optimize=True)
        return True
    except Exception:
        return False


def build_article_card(article: dict, site: dict, dist: Path):
    """Write dist/og/<slug>.png. Returns the site-root path, or None."""
    bits = [article.get("date_human", "")]
    if article.get("location"):
        bits.append(article["location"])
    meta = "  \u00b7  ".join([b for b in bits if b])
    out = dist / "og" / f"{article['slug']}.png"
    if _card(article["title_en"], meta, site["title"], out):
        return f"og/{article['slug']}.png"
    return None


def build_default_card(site: dict, dist: Path):
    """Write dist/og/default.png for non-article pages. Returns path or None."""
    out = dist / "og" / "default.png"
    if _card(site["description"], site.get("brand_sub", ""), site["title"], out):
        return "og/default.png"
    return None
