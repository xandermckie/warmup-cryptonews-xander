"""Read/write user favorite coin ids in data/favorites.json."""

import json
import re
from pathlib import Path

from fetcher import is_valid_coin_id

FAVORITES_PATH = Path(__file__).parent / "data" / "favorites.json"
CLIENT_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
MAX_FAVORITES = 50


def is_valid_client_id(client_id: str) -> bool:
    """Validate browser-generated client id (UUID) before reading/writing favorites."""
    return bool(client_id and CLIENT_ID_PATTERN.match(client_id.lower()))


def _empty_store() -> dict:
    return {"clients": {}}


def load_favorites_store() -> dict:
    """Load the full favorites file; return empty structure if missing or corrupt."""
    if not FAVORITES_PATH.exists():
        return _empty_store()
    try:
        with open(FAVORITES_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        if "clients" not in data or not isinstance(data["clients"], dict):
            return _empty_store()
        return data
    except (json.JSONDecodeError, OSError):
        return _empty_store()


def save_favorites_store(data: dict) -> None:
    """Persist favorites file to disk."""
    FAVORITES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FAVORITES_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def get_favorites(client_id: str) -> list[str]:
    """Return ordered favorite coin ids for one client."""
    store = load_favorites_store()
    favorites = store["clients"].get(client_id, [])
    return [coin_id for coin_id in favorites if is_valid_coin_id(coin_id)]


def toggle_favorite(client_id: str, coin_id: str) -> tuple[list[str], bool]:
    """
    Add or remove a coin from the client's favorites.

    Returns (updated_favorites_list, is_now_favorited).
    """
    if not is_valid_client_id(client_id):
        raise ValueError("Invalid client id.")
    if not is_valid_coin_id(coin_id):
        raise ValueError("Invalid coin id.")

    store = load_favorites_store()
    favorites: list[str] = list(store["clients"].get(client_id, []))

    if coin_id in favorites:
        favorites.remove(coin_id)
        is_favorited = False
    else:
        if len(favorites) >= MAX_FAVORITES:
            raise ValueError(f"You can favorite at most {MAX_FAVORITES} coins.")
        favorites.append(coin_id)
        is_favorited = True

    store["clients"][client_id] = favorites
    save_favorites_store(store)
    return favorites, is_favorited
