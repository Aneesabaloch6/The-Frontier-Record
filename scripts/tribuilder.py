#!/usr/bin/env python3
"""
tribuilder.py — bilingual (English + Urdu) pages with the news-portal shell:
trending-tags strip, centered logo, horizontal category nav, breadcrumb.
build_home_tri.py imports shell()/crumb helpers so every page is identical.
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

EMBLEM = (
    '<svg class="brand-emblem" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<rect x="4" y="4" width="92" height="92" rx="16" fill="none" stroke="var(--amber)" stroke-width="5"/>'
    '<rect x="30" y="26" width="40" height="10" fill="var(--amber)"/>'
    '<rect x="30" y="26" width="10" height="50" fill="var(--amber)"/>'
    '<rect x="30" y="45" width="28" height="9" fill="var(--amber)"/>'
    '<circle cx="69" cy="67" r="5.5" fill="var(--amber)"/></svg>'
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
    "home":     {"en": "Home",    "ur": "صفحہ اول"},
    "archive":  {"en": "Archive", "ur": "آرکائیو"},
    "trending": {"en": "Trending", "ur": "نمایاں"},
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


def head(page_title: str, description: str, site: dict,
         og_image: str | None = None, page_url: str = "",
         og_type: str = "article") -> str:
    """Page <head>. og_image / page_url are site-root relative (e.g.
    'og/slug.png', 'articles/slug.html') and are made absolute with base_url,
    because X, WhatsApp and Facebook all reject relative image URLs."""
    base = site.get("base_url", "").rstrip("/")
    img_abs = f"{base}/{og_image or 'static/og-default.png'}"
    url_abs = f"{base}/{page_url}" if page_url else f"{base}/"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(page_title)}</title>
<meta name="description" content="{esc(description)}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{esc(page_title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:site_name" content="{esc(site['title'])}">
<meta property="og:url" content="{esc(url_abs)}">
<meta property="og:image" content="{esc(img_abs)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(page_title)}">
<meta property="og:locale" content="en_US">
<meta property="og:locale:alternate" content="ur_PK">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(page_title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{esc(img_abs)}">
<link rel="canonical" href="{esc(url_abs)}">
<link rel="icon" href="/static/mark.svg">
<link rel="alternate" type="application/rss+xml" title="{esc(site['title'])}" href="/feed.xml">
{FONTS}
<style>{STYLE}{URDU_CSS}</style>
</head>
<body class="lang-en">
<a class="skip" href="#main">Skip to content</a>"""


def _brand_words(title: str) -> str:
    parts = title.split()
    if len(parts) > 1:
        head_words = " ".join(parts[:-1])
        return f'{esc(head_words)} <span class="amber">{esc(parts[-1])}</span>'
    return esc(title)


def header(site: dict, nav_topics: list, active: str = "") -> str:
    slugs = {t["slug"] for t in nav_topics}
    tag_links = []
    for label in site.get("trending", []):
        s = _slug(label)
        href = f"/topics/{s}.html" if s in slugs else "/"
        tag_links.append(f'<a href="{href}">#{esc(label)}</a>')
    trending = "".join(tag_links)

    menu = [f'<a href="/" class="{ "active" if active=="home" else "" }">{bi(UI["home"]["en"], UI["home"]["ur"])}</a>']
    for t in nav_topics:
        cls = "active" if t["slug"] == active else ""
        menu.append(f'<a href="/topics/{t["slug"]}.html" class="{cls}">{bi(esc(t["en"]), esc(t["ur"]))}</a>')
    menu.append(f'<a href="/archive.html" class="{ "active" if active=="archive" else "" }">'
                f'{bi(UI["archive"]["en"], UI["archive"]["ur"])}</a>')

    return f"""<header class="site-head">
  <div class="topbar"><div class="topbar-inner">
    <span class="topbar-label">{bi(UI['trending']['en'], UI['trending']['ur'])}</span>
    <nav class="topbar-tags" aria-label="Trending tags">{trending}</nav>
  </div></div>
  <div class="brandbar">
    <a class="brand-lockup" href="/">
      {EMBLEM}
      <span class="brand-words">
        <span class="brand-name">{_brand_words(site['title'])}</span>
        <span class="brand-sub">{esc(site.get('brand_sub', site['tagline']))}</span>
      </span>
    </a>
  </div>
  <div class="navbar"><div class="navbar-inner">
    <nav class="menu" aria-label="Primary">{''.join(menu)}</nav>
    <div class="nav-tools">
      <div class="langtoggle" role="group" aria-label="Language">
        <button type="button" data-langbtn="en" onclick="bsSetLang('en')">EN</button>
        <button type="button" data-langbtn="ur" onclick="bsSetLang('ur')">اردو</button>
      </div>
    </div>
  </div></div>
</header>"""


def crumb_bar(crumb: list) -> str:
    if not crumb:
        return ""
    parts = []
    for i, c in enumerate(crumb):
        label = bi(c["en"], c["ur"])
        if c.get("href"):
            parts.append(f'<a href="{c["href"]}">{label}</a>')
        else:
            parts.append(f'<span>{label}</span>')
        if i < len(crumb) - 1:
            parts.append('<span class="sep">&rsaquo;</span>')
    return f'<div class="crumb"><div class="crumb-inner">{"".join(parts)}</div></div>'


def footer(site: dict, year: int) -> str:
    return f"""<footer class="site-foot"><div class="site-foot-inner">
    <div class="site-foot-note">{esc(site['footer_note'])}</div>
    <div class="site-foot-copy">&copy; {year} {esc(site['title'])}</div>
  </div></footer>"""


def shell(inner: str, page_title: str, description: str, site: dict,
          year: int, nav_topics: list, active: str = "", crumb: list | None = None,
          og_image: str | None = None, page_url: str = "",
          og_type: str = "article") -> str:
    return f"""{head(page_title, description, site, og_image, page_url, og_type)}
{header(site, nav_topics, active)}
{crumb_bar(crumb or [])}
<main id="main" class="container">
{inner}
</main>
{footer(site, year)}
<script>{TOGGLE_JS}</script>
</body></html>"""


def _slug(value: str) -> str:
    import re
    v = re.sub(r"[^\w\s-]", "", str(value).strip().lower())
    return re.sub(r"[\s_-]+", "-", v).strip("-") or "untitled"


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

    crumb = [
        {"en": UI["home"]["en"], "ur": UI["home"]["ur"], "href": "/"},
        {"en": esc(article["title_en"]), "ur": esc(article["title_ur"]), "href": None},
    ]
    out = dist / "articles" / f"{article['slug']}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(shell(inner, article['title_en'], article['summary_en'],
                         site, year, nav_topics, active="", crumb=crumb,
                         og_image=article.get("og_image"), page_url=article["url"],
                         og_type="article"), encoding="utf-8")
