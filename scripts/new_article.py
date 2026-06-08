#!/usr/bin/env python3
"""Create a new article stub:  python scripts/new_article.py "My Headline" Topic1 Topic2"""
import datetime as dt, re, sys
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit('Usage: python scripts/new_article.py "Title" [Topic ...]')

title = sys.argv[1]
topics = sys.argv[2:] or ["Uncategorised"]
slug = re.sub(r"[^\w\s-]", "", title.lower())
slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
today = dt.date.today().isoformat()

dest = Path(__file__).resolve().parent.parent / "content" / "articles" / f"{slug}.md"
if dest.exists():
    sys.exit(f"Already exists: {dest}")

topics_yaml = "[" + ", ".join(topics) + "]"
dest.write_text(f"""---
title: "{title}"
date: {today}
author: Editorial Desk
location: ""
topics: {topics_yaml}
summary: ""
sources: []
draft: true
---

Write your report here. Set `draft: false` when ready to publish.
""", encoding="utf-8")
print(f"Created {dest}")
