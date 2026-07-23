#!/usr/bin/env python3
"""
build_from_markdown.py — orchestrator for the bilingual (English + Urdu) site.

Operating model (same feel as Bharat Samvad):
  1. Drop English articles as Markdown in  content/*.md
  2. Run:  python scripts/build_from_markdown.py
     - For any article without an Urdu translation yet, it translates the title,
       summary, and body via Google's free web-translate endpoint and writes a
       reviewable, hand-editable file to  content/urdu/<slug>.html
     - Then it builds every page into  dist/
  3. Commit + push. Cloudflare rebuilds.

Because the Urdu files are committed, Cloudflare never has to translate at deploy
time — it just renders. Translation only happens on your machine, and you can
correct any Urdu file by hand (important for sensitive documentation).

Flags:
  --retranslate   re-translate everything, overwriting content/urdu/*.html
  --no-translate  skip translation entirely (render whatever Urdu exists)
  --serve         serve dist/ at http://localhost:8000 after building
"""

from __future__ import annotations
import argparse
import datetime as dt
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import frontmatter
import markdown
# NOTE: beautifulsoup4 (bs4) is imported lazily inside translate_html(), so it is
# only required when actually translating. Deploy builds run with --no-translate
# and need only markdown + python-frontmatter.

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tribuilder as T
import build_home_tri as H

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
URDU = CONTENT / "urdu"
STATIC = ROOT / "static"
DIST = ROOT / "dist"
TOPICS_CACHE = URDU / "_topics.json"

MD_EXT = ["extra", "toc", "sane_lists", "smarty", "admonition"]

SITE = {
    "title": "The Frontier Record",
    "title_ur": "\u062f\u06cc \u0641\u0631\u0646\u0679\u06cc\u0626\u0631 \u0631\u06cc\u06a9\u0627\u0631\u0688",
    "tagline": "Documenting human rights in Balochistan, the Pashtun belt, and Pakistan's minorities",
    "description": ("An independent documentation project recording enforced "
                    "disappearances, displacement, and the suppression of ethnic "
                    "and religious minorities."),
    "description_ur": ("\u0627\u06cc\u06a9 \u0622\u0632\u0627\u062f \u062f\u0633\u062a\u0627\u0648\u06cc\u0632\u06cc \u0645\u0646\u0635\u0648\u0628\u06c1 \u062c\u0648 \u062c\u0628\u0631\u06cc "
                       "\u06af\u0645\u0634\u062f\u06af\u06cc\u0648\u06ba\u060c \u0646\u0642\u0644 \u0645\u06a9\u0627\u0646\u06cc\u060c \u0627\u0648\u0631 \u0646\u0633\u0644\u06cc \u0648 \u0645\u0630\u06c1\u0628\u06cc "
                       "\u0627\u0642\u0644\u06cc\u062a\u0648\u06ba \u06a9\u06d2 \u062e\u0644\u0627\u0641 \u062f\u0628\u0627\u0624 \u06a9\u0648 \u0631\u06cc\u06a9\u0627\u0631\u0688 \u06a9\u0631\u062a\u0627 \u06c1\u06d2\u06d4"),
    "base_url": "https://thefrontierrecord.org",
    "author": "Editorial Desk",
    "footer_note": "Sourced documentation. Reproduce with attribution.",
    "brand_sub": "Human Rights Documentation",
    "trending": ["Balochistan", "Enforced Disappearances", "Baloch Women",
                 "Pashtun Belt", "Displacement"],
    "home_count": 12,
}

# ---------------------------------------------------------------------------
# Translation (Google free web endpoint — no API key, same as Bharat Samvad)
# ---------------------------------------------------------------------------
_GT = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=ur&dt=t&q="
_run_cache: dict[str, str] = {}


def _gt_once(text: str) -> str:
    req = urllib.request.Request(_GT + urllib.parse.quote(text),
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode("utf-8"))
    return "".join(seg[0] for seg in data[0] if seg and seg[0])


