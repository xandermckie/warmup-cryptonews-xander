"""API calls and cache management for crypto prices and news."""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

load_dotenv()

CACHE_PATH = Path(__file__).parent / "data" / "cache.json"
COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=market_cap_desc&per_page=50&page=1&sparkline=false"
)
NEWSAPI_URL = "https://newsapi.org/v2/everything"
REQUEST_TIMEOUT = 10
MAX_QUERY_LENGTH = 100
VALID_CHART_DAYS = {7, 30, 90, 365}
COIN_ID_PATTERN = re.compile(r"^[a-z0-9\-]+$")
# Only fetch a few missing genesis dates per refresh to avoid exhausting the API quota.
GENESIS_BATCH_PER_REFRESH = 2
GENESIS_FETCH_DELAY_SEC = 2.0


def _empty_cache() -> dict:
    return {
        "last_updated": None,
        "stale": True,
        "fetch_errors": [],
        "coins": [],
        "news": [],
        "pick_of_day": None,
    }


def _strip_html(html: str) -> str:
    """Remove HTML tags from CoinGecko description strings."""
    return re.sub(r"<[^>]+>", "", html or "").strip()


def is_valid_coin_id(coin_id: str) -> bool:
    """Validate CoinGecko coin id format before hitting external APIs."""
    return bool(coin_id and COIN_ID_PATTERN.match(coin_id))


def format_last_updated(iso_timestamp: str | None) -> str:
    """Format UTC ISO timestamp for display in Central Time, e.g. 2026-06-02 1:05PM CST."""
    if not iso_timestamp:
        return "Never"
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        cst = dt.astimezone(ZoneInfo("America/Chicago"))
        hour = cst.strftime("%I").lstrip("0") or "12"
        minute = cst.strftime("%M")
        ampm = cst.strftime("%p")
        return f"{cst.strftime('%Y-%m-%d')} {hour}:{minute}{ampm} CST"
    except (ValueError, TypeError):
        return str(iso_timestamp)


def _is_rate_limited(exc: requests.RequestException) -> bool:
    """Return True when CoinGecko rejected the call for exceeding rate limits."""
    response = getattr(exc, "response", None)
    return response is not None and response.status_code == 429


def load_cache() -> dict:
    """Read cache from disk; return empty skeleton if missing or corrupt."""
    if not CACHE_PATH.exists():
        return _empty_cache()
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for key in ("coins", "news", "fetch_errors"):
            if key not in data:
                data[key] = []
        if "stale" not in data:
            data["stale"] = True
        if "pick_of_day" not in data:
            data["pick_of_day"] = None
        return data
    except (json.JSONDecodeError, OSError):
        return _empty_cache()


def save_cache(data: dict) -> None:
    """Write cache to disk."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def fetch_coins() -> list:
    """Fetch top 50 coins by market cap from CoinGecko."""
    response = requests.get(COINGECKO_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    raw = response.json()
    return [
        {
            "id": coin["id"],
            "symbol": coin["symbol"],
            "name": coin["name"],
            "image": coin.get("image", ""),
            "current_price": coin.get("current_price"),
            "price_change_percentage_24h": coin.get("price_change_percentage_24h"),
            "market_cap_rank": coin.get("market_cap_rank"),
            # Used by the sidebar "pick of the day" heuristic (not financial advice).
            "ath": coin.get("ath"),
            "ath_change_percentage": coin.get("ath_change_percentage"),
            "genesis_date": None,
        }
        for coin in raw
    ]


def _fetch_genesis_date(coin_id: str) -> str | None:
    """Fetch genesis_date for one coin using CoinGecko's lightweight detail endpoint."""
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "false",
        "community_data": "false",
        "developer_data": "false",
    }
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json().get("genesis_date")


