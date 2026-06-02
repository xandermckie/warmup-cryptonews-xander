/**
 * Client-side UI for Crypt0x News.
 * Handles sorting, theme toggle, coin detail modal, search, and rendering.
 */

(function () {
  const initialData = JSON.parse(
    document.getElementById('initial-data').textContent
  );

  // --- Application state ---------------------------------------------------
  // `displayCoins` is the list currently shown (after search); sort applies on top.
  let displayCoins = [...initialData.coins];
  let displayNews = [...initialData.news];
  let currentSort = 'rank';
  let searchActive = false;
  const THEME_STORAGE_KEY = 'cryptox-theme';
  const CLIENT_ID_KEY = 'cryptox-client-id';
  // Ordered coin ids starred by this browser; synced with data/favorites.json.
  let favoriteIds = [];

  // --- Formatting helpers --------------------------------------------------
  function formatLastUpdated(iso) {
    if (!iso) return 'Never';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/Chicago',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      }).formatToParts(d).map((p) => [p.type, p.value])
    );
    return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}${parts.dayPeriod} CST`;
  }

  function formatPrice(price) {
    if (price == null) return '—';
    return '$' + Number(price).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: price >= 1 ? 2 : 6
    });
  }

  function formatChange(pct) {
    if (pct == null) return '—';
    const sign = pct >= 0 ? '+' : '';
    return sign + Number(pct).toFixed(2) + '%';
  }

  function changeClass(pct) {
    if (pct == null) return '';
    return pct >= 0 ? 'positive change-positive' : 'negative change-negative';
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

  // --- Sorting -------------------------------------------------------------
  /**
   * Sort coins in-place according to the dropdown selection.
   * Genesis dates come from CoinGecko; coins without a date sort last.
   */
  function sortCoins(coins, sortKey) {
    const sorted = [...coins];

    const byNumber = (getter, descending) => {
      sorted.sort((a, b) => {
        const av = getter(a);
        const bv = getter(b);
        const aMissing = av == null;
        const bMissing = bv == null;
        if (aMissing && bMissing) return 0;
        if (aMissing) return 1;
        if (bMissing) return -1;
        return descending ? bv - av : av - bv;
      });
    };

    const byDate = (descending) => {
      sorted.sort((a, b) => {
        const av = a.genesis_date ? Date.parse(a.genesis_date) : null;
        const bv = b.genesis_date ? Date.parse(b.genesis_date) : null;
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        return descending ? bv - av : av - bv;
      });
    };

    switch (sortKey) {
      case 'price_desc':
        byNumber((c) => c.current_price, true);
        break;
      case 'price_asc':
        byNumber((c) => c.current_price, false);
        break;
      case 'perf_desc':
        byNumber((c) => c.price_change_percentage_24h, true);
        break;
      case 'perf_asc':
        byNumber((c) => c.price_change_percentage_24h, false);
        break;
      case 'date_asc':
        byDate(false);
        break;
      case 'date_desc':
        byDate(true);
        break;
      default:
        byNumber((c) => c.market_cap_rank, false);
    }

    return sorted;
  }

  /**
   * Pin starred coins to the top in the order the user starred them.
   * Non-favorites keep their sort order from sortCoins().
   */
  function pinFavorites(coins) {
    if (!favoriteIds.length) return coins;

    const visibleById = new Map(coins.map((coin) => [coin.id, coin]));
    const pinned = favoriteIds
      .map((id) => visibleById.get(id))
      .filter(Boolean);
    const favoriteSet = new Set(favoriteIds);
    const rest = coins.filter((coin) => !favoriteSet.has(coin.id));
    return [...pinned, ...rest];
  }

  function isFavorite(coinId) {
    return favoriteIds.includes(coinId);
  }

  function getClientId() {
    let clientId = localStorage.getItem(CLIENT_ID_KEY);
    if (!clientId) {
      clientId = crypto.randomUUID();
      localStorage.setItem(CLIENT_ID_KEY, clientId);
    }
    return clientId;
  }

  function favoritesHeaders() {
    return { 'X-Client-Id': getClientId() };
  }

  async function loadFavorites() {
    try {
      const res = await fetch('/favorites', { headers: favoritesHeaders() });
      const data = await res.json();
      if (!res.ok) {
        console.error(data.error || 'Failed to load favorites');
        return;
      }
      favoriteIds = data.favorites || [];
    } catch (err) {
      console.error('Favorites request failed', err);
    }
  }

  async function toggleFavorite(coinId) {
    try {
      const res = await fetch(`/favorites/${encodeURIComponent(coinId)}`, {
        method: 'POST',
        headers: favoritesHeaders(),
      });
      const data = await res.json();
      if (!res.ok) {
        console.error(data.error || 'Failed to update favorite');
        return;
      }
      favoriteIds = data.favorites || [];
      renderCoins(getSortedDisplayCoins());
    } catch (err) {
      console.error('Favorite toggle failed', err);
    }
  }

  // --- Rendering ------------------------------------------------------------
  function buildTickerItem(coin) {
    const pct = coin.price_change_percentage_24h;
    const cls = changeClass(pct);
    return `
      <div class="ticker-item">
        <img src="${escapeHtml(coin.image)}" alt="" width="24" height="24" loading="lazy">
        <span class="ticker-symbol">${escapeHtml(coin.symbol)}</span>
        <span class="ticker-price">${formatPrice(coin.current_price)}</span>
        <span class="ticker-change ${cls}">${formatChange(pct)}</span>
      </div>`;
  }

  function renderTicker(coins) {
    const track = document.getElementById('ticker-track');
    if (!coins.length) {
      track.innerHTML = '<div class="ticker-item"><span class="text-muted">Loading prices…</span></div>';
      return;
    }
    const items = coins.map(buildTickerItem).join('');
    track.innerHTML = items + items;
  }

  function renderCoins(coins) {
    const grid = document.getElementById('coin-grid');
    const empty = document.getElementById('coins-empty');
    if (!coins.length) {
      grid.innerHTML = '';
      empty.classList.remove('d-none');
      return;
    }
    empty.classList.add('d-none');
    grid.innerHTML = coins.map((coin) => {
      const pct = coin.price_change_percentage_24h;
      const cls = changeClass(pct);
      const starred = isFavorite(coin.id);
      return `
        <div class="col-sm-6 col-md-4">
          <div class="coin-card-wrap${starred ? ' is-favorite' : ''}">
            <button
              type="button"
              class="favorite-btn${starred ? ' is-favorite' : ''}"
              data-favorite-id="${escapeHtml(coin.id)}"
              aria-label="${starred ? 'Unstar' : 'Star'} ${escapeHtml(coin.name)}"
              aria-pressed="${starred}"
            >★</button>
            <button type="button" class="coin-card-btn" data-coin-id="${escapeHtml(coin.id)}" aria-label="View details for ${escapeHtml(coin.name)}">
              <div class="card coin-card h-100">
                <div class="card-body d-flex align-items-center gap-3">
                  <img src="${escapeHtml(coin.image)}" alt="${escapeHtml(coin.name)}">
                  <div class="text-start">
                    <div class="fw-semibold">${escapeHtml(coin.name)}</div>
                    <div class="text-muted small text-uppercase">#${coin.market_cap_rank ?? '—'} · ${escapeHtml(coin.symbol)}</div>
                    <div class="coin-price mt-1">${formatPrice(coin.current_price)}</div>
                    <div class="small ${cls}">${formatChange(pct)} (24h)</div>
                  </div>
                </div>
              </div>
            </button>
          </div>
        </div>`;
    }).join('');
  }

  function renderNews(news) {
    const list = document.getElementById('news-list');
    const empty = document.getElementById('news-empty');
    if (!news.length) {
      list.innerHTML = '';
      empty.classList.remove('d-none');
      return;
    }
    empty.classList.add('d-none');
    list.innerHTML = news.map((article) => {
      const date = article.published_at
        ? new Date(article.published_at).toLocaleString()
        : '';
      const title = escapeHtml(article.title);
      const url = escapeHtml(article.url);
      return `
        <li class="list-group-item">
          <a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>
          <div class="news-meta mt-1">${escapeHtml(article.source)}${date ? ' · ' + date : ''}</div>
          ${article.description ? '<p class="small text-muted mb-0 mt-1">' + escapeHtml(article.description) + '</p>' : ''}
        </li>`;
    }).join('');
  }

  function renderPickOfDay(pick) {
    const panel = document.getElementById('pick-panel');
    if (!pick) {
      panel.classList.add('d-none');
      return;
    }
    panel.classList.remove('d-none');
    const pct = pick.price_change_percentage_24h;
    panel.innerHTML = `
      <div class="pick-badge">Pick of the day</div>
      <div class="d-flex align-items-center gap-3 mt-2">
        <img src="${escapeHtml(pick.image)}" alt="" class="pick-image" width="48" height="48">
        <div>
          <div class="fw-bold">${escapeHtml(pick.name)} <span class="text-uppercase text-muted small">${escapeHtml(pick.symbol)}</span></div>
          <div class="coin-price">${formatPrice(pick.current_price)}</div>
          <div class="small ${changeClass(pct)}">${formatChange(pct)} (24h)</div>
        </div>
      </div>
      <p class="pick-reason small mt-3 mb-2">${escapeHtml(pick.reason)}</p>
      <p class="pick-disclaimer mb-0">Not financial advice — for fun and learning only.</p>`;
  }

  function updateMeta(lastUpdated, stale) {
    const el = document.getElementById('last-updated');
    el.textContent = 'Last updated: ' + formatLastUpdated(lastUpdated);
    const badge = document.getElementById('stale-badge');
    if (stale) badge.classList.remove('d-none');
    else badge.classList.add('d-none');
  }

  function getSortedDisplayCoins() {
    return pinFavorites(sortCoins(displayCoins, currentSort));
  }

  function renderAll(coins, news, lastUpdated, stale) {
    displayCoins = coins;
    displayNews = news;
    const sorted = getSortedDisplayCoins();
    renderTicker(initialData.coins);
    renderCoins(sorted);
    renderNews(news);
    if (lastUpdated !== undefined) updateMeta(lastUpdated, stale);
  }

  // --- Theme toggle ---------------------------------------------------------
  /**
   * Switch between dark (moon) and light (sun) themes without a page reload.
   * Preference is persisted in localStorage.
   */
  function applyTheme(theme) {
    const root = document.documentElement;
    const isLight = theme === 'light';
    root.setAttribute('data-theme', theme);
    root.setAttribute('data-bs-theme', isLight ? 'light' : 'dark');
    document.body.classList.toggle('theme-light', isLight);
    document.body.classList.toggle('theme-dark', !isLight);

    const btn = document.getElementById('theme-toggle');
    btn.setAttribute('aria-label', isLight ? 'Switch to dark mode' : 'Switch to light mode');
    btn.innerHTML = isLight
      ? '<span class="theme-icon" aria-hidden="true">☀️</span>'
      : '<span class="theme-icon" aria-hidden="true">🌙</span>';

    localStorage.setItem(THEME_STORAGE_KEY, theme);

    // Re-style Chart.js if a modal chart is open.
    if (window.coinChartInstance) {
      window.coinChartInstance.options.scales.x.ticks.color = getComputedStyle(document.body).getPropertyValue('--text-muted').trim();
      window.coinChartInstance.options.scales.y.ticks.color = getComputedStyle(document.body).getPropertyValue('--text-muted').trim();
      window.coinChartInstance.options.plugins.legend.labels.color = getComputedStyle(document.body).getPropertyValue('--text').trim();
      window.coinChartInstance.update();
    }
  }

  function initTheme() {
    const saved = localStorage.getItem(THEME_STORAGE_KEY) || 'dark';
    applyTheme(saved);
    document.getElementById('theme-toggle').addEventListener('click', () => {
      const next = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      applyTheme(next);
    });
  }

  // --- Coin detail modal ----------------------------------------------------
  let modalChart = null;
  let activeCoinId = null;
  let activeChartDays = 7;
  // In-memory caches so chart range switches do not re-fetch coin descriptions.
  const coinDetailCache = new Map();
  const chartCache = new Map();

  function fallbackMessage(detail) {
    if (!detail.fallback) return '';
    if (detail.fallback_reason === 'rate_limit') {
      return '<p class="small text-warning">Rate limited — try again in a minute. Showing Wikipedia fallback.</p>';
    }
    return '<p class="small text-warning">CoinGecko is temporarily unavailable — showing Wikipedia fallback.</p>';
  }

  function openModal() {
    const overlay = document.getElementById('coin-modal');
    overlay.classList.add('is-open');
    overlay.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
  }

  function closeModal() {
    const overlay = document.getElementById('coin-modal');
    overlay.classList.remove('is-open');
    overlay.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    activeCoinId = null;
    activeChartDays = 7;
    if (modalChart) {
      modalChart.destroy();
      modalChart = null;
      window.coinChartInstance = null;
    }
  }

  function renderChart(chartData) {
    const canvas = document.getElementById('coin-chart');
    const emptyEl = document.getElementById('chart-empty');
    if (!canvas || !emptyEl) return;

    const prices = chartData.prices || [];
    if (!prices.length) {
      emptyEl.classList.remove('d-none');
      emptyEl.textContent = chartData.rate_limited
        ? 'Rate limited — try again in a minute.'
        : 'Chart unavailable for this range.';
      if (modalChart) {
        modalChart.destroy();
        modalChart = null;
        window.coinChartInstance = null;
      }
      return;
    }
    emptyEl.classList.add('d-none');

    const labels = prices.map((p) => new Date(p.timestamp).toLocaleDateString());
    const values = prices.map((p) => p.price);
    const accent = getComputedStyle(document.body).getPropertyValue('--accent').trim() || '#3b82f6';
    const muted = getComputedStyle(document.body).getPropertyValue('--text-muted').trim() || '#94a3b8';
    const text = getComputedStyle(document.body).getPropertyValue('--text').trim() || '#e8eef7';

    if (modalChart) {
      modalChart.destroy();
    }

    modalChart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'USD price',
          data: values,
          borderColor: accent,
          backgroundColor: accent + '33',
          fill: true,
          tension: 0.25,
          pointRadius: 0,
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: text } }
        },
        scales: {
          x: {
            ticks: { color: muted, maxTicksLimit: 6 },
            grid: { color: muted + '33' }
          },
          y: {
            ticks: {
              color: muted,
              callback: (v) => '$' + Number(v).toLocaleString()
            },
            grid: { color: muted + '33' }
          }
        }
      }
    });
    window.coinChartInstance = modalChart;
  }

  async function fetchDetailCached(coinId) {
    if (coinDetailCache.has(coinId)) {
      return coinDetailCache.get(coinId);
    }
    const res = await fetch(`/coin/${encodeURIComponent(coinId)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to load coin details');
    coinDetailCache.set(coinId, data);
    return data;
  }

  async function fetchChartCached(coinId, days) {
    const key = `${coinId}-${days}`;
    if (chartCache.has(key)) {
      return chartCache.get(key);
    }
    const res = await fetch(`/coin/${encodeURIComponent(coinId)}/chart?days=${days}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Failed to load chart');
    chartCache.set(key, data);
    return data;
  }

  function buildModalHtml(coinId, detail, days) {
    const genesis = detail.genesis_date
      ? new Date(detail.genesis_date).toLocaleDateString(undefined, { dateStyle: 'long' })
      : 'Unknown';

    let descriptionBlock = '';
    if (detail.description) {
      const excerpt = detail.description.length > 600
        ? detail.description.slice(0, 600) + '…'
        : detail.description;
      descriptionBlock = `
        <p class="modal-description">${escapeHtml(excerpt)}</p>
        <p class="citation small">Source: <a href="https://www.coingecko.com/en/coins/${escapeHtml(coinId)}" target="_blank" rel="noopener">CoinGecko</a></p>`;
    }

    let wikiBlock = '';
    if (detail.wikipedia && detail.wikipedia.extract) {
      wikiBlock = `
        <p class="modal-description">${escapeHtml(detail.wikipedia.extract)}</p>
        <p class="citation small">Source: <a href="${escapeHtml(detail.wikipedia.url)}" target="_blank" rel="noopener">Wikipedia — ${escapeHtml(detail.wikipedia.title)}</a></p>`;
    }

    return `
      <div class="modal-header-inner d-flex align-items-center gap-3 mb-3">
        <img src="${escapeHtml(detail.image)}" alt="" width="56" height="56" class="rounded-circle">
        <div>
          <h3 class="h5 mb-0">${escapeHtml(detail.name)} <span class="text-muted text-uppercase small">${escapeHtml(detail.symbol)}</span></h3>
          <p class="small text-muted mb-0">Released: ${escapeHtml(genesis)}</p>
        </div>
      </div>
      ${fallbackMessage(detail)}
      ${descriptionBlock || wikiBlock || '<p class="text-muted">No description available.</p>'}
      ${descriptionBlock && wikiBlock ? '<hr class="modal-divider"><h4 class="h6">From Wikipedia</h4>' + wikiBlock : ''}
      <div class="chart-section mt-4">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h4 class="h6 mb-0">Price performance</h4>
          <div class="btn-group btn-group-sm chart-range-btns" role="group" aria-label="Chart time range">
            ${[7, 30, 90, 365].map((d) => `
              <button type="button" class="btn btn-outline-primary chart-range-btn${d === days ? ' active' : ''}" data-days="${d}">${d === 365 ? '1Y' : d + 'D'}</button>
            `).join('')}
          </div>
        </div>
        <div class="chart-wrap">
          <canvas id="coin-chart"></canvas>
        </div>
        <p class="citation small mb-0 mt-2">Chart data: CoinGecko market_chart API</p>
        <p class="d-none text-muted small" id="chart-empty">Chart unavailable for this range.</p>
      </div>`;
  }

  function bindChartRangeButtons(coinId) {
    document.querySelectorAll('.chart-range-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const days = Number(btn.dataset.days);
        if (days !== activeChartDays) {
          switchChartRange(coinId, days);
        }
      });
    });
  }

  async function switchChartRange(coinId, days) {
    activeChartDays = days;
    document.querySelectorAll('.chart-range-btn').forEach((btn) => {
      btn.classList.toggle('active', Number(btn.dataset.days) === days);
    });

    const emptyEl = document.getElementById('chart-empty');
    if (emptyEl) {
      emptyEl.classList.add('d-none');
    }

    try {
      const chart = await fetchChartCached(coinId, days);
      renderChart(chart);
    } catch (err) {
      if (emptyEl) {
        emptyEl.textContent = err.message;
        emptyEl.classList.remove('d-none');
      }
    }
  }

  async function loadCoinDetail(coinId, days) {
    activeCoinId = coinId;
    activeChartDays = days;
    const body = document.getElementById('modal-body');
    body.innerHTML = '<p class="text-muted">Loading coin details…</p>';
    openModal();

    try {
      const [detail, chart] = await Promise.all([
        fetchDetailCached(coinId),
        fetchChartCached(coinId, days),
      ]);

      body.innerHTML = buildModalHtml(coinId, detail, days);
      bindChartRangeButtons(coinId);
      renderChart(chart);
    } catch (err) {
      body.innerHTML = `<p class="text-danger">Could not load details. ${escapeHtml(err.message)}</p>`;
    }
  }

  function initModal() {
    document.getElementById('coin-grid').addEventListener('click', (event) => {
      const favoriteBtn = event.target.closest('[data-favorite-id]');
      if (favoriteBtn) {
        event.stopPropagation();
        toggleFavorite(favoriteBtn.dataset.favoriteId);
        return;
      }
      const btn = event.target.closest('[data-coin-id]');
      if (!btn) return;
      loadCoinDetail(btn.dataset.coinId, 7);
    });

    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('coin-modal').addEventListener('click', (event) => {
      if (event.target.id === 'coin-modal') closeModal();
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeModal();
    });
  }

  // --- Search ---------------------------------------------------------------
  let debounceTimer;
  const searchInput = document.getElementById('search-input');

  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const q = searchInput.value.trim();
    debounceTimer = setTimeout(async () => {
      if (!q) {
        searchActive = false;
        renderAll(initialData.coins, initialData.news);
        return;
      }
      searchActive = true;
      try {
        const res = await fetch('/search?q=' + encodeURIComponent(q));
        const data = await res.json();
        if (!res.ok) {
          console.error(data.error || 'Search failed');
          return;
        }
        displayCoins = data.coins;
        displayNews = data.news;
        renderTicker(initialData.coins);
        renderCoins(getSortedDisplayCoins());
        renderNews(data.news);
        updateMeta(data.last_updated, data.stale);
      } catch (err) {
        console.error('Search request failed', err);
      }
    }, 300);
  });

  // --- Sort dropdown --------------------------------------------------------
  document.getElementById('sort-select').addEventListener('change', (event) => {
    currentSort = event.target.value;
    renderCoins(getSortedDisplayCoins());
  });

  // --- Boot -----------------------------------------------------------------
  async function boot() {
    await loadFavorites();
    renderPickOfDay(initialData.pick_of_day);
    renderAll(initialData.coins, initialData.news, initialData.last_updated, initialData.stale);
    initTheme();
    initModal();
  }

  boot();
})();
