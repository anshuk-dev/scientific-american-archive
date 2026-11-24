#!/usr/bin/env python3
"""Scientific American Article Scraper & Unpaywalled Archiver.

Fetches articles from Scientific American sitemaps, extracts clean editorial markdown
with high-resolution hero images, metadata, and author biographies, and maintains
a structured catalog index.
"""

import argparse
import html
import json
import logging
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ARTICLES_DIR = ROOT / "articles"
ARTICLES_DIR.mkdir(exist_ok=True)
INDEX_FILE = ROOT / "articles_index.json"
CATALOG_FILE = ROOT / "CATALOG.md"

CTX = ssl._create_unverified_context()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()

def fetch_sitemap_urls(page=1):
    base_url = "https://www.scientificamerican.com/platform/syndication/sitemaps/articles/"
    url = base_url if page == 1 else f"{base_url}?p={page}"
    logging.info(f"Fetching sitemap page {page} from {url}...")

    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, context=CTX, timeout=20) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

    article_urls = []
    for u in root.findall('sm:url', ns):
        loc = u.find('sm:loc', ns).text.strip() if u.find('sm:loc', ns) is not None else ""
        if '/article/' in loc:
            article_urls.append(loc)

    logging.info(f"Found {len(article_urls)} article URLs in sitemap page {page}.")
    return article_urls

