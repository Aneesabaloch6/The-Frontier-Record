#!/usr/bin/env python3
"""
tribuilder.py — builds bilingual (English + Urdu) pages with the Dossier shell.

Provides the shared chrome (fonts, CSS, fixed left sidebar, language toggle) via
shell(); build_home_tri.py imports shell() so every page is identical. build()
renders one article page.
"""

from __future__ import annotations
import html
from pathlib import Path

HERE = Path(__file__).resolve().parent
STYLE = (HERE / "_style.tmp").read_text(encoding="utf-8")
URDU_CSS = (HERE / "_urdu.tmp").read_text(encoding="utf-8")

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Space+Grotesk:wght@400;500;600;700'
    '&family=IBM+Plex+Sans:wght@400;500;600'
    '&family=IBM+Plex+Mono:wght@400;500'
    '&family=Noto+Nastaliq+Urdu:wght@400;600&display=swap" rel="stylesheet">'
)

TOGGLE_JS = """
function bsSetLang(l){
  document.body.classList.remove('lang-en','lang-ur');
  document.body.classList.add('lang-'+l);
  try{localStorage.setItem('rr_lang',l);}catch(e){}
  document.documentElement.setAttribute('lang', l==='ur'?'ur':'en');
  document.querySelectorAll('[data-langbtn]').forEach(function(b){
    b.setAttribute('aria-pressed', b.getAttribute('data-langbtn')===l ? 'true':'false');
  });
}
(function(){
  var saved='en';
  try{ saved = localStorage.getItem('rr_lang') || 'en'; }catch(e){}
  document.addEventListener('DOMContentLoaded', function(){ bsSetLang(saved); });
})();
"""

UI = {
    "latest":   {"en": "Latest",   "ur": "تازہ ترین"},
    "archive":  {"en": "Archive",  "ur": "آرکائیو"},
    "sections": {"en": "Sections", "ur": "حصے"},
    "back":     {"en": "\u2190 Back to latest", "ur": "تازہ ترین کی طرف واپس \u2192"},
    "sources":  {"en": "Sources &amp; references", "ur": "ذرائع و حوالہ جات"},
    "docnote":  {"en": "Documentation", "ur": "دستاویزات"},
    "topic":    {"en": "Section", "ur": "حصہ"},
}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def bi(en: str, ur: str, tag: str = "span", cls: str = "") -> str:
    c = ("langblock " + cls).strip()
    return (f'<{tag} class="{c}" data-lang="en">{en}</{tag}>'
            f'<{tag} class="{c}" data-lang="ur" dir="rtl">{ur}</{tag}>')


def head(page_title: str, description: str, site: dict) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(page_title)}</title>
<meta name="description" content="{esc(description)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{esc(page_title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:site_name" content="{esc(site['title'])}">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/rss+xml" title="{esc(site['title'])}" href="/feed.xml">
{FONTS}
<style>{STYLE}{URDU_CSS}</style>
</head>
<body class="lang-en">
<a class="skip" href="#main">Skip to content</a>"""


def sidebar(site: dict, nav_topics: list, year: int, active: str = "") -> str:
    def link(href, en, ur, key):
        cls = "active" if key == active else ""
        return f'<a href="{href}" class="{cls}">{bi(en, ur)}</a>'

    topics_block = ""
    if nav_topics:
        items = "".join(
            f'<a href="/topics/{t["slug"]}.html" class="{ "active" if t["slug"]==active else "" }">'
            f'{bi(esc(t["en"]), esc(t["ur"]))}</a>' for t in nav_topics)
        topics_block = (
            f'<div><div class="s-heading">{bi(UI["sections"]["en"], UI["sections"]["ur"])}</div>'
            f'<nav class="s-nav s-topics" aria-label="Sections">{items}</nav></div>')

    return f"""<aside class="sidebar">
  <div>
    <a class="brand-link" href="/">
      <span class="s-mark"></span>
      <span class="s-brand-title">{esc(site['title'])}</span>
    </a>
    <div class="s-brand-tag">{esc(site['tagline'])}</div>
  </div>
  <div class="langtoggle" role="group" aria-label="Language">
    <button type="button" data-langbtn="en" onclick="bsSetLang('en')">EN</button>
    <button type="button" data-langbtn="ur" onclick="bsSetLang('ur')">اردو</button>
  </div>
  <nav class="s-nav" aria-label="Primary">
    {link('/', UI['latest']['en'], UI['latest']['ur'], 'latest')}
    {link('/archive.html', UI['archive']['en'], UI['archive']['ur'], 'archive')}
  </nav>
  {topics_block}
  <div class="s-foot">
    <div class="s-foot-note">{esc(site['footer_note'])}</div>
    <div class="s-foot-copy">&copy; {year} {esc(site['title'])}</div>
  </div>
</aside>"""


def shell(inner: str, page_title: str, description: str, site: dict,
          year: int, nav_topics: list, active: str = "") -> str:
    return f"""{head(page_title, description, site)}
<div class="layout">
{sidebar(site, nav_topics, year, active)}
<main id="main" class="content">
{inner}
</main>
</div>
<script>{TOGGLE_JS}</script>
</body></html>"""


def _topic_tags(topics: list, lang: str) -> str:
    return "".join(
        f'<a class="tag" href="/topics/{t["slug"]}.html">{esc(t[lang])}</a>' for t in topics)


def build(article: dict, site: dict, dist: Path, year: int, nav_topics: list) -> None:
    loc = (f'<span class="dot">&middot;</span><span>{esc(article["location"])}</span>'
           if article.get("location") else "")
    sources_html = ""
    if article.get("sources"):
        items = "".join(
            f'<li><a href="{esc(s["url"])}" rel="noopener">{esc(s.get("title") or s["url"])}</a></li>'
            if isinstance(s, dict) else f"<li>{esc(s)}</li>"
            for s in article["sources"])
        sources_html = (f'<section class="sources"><h2>'
                        f'{bi(UI["sources"]["en"], UI["sources"]["ur"])}</h2>'
                        f'<ol>{items}</ol></section>')

    inner = f"""<article class="doc">
  <div class="doc-topics langblock" data-lang="en">{_topic_tags(article['topics'],'en')}</div>
  <div class="doc-topics langblock" data-lang="ur" dir="rtl">{_topic_tags(article['topics'],'ur')}</div>
  {bi(esc(article['title_en']), esc(article['title_ur']), 'h1', 'doc-title')}
  <div class="doc-meta">
    <time datetime="{article['date_iso']}">{article['date_human']}</time>
    <span class="dot">&middot;</span><span>{esc(article['author'])}</span>{loc}
  </div>
  <div class="doc-body langblock" data-lang="en">{article['body_en']}</div>
  <div class="doc-body langblock" data-lang="ur" dir="rtl">{article['body_ur']}</div>
  {sources_html}
  <div class="doc-foot"><a href="/">{bi(UI['back']['en'], UI['back']['ur'])}</a></div>
</article>"""

    out = dist / "articles" / f"{article['slug']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(shell(inner, article['title_en'], article['summary_en'],
                         site, year, nav_topics, active=""), encoding="utf-8")
