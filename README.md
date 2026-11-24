# Scientific American — Unpaywalled Editorial Archive & Reader

> High-fidelity, unpaywalled archival reader and continuous synchronization engine for [Scientific American](https://www.scientificamerican.com).

[![Live Reading Room](https://img.shields.io/badge/Live%20Reader-GitHub%20Pages-b91c1c?style=for-the-badge&logo=safari)](https://anshuk-dev.github.io/scientific-american-archive/)
[![Update Status](https://img.shields.io/badge/Sync-Every%203%20Hours-blue?style=for-the-badge&logo=githubactions)](https://github.com/anshuk-dev/scientific-american-archive/actions)
[![Articles Archived](https://img.shields.io/badge/Articles-140%2B-green?style=for-the-badge)](#)

---

## 📖 Live Reading Room

Access the distraction-free, responsive editorial reading experience:
👉 **[https://anshuk-dev.github.io/scientific-american-archive/](https://anshuk-dev.github.io/scientific-american-archive/)**

### Key Features
- **Unpaywalled Full-Text Articles:** Server-rendered editorial body, high-resolution figures, captions, author biographies, and deks.
- **Classic Editorial Typography:** Merriweather serif body with Playfair Display headings, optimized line-height, and justified columns.
- **Reading Controls:** Custom font switcher (Serif vs. Sans), 4 font size steps, reading progress indicator bar, and Light / Sepia / Dark themes.
- **Live Search & Taxonomy:** Instant client-side search across headlines, topics, and authors, plus curated category tabs (*Space & Physics*, *Health & Medicine*, *Math & Technology*, *Environment & Climate*, *Evolution & Biology*).
- **Offline Ready & Permanent Permalinks:** Each article has an instant direct URL hash (e.g. `#article/<slug>`) and local bookmarking system.
- **Continuous Automation:** GitHub Actions workflow synchronizes newly published articles automatically every 3 hours.

---

## 🗂️ Archive Structure

```
scientificamerican/
├── articles/                     # Raw Markdown articles with JSON frontmatter & full text
│   ├── ai-just-solved-the-real-navier-stokes-problem.md
│   ├── anthropic-mathematician-claims-to-prove-riemann-hypothesis-...md
│   └── ... (140+ full markdown articles)
├── dist/                         # Production static web app deployed to GitHub Pages
│   ├── index.html                # Editorial reading room UI
│   ├── css/reader.css            # Responsive themes & typography styles
│   ├── js/reader.js              # State manager, search, and reader router
│   ├── reader-data/              # Precompiled article bundles & catalog
│   │   ├── catalog.json          # Light index for fast client-side searching
│   │   └── <slug>.json           # Rendered article bodies
│   └── CATALOG.md                # Markdown directory of all archived articles
├── scripts/
│   └── build_reader.py           # Markdown-to-HTML & JSON reader bundle compiler
├── .github/workflows/
│   └── update-articles.yml       # Scheduled GitHub Action (runs every 3 hours)
├── scraper.py                    # Multi-threaded sitemap crawler & extractor
├── articles_index.json           # Machine-readable archive catalog
├── CATALOG.md                    # Editorial table with links and metadata
├── start_reader.command          # 1-Click macOS offline launcher
└── README.md
```

---

## 🚀 Local Usage

### 1-Click macOS Launcher
Double-click `start_reader.command` in Finder to launch a local server and open the reader in your default browser.

### Command Line
```bash
# Clone the repository
git clone https://github.com/anshuk-dev/scientific-american-archive.git
cd scientific-american-archive

# Start local reader
python3 -m http.server 8765 --directory dist
# Open http://localhost:8765
```

### Scraping Additional Articles
```bash
# Fetch latest articles with multi-threading
python3 scraper.py --limit 100 --workers 8

# Rebuild reader web app
python3 scripts/build_reader.py
```

---

## ⚙️ Automated Continuous Sync

The GitHub Action defined in `.github/workflows/update-articles.yml` runs automatically every 3 hours:
1. Fetches latest article URLs from the official Scientific American sitemaps.
2. Extracts new unpaywalled articles and creates clean Markdown files.
3. Recompiles `dist/reader-data/` with the new catalog and article bundles.
4. Commits and pushes any new articles back to the `main` branch.
5. Deploys the updated `dist/` directory directly to GitHub Pages.

---

## 📜 Disclaimer
This archive is maintained for personal research, educational preservation, and non-commercial reference under fair use. All intellectual property and journalistic copyright belong to Scientific American and Springer Nature.
