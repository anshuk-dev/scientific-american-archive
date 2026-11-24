/* Scientific American Unpaywalled Editorial Reader - Core Script */

(function () {
  'use strict';

  // State
  let catalog = [];
  let currentArticleSlug = null;
  let activeCategory = 'all';
  let searchQuery = '';
  let sortBy = 'newest';

  // User Preferences
  const STORAGE_THEME = 'sciam_reader_theme';
  const STORAGE_BOOKMARKS = 'sciam_reader_bookmarks';
  const STORAGE_READ = 'sciam_reader_read';
  const STORAGE_FONT_SIZE = 'sciam_reader_fontsize';
  const STORAGE_FONT_FAMILY = 'sciam_reader_fontfamily';

  let bookmarks = new Set(JSON.parse(localStorage.getItem(STORAGE_BOOKMARKS) || '[]'));
  let readArticles = new Set(JSON.parse(localStorage.getItem(STORAGE_READ) || '[]'));

  // Category Taxonomy Mapping
  const CATEGORY_MAP = {
    'space-physics': [
      'Space Exploration', 'Astronomy', 'Astrophysics', 'Quantum Physics',
      'Cosmology', 'Universe', 'Mars', 'Planetary Science', 'Solar system',
      'Spacecraft', 'Space & Physics', 'Extraterrestrial Life'
    ],
    'health-medicine': [
      'Public Health', 'Neuroscience', 'GLP-1 Drugs', 'Medicine',
      'Alzheimer\'s Disease', 'Cancer', 'Sleep', 'Epidemiology', 'Measles',
      'Obesity', 'Exercise', 'Psychology', 'Mind & Brain'
    ],
    'math-tech': [
      'Mathematics', 'Artificial Intelligence', 'Math Puzzles', 'Math',
      'Engineering', 'Technology', 'Quantum Computing', 'Robotics', 'Internet'
    ],
    'environment': [
      'Climate Change', 'El Niño', 'Weather', 'Oceans', 'Ecology',
      'Geology', 'Anthropocene', 'Nuclear energy'
    ],
    'biology': [
      'Animals', 'Evolution', 'Evolutionary Biology', 'Archaeology',
      'Anthropology', 'Food', 'Cats', 'Social Sciences', 'Culture'
    ]
  };

  // DOM Elements
  const gridEl = document.getElementById('articlesGrid');
  const searchInput = document.getElementById('searchInput');
  const sortSelect = document.getElementById('sortSelect');
  const catTabs = document.querySelectorAll('.cat-tab');
  const countStats = document.getElementById('countStats');
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const readerModal = document.getElementById('readerModal');
  const readerContent = document.getElementById('readerArticleBody');
  const readerProgressBar = document.getElementById('readerProgressBar');
  const backBtn = document.getElementById('readerBackBtn');
  const readerBookmarkBtn = document.getElementById('readerBookmarkBtn');
  const readerShareBtn = document.getElementById('readerShareBtn');
  const readerOrigLink = document.getElementById('readerOrigLink');
  const readerFontToggle = document.getElementById('readerFontToggle');
  const readerSizeDec = document.getElementById('readerSizeDec');
  const readerSizeInc = document.getElementById('readerSizeInc');

  // Initialize
  async function init() {
    initTheme();
    initTypography();
    attachEventListeners();
    await loadCatalog();
    handleHashChange();
  }

  // Load Catalog Index
  async function loadCatalog() {
    try {
      countStats.textContent = 'Loading library...';
      const res = await fetch('reader-data/catalog.json');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      catalog = await res.json();
      renderCatalog();
    } catch (err) {
      console.error('Failed to load catalog:', err);
      // Fallback try root articles_index.json
      try {
        const res2 = await fetch('articles_index.json');
        catalog = await res2.json();
        renderCatalog();
      } catch (err2) {
        gridEl.innerHTML = `
          <div class="empty-state" style="grid-column: 1/-1;">
            <h3>Unable to load catalog</h3>
            <p>Please ensure you are viewing this via a web server or GitHub Pages.</p>
          </div>
        `;
      }
    }
  }

  // Filter & Sort Logic
  function getFilteredArticles() {
    let list = catalog.slice();

    // 1. Category Filter
    if (activeCategory === 'bookmarks') {
      list = list.filter(a => bookmarks.has(a.slug));
    } else if (activeCategory !== 'all') {
      const allowedCategories = CATEGORY_MAP[activeCategory] || [activeCategory];
      list = list.filter(a => allowedCategories.includes(a.category));
    }

    // 2. Search Query Filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      list = list.filter(a => {
        return (
          (a.title && a.title.toLowerCase().includes(q)) ||
          (a.subtitle && a.subtitle.toLowerCase().includes(q)) ||
          (a.author && a.author.toLowerCase().includes(q)) ||
          (a.category && a.category.toLowerCase().includes(q)) ||
          (a.slug && a.slug.toLowerCase().includes(q))
        );
      });
    }

    // 3. Sorting
    if (sortBy === 'newest') {
      list.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    } else if (sortBy === 'oldest') {
      list.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
    } else if (sortBy === 'reading-time') {
      list.sort((a, b) => {
        const ra = parseInt(a.read_time) || 5;
        const rb = parseInt(b.read_time) || 5;
        return rb - ra;
      });
    } else if (sortBy === 'word-count') {
      list.sort((a, b) => (b.word_count || 0) - (a.word_count || 0));
    }

    return list;
  }

  // Render Catalog Cards
  function renderCatalog() {
    const articles = getFilteredArticles();
    countStats.textContent = `Showing ${articles.length} of ${catalog.length} articles`;

    if (articles.length === 0) {
      gridEl.innerHTML = `
        <div class="empty-state" style="grid-column: 1/-1;">
          <h3>No articles found</h3>
          <p>Try adjusting your search terms or selecting a different topic tab.</p>
        </div>
      `;
      return;
    }

    const html = articles.map(art => {
      const isSaved = bookmarks.has(art.slug);
      const isRead = readArticles.has(art.slug);
      const hero = art.hero_image || 'https://static.scientificamerican.com/dam/asset/cee10388-a264-4ba7-b944-7f0a8daf537d/riemann.jpg';
      
      return `
        <article class="article-card" data-slug="${art.slug}" role="button" tabindex="0">
          <div class="card-image-wrap">
            <img src="${hero}" alt="${escapeHtml(art.title)}" class="card-img" loading="lazy" onerror="this.src='data:image/svg+xml;utf8,<svg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'400\\' height=\\'200\\' viewBox=\\'0 0 400 200\\'><rect width=\\'400\\' height=\\'200\\' fill=\\'%23161920\\'/><text x=\\'50%\\' y=\\'50%\\' fill=\\'%23b91c1c\\' font-family=\\'serif\\' font-size=\\'24\\' text-anchor=\\'middle\\' dy=\\'.3em\\'>SCIENTIFIC AMERICAN</text></svg>'">
            <span class="card-badge">${escapeHtml(art.category || 'Science')}</span>
          </div>
          <div class="card-body">
            <div class="card-category">${escapeHtml(art.category || 'Science')}</div>
            <h2 class="card-title">${escapeHtml(art.title)}</h2>
            ${art.subtitle ? `<p class="card-dek">${escapeHtml(art.subtitle)}</p>` : ''}
            <div class="card-footer">
              <span class="card-author">${escapeHtml(art.author || 'Scientific American')}</span>
              <div class="card-meta-right">
                <span>${art.date || ''}</span>
                <span>&bull;</span>
                <span>${art.read_time || '5 min'}</span>
                ${isRead ? '<span title="Read">✓</span>' : ''}
              </div>
            </div>
          </div>
        </article>
      `;
    }).join('');

    gridEl.innerHTML = html;

    // Attach card click handlers
    gridEl.querySelectorAll('.article-card').forEach(card => {
      card.addEventListener('click', () => {
        const slug = card.getAttribute('data-slug');
        openArticle(slug);
      });
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const slug = card.getAttribute('data-slug');
          openArticle(slug);
        }
      });
    });
  }

  // Open Article Reader
  async function openArticle(slug) {
    currentArticleSlug = slug;
    window.location.hash = `article/${slug}`;

    readerModal.classList.add('open');
    readerModal.scrollTop = 0;
    document.body.style.overflow = 'hidden';

    // Show loading skeleton
    readerContent.innerHTML = `
      <div style="padding: 60px 0; text-align: center; color: var(--text-muted);">
        <p style="font-size: 1.2rem;">Loading unpaywalled editorial article...</p>
      </div>
    `;

    updateReaderActionButtons(slug);

    try {
      const res = await fetch(`reader-data/${slug}.json`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const article = await res.json();
      renderArticleDetail(article);
      markAsRead(slug);
    } catch (err) {
      console.error('Failed to load article details:', err);
      readerContent.innerHTML = `
        <div style="padding: 40px; text-align: center;">
          <h2 style="color: var(--sciam-red); margin-bottom: 12px;">Error Loading Article</h2>
          <p>Could not retrieve reader bundle for this article.</p>
          <p style="margin-top: 16px;"><button class="reader-back-btn" onclick="window.history.back()">Back to Archive</button></p>
        </div>
      `;
    }
  }

  // Render Full Article Details
  function renderArticleDetail(art) {
    const heroHtml = art.hero_image ? `
      <figure class="reader-hero-figure">
        <img src="${art.hero_image}" alt="${escapeHtml(art.title)}" class="reader-hero-img" onerror="this.style.display='none'">
      </figure>
    ` : '';

    readerOrigLink.href = art.source_url || `https://www.scientificamerican.com/article/${art.slug}/`;

    readerContent.innerHTML = `
      <div class="reader-category">${escapeHtml(art.category || 'Science')}</div>
      <h1 class="reader-title">${escapeHtml(art.title)}</h1>
      ${art.subtitle ? `<p class="reader-dek">${escapeHtml(art.subtitle)}</p>` : ''}
      <div class="reader-byline">
        <span>By <strong>${escapeHtml(art.author || 'Scientific American')}</strong></span>
        <span>&bull;</span>
        <span>${art.date || ''}</span>
        <span>&bull;</span>
        <span>${art.read_time || '5 min read'} (${art.word_count || ''} words)</span>
      </div>
      ${heroHtml}
      <div class="article-content">
        ${art.html}
      </div>
    `;
  }

  // Close Article Reader
  function closeArticle() {
    readerModal.classList.remove('open');
    document.body.style.overflow = '';
    currentArticleSlug = null;
    readerProgressBar.style.width = '0%';
    if (window.location.hash.startsWith('#article/')) {
      window.location.hash = '';
    }
    renderCatalog(); // Update read checkmarks
  }

  // Handle URL Hash Changes (Permalinks & Back/Forward)
  function handleHashChange() {
    const hash = window.location.hash;
    if (hash.startsWith('#article/')) {
      const slug = hash.replace('#article/', '').trim();
      if (slug && slug !== currentArticleSlug) {
        openArticle(slug);
      }
    } else if (readerModal.classList.contains('open')) {
      closeArticle();
    }
  }

  // Mark Read
  function markAsRead(slug) {
    if (!readArticles.has(slug)) {
      readArticles.add(slug);
      localStorage.setItem(STORAGE_READ, JSON.stringify([...readArticles]));
    }
  }

  // Toggle Bookmark
  function toggleBookmark(slug) {
    if (bookmarks.has(slug)) {
      bookmarks.delete(slug);
    } else {
      bookmarks.add(slug);
    }
    localStorage.setItem(STORAGE_BOOKMARKS, JSON.stringify([...bookmarks]));
    updateReaderActionButtons(slug);
    if (activeCategory === 'bookmarks') {
      renderCatalog();
    }
  }

  function updateReaderActionButtons(slug) {
    if (!readerBookmarkBtn) return;
    const isSaved = bookmarks.has(slug);
    readerBookmarkBtn.innerHTML = isSaved
      ? '★ Saved'
      : '☆ Save';
  }

  // Reading Progress Bar
  readerModal.addEventListener('scroll', () => {
    const total = readerModal.scrollHeight - readerModal.clientHeight;
    if (total > 0) {
      const progress = (readerModal.scrollTop / total) * 100;
      readerProgressBar.style.width = `${Math.min(100, Math.max(0, progress))}%`;
    }
  });

  // Attach Event Listeners
  function attachEventListeners() {
    // Search
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value;
      renderCatalog();
    });

    // Sort
    sortSelect.addEventListener('change', (e) => {
      sortBy = e.target.value;
      renderCatalog();
    });

    // Categories
    catTabs.forEach(tab => {
      tab.addEventListener('click', () => {
        catTabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeCategory = tab.getAttribute('data-cat');
        renderCatalog();
      });
    });

    // Theme Toggle
    themeToggleBtn.addEventListener('click', () => {
      cycleTheme();
    });

    // Back button in reader
    backBtn.addEventListener('click', () => {
      closeArticle();
    });

    // Reader action buttons
    readerBookmarkBtn.addEventListener('click', () => {
      if (currentArticleSlug) {
        toggleBookmark(currentArticleSlug);
      }
    });

    readerShareBtn.addEventListener('click', () => {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(window.location.href).then(() => {
          const original = readerShareBtn.innerHTML;
          readerShareBtn.innerHTML = '✓ Copied';
          setTimeout(() => { readerShareBtn.innerHTML = original; }, 2000);
        });
      }
    });

    // Font family toggle
    readerFontToggle.addEventListener('click', () => {
      const current = document.documentElement.style.getPropertyValue('--reader-font');
      const isSans = current.includes('sans');
      const next = isSans ? 'var(--font-serif)' : 'var(--font-sans)';
      document.documentElement.style.setProperty('--reader-font', next);
      localStorage.setItem(STORAGE_FONT_FAMILY, isSans ? 'serif' : 'sans');
      readerFontToggle.textContent = isSans ? 'Font: Serif' : 'Font: Sans';
    });

    // Font size controls
    readerSizeDec.addEventListener('click', () => adjustFontSize(-0.1));
    readerSizeInc.addEventListener('click', () => adjustFontSize(0.1));

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && readerModal.classList.contains('open')) {
        closeArticle();
      } else if (e.key === '/' && !readerModal.classList.contains('open') && document.activeElement !== searchInput) {
        e.preventDefault();
        searchInput.focus();
      }
    });

    // Window Hash Listener
    window.addEventListener('hashchange', handleHashChange);
  }

  // Theme Handling
  function initTheme() {
    const saved = localStorage.getItem(STORAGE_THEME) || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeBtnText(saved);
  }

  function cycleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'light';
    let next = 'dark';
    if (current === 'light') next = 'sepia';
    else if (current === 'sepia') next = 'dark';
    else if (current === 'dark') next = 'light';

    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem(STORAGE_THEME, next);
    updateThemeBtnText(next);
  }

  function updateThemeBtnText(theme) {
    if (theme === 'dark') themeToggleBtn.innerHTML = '🌙 Dark';
    else if (theme === 'sepia') themeToggleBtn.innerHTML = '📜 Sepia';
    else themeToggleBtn.innerHTML = '☀️ Light';
  }

  // Typography Settings
  function initTypography() {
    const savedFont = localStorage.getItem(STORAGE_FONT_FAMILY);
    if (savedFont === 'sans') {
      document.documentElement.style.setProperty('--reader-font', 'var(--font-sans)');
      readerFontToggle.textContent = 'Font: Sans';
    }

    const savedSize = localStorage.getItem(STORAGE_FONT_SIZE);
    if (savedSize) {
      document.documentElement.style.setProperty('--reader-size', `${savedSize}rem`);
    }
  }

  let currentSizeVal = 1.15;
  function adjustFontSize(delta) {
    currentSizeVal = Math.min(1.6, Math.max(0.9, currentSizeVal + delta));
    document.documentElement.style.setProperty('--reader-size', `${currentSizeVal.toFixed(2)}rem`);
    localStorage.setItem(STORAGE_FONT_SIZE, currentSizeVal.toFixed(2));
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
