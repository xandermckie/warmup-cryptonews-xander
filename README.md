# Crypto News Visualizer

Flask web app showing live cryptocurrency prices (CoinGecko) and crypto-related news (NewsAPI). Data is cached in `data/cache.json` and refreshed every 15 minutes in the background—no server restart required.

## Setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # macOS/Linux
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy environment file and add your NewsAPI key:

   ```bash
   copy .env.example .env   # Windows
   # cp .env.example .env   # macOS/Linux
   ```

   Edit `.env` and set `NEWS_API_KEY` from [newsapi.org](https://newsapi.org).

4. Run the app:

   ```bash
   flask run
   ```

   Open http://127.0.0.1:5000/

## Architecture

| File | Role |
|------|------|
| `app.py` | Flask routes only (`/`, `/search`, error handlers) |
| `fetcher.py` | CoinGecko & NewsAPI calls, cache read/write, stale fallback |
| `scheduler.py` | APScheduler background job every 15 minutes |
| `data/cache.json` | Cached coins, news, timestamps, error state |

On API failure, the app keeps the previous cache, sets `stale: true`, and shows a “Showing cached data” badge with the last successful timestamp.

## Features

- Top 50 coins by market cap with images and 24h change
- Scrolling price ticker across the top
- Crypto news headlines
- Client-side search via `/search` (no page reload)
- “Last updated” timestamp always visible

## Requirements

- Python 3.10+
- Free NewsAPI key (CoinGecko requires no key)
