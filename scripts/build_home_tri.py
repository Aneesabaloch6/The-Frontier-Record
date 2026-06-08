#!/usr/bin/env python3
"""
build_home_tri.py — homepage, archive, and topic pages for the Dossier theme.
Uses the shared sidebar shell from tribuilder.py.
"""

from __future__ import annotations
from pathlib import Path

import tribuilder as T
from tribuilder import bi, esc, UI


def _entry(a: dict) -> str:
    loc = f'<div class="loc">{esc(a["location"])}</div>' if a.get("location") else ""
    te = "".join(f'<a class="tag" href="/topics/{t["slug"]}.html">{esc(t["en"])}</a>' for t in a["topics"])
    tu = "".join(f'<a class="tag" href="/topics/{t["slug"]}.html">{esc(t["ur"])}</a>' for t in a["topics"])
    return f"""<article class="entry">
  <div class="entry-meta"><time datetime="{a['date_iso']}">{a['date_human']}</time>{loc}</div>
  <div class="entry-main">
    {bi(f'<a href="/{a["url"]}">{esc(a["title_en"])}</a>',
        f'<a href="/{a["url"]}">{esc(a["title_ur"])}</a>', 'h2', 'entry-title')}
    {bi(esc(a['summary_en']), esc(a['summary_ur']), 'p', 'entry-summary')}
    <div class="tags langblock" data-lang="en">{te}</div>
    <div class="tags langblock" data-lang="ur" dir="rtl">{tu}</div>
  </div>
</article>"""


def build_home(articles, site, dist: Path, year, nav_topics):
    entries = "".join(_entry(a) for a in articles[: site.get("home_count", 12)])
    if not entries:
        entries = ('<p class="empty">No reports yet. Add a .md file to '
                   '<code>content/</code> and run the build.</p>')
    more = (f'<p class="more"><a href="/archive.html">'
            f'{bi("View full archive &rarr;", "&larr; مکمل آرکائیو دیکھیں")}</a></p>'
            if articles else "")
    inner = f"""<section class="lede">
  <div class="lede-kicker">{bi(UI['docnote']['en'], UI['docnote']['ur'])}</div>
  {bi(esc(site['title']), esc(site['title_ur']), 'h1', 'lede-title')}
  {bi(esc(site['description']), esc(site['description_ur']), 'p', 'lede-desc')}
</section>
<section class="entries" aria-label="Latest reports">{entries}</section>
{more}"""
    (dist / "index.html").write_text(
        T.shell(inner, site["title"], site["description"], site, year, nav_topics, active="latest"),
        encoding="utf-8")


def build_archive(articles, site, dist: Path, year, nav_topics):
    entries = "".join(_entry(a) for a in articles)
    inner = f"""<section class="list-head">
  <div class="kicker">{bi("Archive", "آرکائیو")}</div>
  {bi("Full Archive", "مکمل آرکائیو", 'h1', 'list-title')}
</section>
<section class="entries">{entries}</section>"""
    (dist / "archive.html").write_text(
        T.shell(inner, f"Archive \u2014 {site['title']}", site["description"],
                site, year, nav_topics, active="archive"),
        encoding="utf-8")


def build_topics(topics_index, site, dist: Path, year, nav_topics):
    out = dist / "topics"
    out.mkdir(parents=True, exist_ok=True)
    for slug, data in topics_index.items():
        entries = "".join(_entry(a) for a in data["articles"])
        inner = f"""<section class="list-head">
  <div class="kicker">{bi(UI['topic']['en'], UI['topic']['ur'])}</div>
  {bi(esc(data['en']), esc(data['ur']), 'h1', 'list-title')}
</section>
<section class="entries">{entries}</section>"""
        (out / f"{slug}.html").write_text(
            T.shell(inner, f"{data['en']} \u2014 {site['title']}", site["description"],
                    site, year, nav_topics, active=slug),
            encoding="utf-8")