def parse_article_html(html_text, url):
    slug = url.strip('/').split('/')[-1]

    # 1. Parse JSON-LD
    meta = {
        'title': '',
        'subtitle': '',
        'date': '',
        'authors': [],
        'editors': [],
        'category': 'Science',
        'hero_image': '',
        'read_time': '',
        'source_url': url,
        'slug': slug
    }

    lds = re.findall(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', html_text, re.DOTALL)
    for ld in lds:
        try:
            data = json.loads(ld)
            if data.get('@type') == 'NewsArticle':
                meta['title'] = clean_html(data.get('headline') or '')
                meta['subtitle'] = clean_html(data.get('description') or '')
                meta['date'] = data.get('datePublished', '')[:10]

                # Image
                img = data.get('image')
                if isinstance(img, list) and img:
                    meta['hero_image'] = img[0]
                elif isinstance(img, dict):
                    meta['hero_image'] = img.get('url', '')
                elif isinstance(img, str):
                    meta['hero_image'] = img

                # Authors
                auths = data.get('author', [])
                if isinstance(auths, list):
                    meta['authors'] = [a.get('name') for a in auths if isinstance(a, dict) and a.get('name')]
                elif isinstance(auths, dict):
                    meta['authors'] = [auths.get('name')]

                # Editors
                eds = data.get('editor', [])
                if isinstance(eds, list):
                    meta['editors'] = [e.get('name') for e in eds if isinstance(e, dict) and e.get('name')]

                # Breadcrumb / Category
                bc = data.get('mainEntityOfPage', {}).get('breadcrumb', {}).get('itemListElement', [])
                if bc and len(bc) > 0:
                    meta['category'] = clean_html(bc[0].get('name', 'Science'))
                break
        except Exception:
            pass

    # 2. Extract Dek from HTML if not in JSON-LD
    if not meta['subtitle']:
        dek_m = re.search(r'<p[^>]*class=[\"\'][^\"\']*dek[^\"]*[\"\'][^>]*>(.*?)</p>', html_text, re.I | re.DOTALL)
        if dek_m:
            meta['subtitle'] = clean_html(dek_m.group(1))

    # 3. Read Time
    rt_m = re.search(r'(\d+)\s*min\s*read', html_text, re.I)
    if rt_m:
        meta['read_time'] = f"{rt_m.group(1)} min read"

    # 4. Extract Article Content
    art_m = re.search(r'<article[^>]*>(.*?)</article>', html_text, re.DOTALL)
    if not art_m:
        return None

    art_html = art_m.group(1)

    # Extract Title if missing
    if not meta['title']:
        h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', art_html, re.DOTALL)
        if h1_m:
            meta['title'] = clean_html(h1_m.group(1))

    # Parse structural content blocks
    blocks = re.findall(r'<(h2|h3|p|blockquote|figure)[^>]*>(.*?)</\1>', art_html, re.DOTALL)

    body_paragraphs = []
    bio_paragraphs = []
    in_bio = False

    for tag, content in blocks:
        txt = clean_html(content)
        if not txt:
            continue

        # Skip subscription / support pleas
        if any(skip_phrase in txt.lower() for skip_phrase in [
            'on supporting science journalism',
            'if you\'re enjoying this article',
            'subscribe to support independent journalism',
            'great science journalism requires human expertise',
            'when you subscribe, you are supporting',
            'thank you,',
            'jeanna bryner, editor in chief',
            'sign up for scientific american',
            'get the best of science journalism'
        ]):
            continue

        # Skip header metadata paragraphs that repeat title, date, or author
        if txt == meta['title'] or txt == meta['subtitle']:
            continue
        if re.match(r'^[A-Z][a-z]+ \d{1,2}, \d{4}$', txt): # Date line
            continue
        if re.match(r'^\d+ min read$', txt, re.I): # Read time line
            continue
        if txt.startswith('By ') and any(a in txt for a in meta['authors']):
            continue

        # Detect author bios at the end of article
        if any(txt.startswith(f"{a} is") or txt.startswith(f"{a} was") or txt.startswith(f"{a} covers") for a in meta['authors']):
            in_bio = True

        if tag == 'figure':
            # Extract image inside figure
            img_src = re.search(r'src=[\"\']([^\"\']+)[\"\']', content)
            if img_src:
                img_url = img_src.group(1)
                caption = clean_html(re.sub(r'<img[^>]*>', '', content))
                body_paragraphs.append(f"\n![{caption}]({img_url})\n*{caption}*\n")
            continue

        if in_bio:
            bio_paragraphs.append(txt)
        elif tag == 'h2':
            body_paragraphs.append(f"\n## {txt}\n")
        elif tag == 'h3':
            body_paragraphs.append(f"\n### {txt}\n")
        elif tag == 'blockquote':
            body_paragraphs.append(f"\n> {txt}\n")
        else:
            body_paragraphs.append(txt)

    if not body_paragraphs:
        return None

    authors_str = ", ".join(meta['authors']) if meta['authors'] else "Scientific American"
    editors_str = f" | Edited by {', '.join(meta['editors'])}" if meta['editors'] else ""

    # Build Markdown document
    md_lines = [
        "---",
        f"title: {json.dumps(meta['title'], ensure_ascii=False)}",
        f"subtitle: {json.dumps(meta['subtitle'], ensure_ascii=False)}",
        f"author: {json.dumps(authors_str, ensure_ascii=False)}",
        f"date: {json.dumps(meta['date'], ensure_ascii=False)}",
        f"category: {json.dumps(meta['category'], ensure_ascii=False)}",
        f"read_time: {json.dumps(meta['read_time'] or '5 min read', ensure_ascii=False)}",
        f"hero_image: {json.dumps(meta['hero_image'], ensure_ascii=False)}",
        f"source_url: {json.dumps(meta['source_url'], ensure_ascii=False)}",
        f"slug: {json.dumps(meta['slug'], ensure_ascii=False)}",
        "---",
        "",
        f"# {meta['title']}",
        "",
        f"*{meta['subtitle']}*" if meta['subtitle'] else "",
        "",
        f"**By {authors_str}**{editors_str} &bull; **{meta['date']}** &bull; {meta['read_time'] or '5 min read'}",
        "",
        f"![{meta['title']}]({meta['hero_image']})" if meta['hero_image'] else "",
        "",
        "---",
        ""
    ]

    for p in body_paragraphs:
        md_lines.append(p)
        md_lines.append("")

    if bio_paragraphs:
        md_lines.append("---")
        md_lines.append("### About the Author(s)")
        for b in bio_paragraphs:
            md_lines.append(f"*{b}*")
            md_lines.append("")

    content_markdown = "\n".join(md_lines)
    word_count = len(re.findall(r'\b\w+\b', content_markdown))

    record = {
        'id': 0, # assigned later
        'slug': slug,
        'title': meta['title'],
        'subtitle': meta['subtitle'],
        'author': authors_str,
        'date': meta['date'],
        'category': meta['category'],
        'read_time': meta['read_time'] or '5 min read',
        'hero_image': meta['hero_image'],
        'source_url': meta['source_url'],
        'word_count': word_count,
        'filename': f"{slug}.md"
    }

    return record, content_markdown

def scrape_one_article(url):
    slug = url.strip('/').split('/')[-1]
    out_file = ARTICLES_DIR / f"{slug}.md"

    if out_file.exists():
        # Already cached, parse from existing markdown frontmatter
        try:
            txt = out_file.read_text(encoding='utf-8')
            m = re.search(r'^---\s*\n(.*?)\n---', txt, re.DOTALL)
            if m:
                meta = {}
                for line in m.group(1).splitlines():
                    if ':' in line:
                        k, v = line.split(':', 1)
                        try:
                            meta[k.strip()] = json.loads(v.strip())
                        except:
                            meta[k.strip()] = v.strip().strip('"').strip("'")
                return {
                    'slug': slug,
                    'title': meta.get('title', slug),
                    'subtitle': meta.get('subtitle', ''),
                    'author': meta.get('author', 'Scientific American'),
                    'date': meta.get('date', ''),
                    'category': meta.get('category', 'Science'),
                    'read_time': meta.get('read_time', '5 min read'),
                    'hero_image': meta.get('hero_image', ''),
                    'source_url': meta.get('source_url', url),
                    'word_count': len(re.findall(r'\b\w+\b', txt)),
                    'filename': f"{slug}.md"
                }, True
        except Exception:
            pass

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, context=CTX, timeout=12) as resp:
                html_text = resp.read().decode('utf-8', errors='ignore')
                res = parse_article_html(html_text, url)
                if res:
                    record, md_text = res
                    out_file.write_text(md_text, encoding='utf-8')
                    return record, False
                return None, False
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 * (attempt + 1))
            elif e.code == 404:
                return None, False
            else:
                time.sleep(1)
        except Exception:
            time.sleep(1)
    return None, False

