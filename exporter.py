"""Build CSV/ZIP exports from cached crypto and news data."""

import csv
import io
import zipfile
from datetime import datetime, timezone

from fetcher import load_cache

VALID_DATASETS = frozenset({"coins", "news", "all"})

COIN_COLUMNS = (
    "id",
    "symbol",
    "name",
    "current_price",
    "price_change_percentage_24h",
    "market_cap_rank",
    "ath",
    "ath_change_percentage",
    "genesis_date",
    "image",
)

NEWS_COLUMNS = ("title", "description", "source", "published_at", "url")


def _export_date_suffix(cache: dict) -> str:
    """Derive YYYYMMDD filename suffix from cache last_updated or UTC today."""
    last_updated = cache.get("last_updated")
    if isinstance(last_updated, str) and last_updated.strip():
        try:
            dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            return dt.strftime("%Y%m%d")
        except ValueError:
            pass
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _cell(value) -> str:
    """Format a cache field for CSV output; None becomes empty string."""
    if value is None:
        return ""
    return str(value)


def build_coins_csv(coins: list) -> bytes:
    """Serialize coin list to UTF-8 CSV bytes with header row."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(COIN_COLUMNS)
    for coin in coins:
        if not isinstance(coin, dict):
            continue
        writer.writerow([_cell(coin.get(col)) for col in COIN_COLUMNS])
    return buffer.getvalue().encode("utf-8")


def build_news_csv(news: list) -> bytes:
    """Serialize news list to UTF-8 CSV bytes with header row."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(NEWS_COLUMNS)
    for article in news:
        if not isinstance(article, dict):
            continue
        writer.writerow([_cell(article.get(col)) for col in NEWS_COLUMNS])
    return buffer.getvalue().encode("utf-8")


def build_export_zip(cache: dict) -> bytes:
    """Package coins.csv and news.csv into a single ZIP archive."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("coins.csv", build_coins_csv(cache.get("coins", [])))
        archive.writestr("news.csv", build_news_csv(cache.get("news", [])))
    return zip_buffer.getvalue()


def build_export(dataset: str) -> tuple[bytes, str, str]:
    """
    Build export content from cache for the requested dataset.

    Returns (content_bytes, filename, mimetype).
    """
    cache = load_cache()
    date_suffix = _export_date_suffix(cache)

    if dataset == "coins":
        return (
            build_coins_csv(cache.get("coins", [])),
            f"cryptox-coins-{date_suffix}.csv",
            "text/csv; charset=utf-8",
        )
    if dataset == "news":
        return (
            build_news_csv(cache.get("news", [])),
            f"cryptox-news-{date_suffix}.csv",
            "text/csv; charset=utf-8",
        )
    return (
        build_export_zip(cache),
        f"cryptox-cache-{date_suffix}.zip",
        "application/zip",
    )