def gt(text: str):
    """Translate EN -> UR. Returns None if the endpoint is unreachable."""
    text = text or ""
    if not text.strip():
        return text
    if text in _run_cache:
        return _run_cache[text]
    try:
        if len(text) <= 1200:
            out = _gt_once(text)
        else:  # chunk long strings on sentence/space boundaries
            parts, buf = [], ""
            for tok in re.split(r"(\s+)", text):
                if len(buf) + len(tok) > 1200 and buf:
                    parts.append(_gt_once(buf)); buf = tok
                else:
                    buf += tok
            if buf:
                parts.append(_gt_once(buf))
            out = "".join(parts)
        _run_cache[text] = out
        time.sleep(0.12)
        return out
    except Exception as e:
        print(f"  [translate] endpoint unavailable ({e.__class__.__name__}); "
              f"will keep English placeholder")
        return None


def translate_html(html_str: str):
    """Translate visible text inside an HTML fragment, preserving all tags."""
    from bs4 import BeautifulSoup  # imported here so it's only needed when translating
    soup = BeautifulSoup(html_str, "html.parser")
    for node in list(soup.find_all(string=True)):
        if node.parent.name in ("code", "pre", "script", "style"):
            continue
        raw = str(node)
        core = raw.strip()
        if not core:
            continue
        tr = gt(core)
        if tr is None:
            return None
        lead = raw[: len(raw) - len(raw.lstrip())]
        trail = raw[len(raw.rstrip()):]
        node.replace_with(lead + tr + trail)
    return str(soup)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slugify(value: str) -> str:
    v = re.sub(r"[^\w\s-]", "", str(value).strip().lower())
    v = re.sub(r"[\s_-]+", "-", v)
    return v.strip("-") or "untitled"


def parse_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return dt.date.today()


def load_urdu_file(path: Path):
    raw = path.read_text(encoding="utf-8")
    mt = re.search(r"<!--\s*ur-title:\s*(.*?)\s*-->", raw)
    ms = re.search(r"<!--\s*ur-summary:\s*(.*?)\s*-->", raw)
    body = re.sub(r"<!--\s*ur-(title|summary):.*?-->\s*", "", raw).strip()
    return (mt.group(1) if mt else ""), (ms.group(1) if ms else ""), body


