#!/usr/bin/env python3
"""
Static site generator.

Pipeline:
  content/articles/*.md   -> dist/articles/<slug>.html   (Markdown + YAML front matter)
  content/pages/*.md      -> dist/<slug>.html             (standalone pages: about, contact, methodology...)
  special/*.html          -> dist/special/<name>.html     (hand-crafted HTML, wrapped in site chrome)
  static/                 -> dist/static/                 (css, images, js, copied as-is)

Also generates:
  dist/index.html         home page (latest articles)
  dist/topics/<topic>.html  one listing page per topic/category
  dist/archive.html       full chronological archive
  dist/feed.xml           RSS feed
  dist/sitemap.xml        sitemap

Usage:
  python build.py            # build into ./dist
  python build.py --serve    # build, then serve ./dist on http://localhost:8000
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import shutil
import sys
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import frontmatter
import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ---------------------------------------------------------------------------
# Site configuration. Edit these for your deployment.
# ---------------------------------------------------------------------------
SITE = {
    "title": "The Frontier Record",
    "tagline": "Documenting human rights in Balochistan, the Pashtun belt, and Pakistan's minorities",
    "description": (
        "An independent documentation project recording enforced disappearances, "
        "displacement, and the suppression of ethnic and religious minorities."
    ),
    # Set this to your real domain once deployed (used for feed/sitemap absolute URLs).
    "base_url": "https://example.pages.dev",
    "language": "en",
    "author": "Editorial Desk",
    "footer_note": "Sourced documentation. Reproduce with attribution.",
    # How many articles to show on the home page.
    "home_count": 12,
}

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
ARTICLES_DIR = CONTENT / "articles"
PAGES_DIR = CONTENT / "pages"
SPECIAL_DIR = ROOT / "special"
STATIC_DIR = ROOT / "static"
TEMPLATES_DIR = ROOT / "templates"
DIST = ROOT / "dist"

MD_EXTENSIONS = [
    "extra",          # tables, fenced code, footnotes, def lists, attr_list...
    "toc",
    "sane_lists",
    "smarty",         # smart quotes / dashes
    "admonition",     # note/warning callout boxes
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[\s_-]+", "-", value)
    return value.strip("-") or "untitled"


def parse_date(value) -> dt.date:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if value is None:
        return dt.date.today()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return dt.date.today()


def read_articles() -> list[dict]:
    """Parse every .md article into a dict of metadata + rendered html."""
    articles: list[dict] = []
    if not ARTICLES_DIR.exists():
        return articles

    for path in sorted(ARTICLES_DIR.glob("*.md")):
        post = frontmatter.load(path)
        meta = post.metadata
        md = markdown.Markdown(extensions=MD_EXTENSIONS, output_format="html5")
        body_html = md.convert(post.content)

        title = meta.get("title") or path.stem.replace("-", " ").title()
        slug = slugify(meta.get("slug") or title)
        date = parse_date(meta.get("date"))

        topics = meta.get("topics") or meta.get("topic") or meta.get("category") or []
        if isinstance(topics, str):
            topics = [t.strip() for t in topics.split(",") if t.strip()]

        summary = meta.get("summary") or meta.get("excerpt") or ""
        if not summary:
            # First paragraph of plain text, trimmed.
            plain = re.sub(r"<[^>]+>", "", body_html)
            summary = re.sub(r"\s+", " ", plain).strip()[:220]

        articles.append({
            "title": title,
            "slug": slug,
            "date": date,
            "date_iso": date.isoformat(),
            "date_human": date.strftime("%d %B %Y"),
            "author": meta.get("author") or SITE["author"],
            "topics": topics,
            "location": meta.get("location", ""),
            "summary": summary,
            "sources": meta.get("sources") or [],
            "body": body_html,
            "url": f"articles/{slug}.html",
            "draft": bool(meta.get("draft", False)),
        })

    # Newest first; drop drafts.
    articles = [a for a in articles if not a["draft"]]
    articles.sort(key=lambda a: a["date"], reverse=True)
    return articles


def read_pages() -> list[dict]:
    pages: list[dict] = []
    if not PAGES_DIR.exists():
        return pages
    for path in sorted(PAGES_DIR.glob("*.md")):
        post = frontmatter.load(path)
        meta = post.metadata
        md = markdown.Markdown(extensions=MD_EXTENSIONS, output_format="html5")
        body_html = md.convert(post.content)
        title = meta.get("title") or path.stem.replace("-", " ").title()
        slug = slugify(meta.get("slug") or title)
        pages.append({
            "title": title,
            "slug": slug,
            "body": body_html,
            "url": f"{slug}.html",
            "nav": bool(meta.get("nav", False)),
            "nav_order": int(meta.get("nav_order", 99)),
        })
    return pages


def read_specials() -> list[dict]:
    """Hand-crafted HTML pieces. The raw file body is injected verbatim."""
    specials: list[dict] = []
    if not SPECIAL_DIR.exists():
        return specials
    for path in sorted(SPECIAL_DIR.glob("*.html")):
        raw = path.read_text(encoding="utf-8")
        # Optional <!-- title: ... --> on the first line.
        m = re.search(r"<!--\s*title:\s*(.*?)\s*-->", raw)
        title = m.group(1) if m else path.stem.replace("-", " ").title()
        specials.append({
            "title": title,
            "slug": slugify(path.stem),
            "body": raw,
            "url": f"special/{slugify(path.stem)}.html",
        })
    return specials


def build_topics(articles: list[dict]) -> dict[str, list[dict]]:
    topics: dict[str, list[dict]] = {}
    for a in articles:
        for t in a["topics"]:
            topics.setdefault(t, []).append(a)
    return dict(sorted(topics.items(), key=lambda kv: kv[0].lower()))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["topic_slug"] = slugify
    return env


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_site() -> None:
    env = make_env()
    articles = read_articles()
    pages = read_pages()
    specials = read_specials()
    topics = build_topics(articles)

    nav_pages = sorted([p for p in pages if p["nav"]], key=lambda p: p["nav_order"])

    ctx_common = {
        "site": SITE,
        "topics": topics,
        "nav_pages": nav_pages,
        "specials": specials,
        "year": dt.date.today().year,
    }

    # Clean output dir.
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    # Static assets.
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, DIST / "static")

    # Home.
    tpl_home = env.get_template("home.html")
    write(DIST / "index.html", tpl_home.render(
        **ctx_common,
        articles=articles[: SITE["home_count"]],
        page_title=SITE["title"],
        is_home=True,
    ))

    # Articles.
    tpl_article = env.get_template("article.html")
    for a in articles:
        write(DIST / a["url"], tpl_article.render(
            **ctx_common, article=a, page_title=a["title"],
        ))

    # Topic listing pages.
    tpl_list = env.get_template("listing.html")
    for topic, items in topics.items():
        write(DIST / "topics" / f"{slugify(topic)}.html", tpl_list.render(
            **ctx_common, articles=items,
            list_title=topic, list_kind="Topic",
            page_title=f"{topic} \u2014 {SITE['title']}",
        ))

    # Full archive.
    write(DIST / "archive.html", tpl_list.render(
        **ctx_common, articles=articles,
        list_title="Full Archive", list_kind="Archive",
        page_title=f"Archive \u2014 {SITE['title']}",
    ))

    # Static content pages.
    tpl_page = env.get_template("page.html")
    for p in pages:
        write(DIST / p["url"], tpl_page.render(
            **ctx_common, page=p, page_title=p["title"],
        ))

    # Special hand-crafted HTML pieces (wrapped in site chrome).
    tpl_special = env.get_template("special.html")
    for s in specials:
        write(DIST / s["url"], tpl_special.render(
            **ctx_common, special=s, page_title=s["title"],
        ))

    # Feed + sitemap.
    write(DIST / "feed.xml", render_feed(articles))
    write(DIST / "sitemap.xml", render_sitemap(articles, pages, topics, specials))
    write(DIST / "robots.txt",
          f"User-agent: *\nAllow: /\nSitemap: {SITE['base_url'].rstrip('/')}/sitemap.xml\n")

    print(f"Built {len(articles)} articles, {len(pages)} pages, "
          f"{len(specials)} special pieces, {len(topics)} topics -> {DIST}")


def render_feed(articles: list[dict]) -> str:
    base = SITE["base_url"].rstrip("/")
    now = format_datetime(dt.datetime.now(dt.timezone.utc))
    items = []
    for a in articles[:30]:
        pub = format_datetime(
            dt.datetime.combine(a["date"], dt.time(12, 0), dt.timezone.utc))
        link = f"{base}/{a['url']}"
        items.append(f"""    <item>
      <title>{xml_escape(a['title'])}</title>
      <link>{link}</link>
      <guid isPermaLink="true">{link}</guid>
      <pubDate>{pub}</pubDate>
      <description>{xml_escape(a['summary'])}</description>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{xml_escape(SITE['title'])}</title>
    <link>{base}/</link>
    <description>{xml_escape(SITE['description'])}</description>
    <language>{SITE['language']}</language>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""


def render_sitemap(articles, pages, topics, specials) -> str:
    base = SITE["base_url"].rstrip("/")
    urls = [f"{base}/", f"{base}/archive.html"]
    urls += [f"{base}/{a['url']}" for a in articles]
    urls += [f"{base}/{p['url']}" for p in pages]
    urls += [f"{base}/topics/{slugify(t)}.html" for t in topics]
    urls += [f"{base}/{s['url']}" for s in specials]
    body = "\n".join(f"  <url><loc>{xml_escape(u)}</loc></url>" for u in urls)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{body}
</urlset>
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true", help="serve dist/ after build")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    render_site()

    if args.serve:
        import functools
        import http.server
        import socketserver
        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(DIST))
        with socketserver.TCPServer(("", args.port), handler) as httpd:
            print(f"Serving {DIST} at http://localhost:{args.port} (Ctrl+C to stop)")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
