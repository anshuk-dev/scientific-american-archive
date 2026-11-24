#!/usr/bin/env python3
"""Build reader data and catalog for Scientific American archive web app.

Converts markdown articles to structured JSON bundles with clean rendered HTML,
allowing fast client-side offline reading, search, and categorization without external pip dependencies.
"""

import json
import logging
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "articles"
DIST_DIR = ROOT / "dist"
DATA_DIR = DIST_DIR / "reader-data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')

def parse_markdown_to_html(md_text):
    """Clean standard markdown converter with zero dependencies."""
    # 1. Strip YAML frontmatter
    body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', md_text, flags=re.DOTALL)
    lines = body.splitlines()

    html_parts = []
    in_list = False
    in_quote = False
    quote_lines = []

    def flush_quote():
        nonlocal in_quote, quote_lines
        if in_quote and quote_lines:
            q_text = " ".join(quote_lines)
            html_parts.append(f"<blockquote><p>{inline_format(q_text)}</p></blockquote>")
            quote_lines = []
            in_quote = False

    def flush_list():
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    def inline_format(t):
        # Escape raw HTML brackets except permitted
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Restore safe entities
        t = t.replace("&amp;bull;", "&bull;").replace("&amp;mdash;", "&mdash;").replace("&amp;ndash;", "&ndash;")
        # Links: [text](url)
        t = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', t)
        # Bold: **text**
        t = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', t)
        # Italic: *text*
        t = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', t)
        return t

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line:
            flush_quote()
            flush_list()
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^---+$', line):
            flush_quote()
            flush_list()
            html_parts.append('<hr class="editorial-divider" />')
            i += 1
            continue

        # Headings
        if line.startswith('# '):
            flush_quote()
            flush_list()
            # We already display title in hero, but retain or wrap in article header
            i += 1
            continue
        elif line.startswith('## '):
            flush_quote()
            flush_list()
            txt = line[3:].strip()
            html_parts.append(f'<h2 class="article-section-title">{inline_format(txt)}</h2>')
            i += 1
            continue
        elif line.startswith('### '):
            flush_quote()
            flush_list()
            txt = line[4:].strip()
            html_parts.append(f'<h3 class="article-subheading">{inline_format(txt)}</h3>')
            i += 1
            continue

        # Blockquote
        if line.startswith('> '):
            flush_list()
            in_quote = True
            quote_lines.append(line[2:].strip())
            i += 1
            continue
        else:
            flush_quote()

        # Unordered list
        if line.startswith('- ') or line.startswith('* '):
            if not in_list:
                html_parts.append('<ul class="article-list">')
                in_list = True
            txt = line[2:].strip()
            html_parts.append(f'<li>{inline_format(txt)}</li>')
            i += 1
            continue
        else:
            flush_list()

        # Standalone Image: ![alt](url)
        img_m = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)$', line)
        if img_m:
            alt = img_m.group(1)
            src = img_m.group(2)
            # Check next line for caption
            caption = ""
            if i + 1 < len(lines) and lines[i + 1].strip().startswith('*') and lines[i + 1].strip().endswith('*'):
                caption = lines[i + 1].strip().strip('*')
                i += 1
            
            cap_html = f'<figcaption class="figure-caption">{inline_format(caption or alt)}</figcaption>' if (caption or alt) else ''
            html_parts.append(
                f'<figure class="article-figure">'
                f'<img src="{src}" alt="{alt}" loading="lazy" class="article-img" onerror="this.style.display=\'none\'" />'
                f'{cap_html}'
                f'</figure>'
            )
            i += 1
            continue

        # Regular paragraph
        html_parts.append(f'<p class="article-p">{inline_format(line)}</p>')
        i += 1

    flush_quote()
    flush_list()
    return "\n".join(html_parts)

def parse_frontmatter(text):
    m = re.search(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            k = k.strip()
            v = v.strip()
            try:
                meta[k] = json.loads(v)
            except Exception:
                meta[k] = v.strip('"').strip("'")
    return meta

def main():
    if not ARTICLES_DIR.exists():
        logging.error(f"Articles directory not found at {ARTICLES_DIR}")
        sys.exit(1)

    md_files = sorted(ARTICLES_DIR.glob("*.md"))
    logging.info(f"Processing {len(md_files)} markdown articles...")

    catalog = []
    
    for f in md_files:
        try:
            content = f.read_text(encoding='utf-8')
            meta = parse_frontmatter(content)
            slug = meta.get('slug') or f.stem
            title = meta.get('title') or slug.replace('-', ' ').title()
            subtitle = meta.get('subtitle') or ''
            author = meta.get('author') or 'Scientific American'
            date = meta.get('date') or ''
            category = meta.get('category') or 'Science'
            read_time = meta.get('read_time') or '5 min read'
            hero_image = meta.get('hero_image') or ''
            source_url = meta.get('source_url') or f"https://www.scientificamerican.com/article/{slug}/"
            word_count = len(re.findall(r'\b\w+\b', content))

            rendered_html = parse_markdown_to_html(content)

            article_record = {
                'slug': slug,
                'title': title,
                'subtitle': subtitle,
                'author': author,
                'date': date,
                'category': category,
                'read_time': read_time,
                'hero_image': hero_image,
                'source_url': source_url,
                'word_count': word_count
            }

            # Save full article JSON
            article_payload = dict(article_record)
            article_payload['html'] = rendered_html
            out_json = DATA_DIR / f"{slug}.json"
            with open(out_json, "w", encoding="utf-8") as out_f:
                json.dump(article_payload, out_f, indent=2, ensure_ascii=False)

            catalog.append(article_record)

        except Exception as e:
            logging.warning(f"Error parsing {f.name}: {e}")

    # Sort catalog newest first
    catalog.sort(key=lambda x: x.get('date') or '', reverse=True)
    for idx, item in enumerate(catalog, 1):
        item['id'] = idx

    # Save catalog.json
    catalog_path = DATA_DIR / "catalog.json"
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved catalog with {len(catalog)} items to {catalog_path}")

    # Also sync root articles_index.json
    root_index = ROOT / "articles_index.json"
    with open(root_index, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    logging.info(f"Updated {root_index}")

if __name__ == "__main__":
    main()