def write_urdu_file(path: Path, title_ur: str, summary_ur: str, body_ur: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"<!-- ur-title: {title_ur} -->\n"
        f"<!-- ur-summary: {summary_ur} -->\n{body_ur}\n",
        encoding="utf-8")


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build(retranslate=False, no_translate=False):
    articles, topic_labels = [], {}
    topics_ur = json.loads(TOPICS_CACHE.read_text(encoding="utf-8")) if TOPICS_CACHE.exists() else {}

    for path in sorted(CONTENT.glob("*.md")):
        post = frontmatter.load(path)
        m = post.metadata
        if m.get("draft"):
            continue
        title = m.get("title") or path.stem.replace("-", " ").title()
        slug = slugify(m.get("slug") or path.stem)
        date = parse_date(m.get("date"))
        summary = m.get("summary") or ""

        md = markdown.Markdown(extensions=MD_EXT, output_format="html5")
        body_en = md.convert(post.content)
        if not summary:
            plain = re.sub(r"<[^>]+>", "", body_en)
            summary = re.sub(r"\s+", " ", plain).strip()[:220]

        # topics
        raw_topics = m.get("topics") or m.get("topic") or []
        if isinstance(raw_topics, str):
            raw_topics = [t.strip() for t in raw_topics.split(",") if t.strip()]
        topics = []
        for label in raw_topics:
            if label not in topics_ur and not no_translate:
                tr = gt(label)
                if tr:
                    topics_ur[label] = tr
            topics.append({"en": label, "ur": topics_ur.get(label, label),
                           "slug": slugify(label)})
            topic_labels.setdefault(label, []).append(slug)

        # Urdu translation: load existing, or translate + write reviewable file
        upath = URDU / f"{slug}.html"
        if upath.exists() and not retranslate:
            title_ur, summary_ur, body_ur = load_urdu_file(upath)
            if not title_ur:
                title_ur = title
            if not summary_ur:
                summary_ur = summary
        elif no_translate:
            title_ur, summary_ur, body_ur = title, summary, body_en
        else:
            print(f"  translating: {slug}")
            t_ur = gt(title)
            s_ur = gt(summary)
            b_ur = translate_html(body_en)
            if None in (t_ur, s_ur, b_ur):  # offline: fall back, don't cache
                title_ur, summary_ur, body_ur = title, summary, body_en
            else:
                title_ur, summary_ur, body_ur = t_ur, s_ur, b_ur
                write_urdu_file(upath, title_ur, summary_ur, body_ur)

        articles.append({
            "slug": slug, "url": f"articles/{slug}.html",
            "date": date, "date_iso": date.isoformat(),
            "date_human": date.strftime("%d %b %Y"),
            "author": m.get("author") or SITE["author"],
            "location": m.get("location", ""),
            "topics": topics,
            "title_en": title, "title_ur": title_ur,
            "summary_en": summary, "summary_ur": summary_ur,
            "body_en": body_en, "body_ur": body_ur,
            "sources": m.get("sources") or [],
        })

    articles.sort(key=lambda a: a["date"], reverse=True)

    # persist topic translations for reuse / hand-editing
    if topics_ur:
        URDU.mkdir(parents=True, exist_ok=True)
        TOPICS_CACHE.write_text(json.dumps(topics_ur, ensure_ascii=False, indent=2),
                                encoding="utf-8")

    # topic index for topic pages
    topics_index = {}
    for label, slugs in topic_labels.items():
        s = slugify(label)
        topics_index[s] = {
            "en": label, "ur": topics_ur.get(label, label),
            "articles": [a for a in articles if any(t["slug"] == s for t in a["topics"])],
        }
    nav_topics = sorted(
        ({"en": d["en"], "ur": d["ur"], "slug": s} for s, d in topics_index.items()),
        key=lambda t: t["en"].lower())

    # output
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    if STATIC.exists():
        shutil.copytree(STATIC, DIST / "static")

    year = dt.date.today().year
    for a in articles:
        T.build(a, SITE, DIST, year, nav_topics)
    H.build_home(articles, SITE, DIST, year, nav_topics)
    H.build_archive(articles, SITE, DIST, year, nav_topics)
    H.build_topics(topics_index, SITE, DIST, year, nav_topics)
    write_feed(articles)
    write_sitemap(articles, topics_index)
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE['base_url'].rstrip('/')}/sitemap.xml\n",
        encoding="utf-8")

    print(f"Built {len(articles)} bilingual articles, {len(topics_index)} topics -> {DIST}")


def write_feed(articles):
    base = SITE["base_url"].rstrip("/")
    now = format_datetime(dt.datetime.now(dt.timezone.utc))
    items = []
    for a in articles[:30]:
        pub = format_datetime(dt.datetime.combine(a["date"], dt.time(12, 0), dt.timezone.utc))
        link = f"{base}/{a['url']}"
        items.append(f"<item><title>{xml_escape(a['title_en'])}</title>"
                     f"<link>{link}</link><guid>{link}</guid>"
                     f"<pubDate>{pub}</pubDate>"
                     f"<description>{xml_escape(a['summary_en'])}</description></item>")
    (DIST / "feed.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
        f'<title>{xml_escape(SITE["title"])}</title><link>{base}/</link>'
        f'<description>{xml_escape(SITE["description"])}</description>'
        f'<lastBuildDate>{now}</lastBuildDate>{"".join(items)}</channel></rss>\n',
        encoding="utf-8")


def write_sitemap(articles, topics_index):
    base = SITE["base_url"].rstrip("/")
    urls = [f"{base}/", f"{base}/archive.html"]
    urls += [f"{base}/{a['url']}" for a in articles]
    urls += [f"{base}/topics/{s}.html" for s in topics_index]
    body = "".join(f"<url><loc>{xml_escape(u)}</loc></url>" for u in urls)
    (DIST / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n',
        encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retranslate", action="store_true")
    ap.add_argument("--no-translate", action="store_true")
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    build(retranslate=args.retranslate, no_translate=args.no_translate)

    if args.serve:
        import functools, http.server, socketserver
        h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
        with socketserver.TCPServer(("", args.port), h) as s:
            print(f"Serving {DIST} at http://localhost:{args.port}")
            try:
                s.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
