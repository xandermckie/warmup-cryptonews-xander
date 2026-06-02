# Architecture Notepad — Crypto News Visualizer

## Module split

- **app.py** — Routes only: `/` renders template from cache; `/search` returns filtered JSON; 404/500 use `_error.html`.
- **fetcher.py** — All HTTP and cache logic: `fetch_coins`, `fetch_news`, `refresh_cache`, `load_cache`, `filter_cache`.
- **scheduler.py** — `BackgroundScheduler` calls `refresh_cache` every 15 minutes; startup runs one refresh immediately.

## Cache schema (`data/cache.json`)

- `last_updated` — ISO UTC timestamp of last refresh attempt
- `stale` — `true` if any API failed on last refresh (UI shows cached data badge)
- `fetch_errors` — Human-readable error messages from failed APIs
- `coins` — Top 50 by market cap (id, symbol, name, image, price, 24h %, rank)
- `news` — Up to 20 articles (title, description, url, source, published_at)

## Scheduler

- Interval: **15 minutes**
- Flask debug reloader guard: scheduler starts only when `WERKZEUG_RUN_MAIN=true` to avoid duplicate jobs
- No restart needed: cache file updates in place; next page load or search reads fresh data

## Stale-data policy

- Partial or total API failure: keep previous `coins` / `news`, set `stale: true`, record errors in `fetch_errors`
- Full success: replace data, `stale: false`

## Coin scope

- CoinGecko `coins/markets` — top **50** by market cap (not full CoinGecko catalog) for usable ticker and grid

## APIs

- CoinGecko: no API key
- NewsAPI: `NEWS_API_KEY` in `.env` only