def enrich_coins_with_genesis(coins: list, previous_coins: list | None = None) -> list:
    """
    Attach genesis_date to each coin for release-date sorting.

    Reuses dates already stored in cache to avoid redundant API calls on every refresh.
    Skips all CoinGecko calls when every coin already has a cached genesis_date.
    Only coins still missing a date trigger a new request (max GENESIS_BATCH_PER_REFRESH).
    """
    previous = {c["id"]: c.get("genesis_date") for c in (previous_coins or [])}

    if coins and all(previous.get(coin["id"]) for coin in coins):
        return [{**coin, "genesis_date": previous[coin["id"]]} for coin in coins]

    enriched: list[dict] = []
    fetches_this_cycle = 0

    for coin in coins:
        coin_id = coin["id"]
        genesis_date = previous.get(coin_id) or coin.get("genesis_date")

        if genesis_date is None and fetches_this_cycle < GENESIS_BATCH_PER_REFRESH:
            try:
                genesis_date = _fetch_genesis_date(coin_id)
                fetches_this_cycle += 1
                time.sleep(GENESIS_FETCH_DELAY_SEC)
            except requests.RequestException:
                genesis_date = None

        enriched.append({**coin, "genesis_date": genesis_date})

    return enriched


def get_coin_from_cache(coin_id: str) -> dict | None:
    """Look up a single coin from the on-disk cache for modal fallbacks."""
    for coin in load_cache().get("coins", []):
        if coin.get("id") == coin_id:
            return coin
    return None


def compute_pick_of_day(coins: list) -> dict | None:
    """
    Pick a fun 'coin of the day' using a simple momentum + value heuristic.

    Favors established coins (top 30 by market cap) that are well below their
    all-time high but showing positive 24h momentum. This is entertainment only.
    """
    if not coins:
        return None

    candidates = [
        c for c in coins
        if c.get("market_cap_rank") and c["market_cap_rank"] <= 30
    ]
    if not candidates:
        candidates = coins[:10]

    best: dict | None = None
    best_score = float("-inf")

    for coin in candidates:
        ath_change = coin.get("ath_change_percentage")
        change_24h = coin.get("price_change_percentage_24h") or 0
        rank = coin.get("market_cap_rank") or 50

        if ath_change is None:
            score = change_24h + (51 - rank) * 0.2
        else:
            # Negative ath_change means price is below ATH — larger dip = higher "value" score.
            dip_score = abs(ath_change) if ath_change < 0 else 0
            score = (change_24h * 1.5) + (dip_score * 0.08) + (51 - rank) * 0.3

        if score > best_score:
            best_score = score
            best = coin

    if not best:
        return None

    ath_change = best.get("ath_change_percentage")
    if ath_change is not None and ath_change < 0:
        reason = (
            f"{best['name']} is trading about {abs(ath_change):.1f}% below its all-time high "
            f"with a {best.get('price_change_percentage_24h') or 0:+.2f}% move in the last 24 hours."
        )
    else:
        reason = (
            f"{best['name']} shows strong recent momentum "
            f"({best.get('price_change_percentage_24h') or 0:+.2f}% in 24h) among top market-cap coins."
        )

    return {
        "id": best["id"],
        "name": best["name"],
        "symbol": best["symbol"],
        "image": best.get("image", ""),
        "current_price": best.get("current_price"),
        "price_change_percentage_24h": best.get("price_change_percentage_24h"),
        "ath_change_percentage": best.get("ath_change_percentage"),
        "reason": reason,
    }


def fetch_wikipedia_summary(title: str) -> dict | None:
    """Fetch a short Wikipedia summary for modal citations."""
    slug = title.replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(slug)}"
    headers = {"User-Agent": "CryptoNewsVisualizer/1.0 (educational project)"}

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        page_url = (data.get("content_urls") or {}).get("desktop", {}).get("page")
        return {
            "title": data.get("title"),
            "extract": data.get("extract"),
            "url": page_url,
        }
    except requests.RequestException:
        return None