def build_catalog(records):
    # Sort newest first
    records.sort(key=lambda x: x.get('date') or '', reverse=True)
    for idx, r in enumerate(records, 1):
        r['id'] = idx

    # Save JSON index
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved {len(records)} records to {INDEX_FILE}")

    # Generate Markdown Catalog
    lines = [
        "# Scientific American — Archive & Editorial Library",
        "",
        f"**Total Articles Archived:** {len(records)} | **Topics:** Science, Space, Physics, Health, Environment, Technology",
        "",
        "---",
        "",
        "| # | Date | Category | Title | Author | Source Link |",
        "|:---:|:---:|:---:|---|---|:---:|"
    ]

    for r in records:
        date = r.get('date') or 'N/A'
        cat = r.get('category') or 'Science'
        title = r.get('title', '').replace('|', '-')
        auth = r.get('author', '').replace('|', '-')
        src = r.get('source_url', '')
        link = f"[Read on SciAm ↗]({src})" if src.startswith('http') else "—"
        slug = r.get('slug')
        lines.append(f"| {r['id']} | {date} | `{cat}` | **[{title}](articles/{slug}.md)** | {auth} | {link} |")

    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logging.info(f"Generated {CATALOG_FILE}")

def main():
    parser = argparse.ArgumentParser(description="Scrape Scientific American articles")
    parser.add_argument('--workers', type=int, default=8, help='Concurrent worker threads')
    parser.add_argument('--limit', type=int, default=150, help='Max articles to scrape (0 for all)')
    parser.add_argument('--page', type=int, default=1, help='Sitemap page number')
    args = parser.parse_args()

    urls = fetch_sitemap_urls(page=args.page)
    if args.limit > 0:
        urls = urls[:args.limit]

    logging.info(f"Targeting {len(urls)} articles with {args.workers} workers...")

    records = []
    completed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(scrape_one_article, u): u for u in urls}
        for fut in as_completed(futures):
            res, was_cached = fut.result()
            completed += 1
            if res:
                records.append(res)
            if completed % 25 == 0 or completed == len(urls):
                elapsed = time.time() - t0
                logging.info(f"Progress: {completed}/{len(urls)} ({completed/len(urls)*100:.1f}%) in {elapsed:.1f}s [Saved: {len(records)}]")

    logging.info(f"Scrape completed in {time.time()-t0:.1f}s. Total valid articles: {len(records)}")
    build_catalog(records)

if __name__ == "__main__":
    main()