def fetch_coin_detail(coin_id: str) -> dict:
    """Fetch rich coin metadata for the detail modal (description + genesis date)."""
    if not is_valid_coin_id(coin_id):
        raise ValueError("Invalid coin id")

    cached = get_coin_from_cache(coin_id)
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "false",
        "developer_data": "false",
    }

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        description = _strip_html((data.get("description") or {}).get("en", ""))
        wiki = fetch_wikipedia_summary(data.get("name") or coin_id)
        return {
            "id": coin_id,
            "name": data.get("name"),
            "symbol": (data.get("symbol") or "").upper(),
            "image": (data.get("image") or {}).get("small", ""),
            "genesis_date": data.get("genesis_date"),
            "description": description,
            "description_source": "CoinGecko" if description else None,
            "wikipedia": wiki,
        }
    except requests.RequestException as exc:
        # Graceful fallback when CoinGecko rate-limits or is unavailable.
        name = (cached or {}).get("name") or coin_id.replace("-", " ").title()
        wiki = fetch_wikipedia_summary(name)
        reason = "rate_limit" if _is_rate_limited(exc) else "unavailable"
        return {
            "id": coin_id,
            "name": name,
            "symbol": ((cached or {}).get("symbol") or coin_id[:3]).upper(),
            "image": (cached or {}).get("image", ""),
            "genesis_date": (cached or {}).get("genesis_date"),
            "description": "",
            "description_source": None,
            "wikipedia": wiki,
            "fallback": True,
            "fallback_reason": reason,
        }


def fetch_coin_chart(coin_id: str, days: int) -> dict:
    """Fetch USD price history from CoinGecko for the modal performance chart."""
    if not is_valid_coin_id(coin_id):
        raise ValueError("Invalid coin id")
    if days not in VALID_CHART_DAYS:
        raise ValueError(f"days must be one of {sorted(VALID_CHART_DAYS)}")

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": str(days)}

    try:
        response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        prices = response.json().get("prices", [])
    except requests.RequestException as exc:
        return {
            "days": days,
            "prices": [],
            "source": "CoinGecko",
            "unavailable": True,
            "rate_limited": _is_rate_limited(exc),
        }

    return {
        "days": days,
        "prices": [{"timestamp": point[0], "price": point[1]} for point in prices],
        "source": "CoinGecko",
    }


def fetch_news() -> list:
    """Fetch crypto-related headlines from NewsAPI."""
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise ValueError("NEWS_API_KEY is not set in environment")

    params = {
        "q": "cryptocurrency OR bitcoin OR ethereum",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 20,
        "apiKey": api_key,
    }
    response = requests.get(NEWSAPI_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "ok":
        raise ValueError(payload.get("message", "NewsAPI returned an error"))

    articles = []
    for article in payload.get("articles", []):
        articles.append(
            {
                "title": article.get("title") or "",
                "description": article.get("description") or "",
                "url": article.get("url") or "",
                "source": (article.get("source") or {}).get("name", "Unknown"),
                "published_at": article.get("publishedAt") or "",
            }
        )
    return articles


def refresh_cache() -> dict:
    """Fetch fresh data, merge with stale fallback on failure, write cache."""
    previous = load_cache()
    errors: list[str] = []
    coins = previous.get("coins", [])
    news = previous.get("news", [])
    any_success = False

    try:
        coins = fetch_coins()
        coins = enrich_coins_with_genesis(coins, previous.get("coins", []))
        any_success = True
    except (requests.RequestException, ValueError) as exc:
        errors.append(f"CoinGecko: {exc}")

    try:
        news = fetch_news()
        any_success = True
    except (requests.RequestException, ValueError) as exc:
        errors.append(f"NewsAPI: {exc}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stale = len(errors) > 0
    if not any_success and not previous.get("coins") and not previous.get("news"):
        stale = True

    data = {
        "last_updated": now,
        "stale": stale,
        "fetch_errors": errors,
        "coins": coins,
        "news": news,
        "pick_of_day": compute_pick_of_day(coins) if coins else previous.get("pick_of_day"),
    }
    save_cache(data)
    return data


def filter_cache(query: str, cache: dict | None = None) -> dict:
    """Filter coins and news by query string (case-insensitive)."""
    if cache is None:
        cache = load_cache()
    q = query.lower().strip()
    if not q:
        return {
            "coins": cache.get("coins", []),
            "news": cache.get("news", []),
            "last_updated": cache.get("last_updated"),
            "stale": cache.get("stale", False),
        }

    coins = [
        c
        for c in cache.get("coins", [])
        if q in c.get("name", "").lower()
        or q in c.get("symbol", "").lower()
        or q in c.get("id", "").lower()
    ]
    news = [
        n
        for n in cache.get("news", [])
        if q in n.get("title", "").lower()
        or q in (n.get("description") or "").lower()
    ]
    return {
        "coins": coins,
        "news": news,
        "last_updated": cache.get("last_updated"),
        "stale": cache.get("stale", False),
    }
