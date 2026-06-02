"""Read/write fetch refresh events in data/fetch-log.json."""

import json
from pathlib import Path

FETCH_LOG_PATH = Path(__file__).parent / "data" / "fetch-log.json"
MAX_EVENTS = 10


def _empty_log() -> dict:
    return {"events": []}


def load_fetch_log() -> dict:
    """Load the fetch log file; return empty structure if missing or corrupt."""
    if not FETCH_LOG_PATH.exists():
        return _empty_log()
    try:
        with open(FETCH_LOG_PATH, encoding="utf-8") as handle:
            data = json.load(handle)
        if "events" not in data or not isinstance(data["events"], list):
            return _empty_log()
        return data
    except (json.JSONDecodeError, OSError):
        return _empty_log()


def _save_fetch_log(data: dict) -> None:
    """Persist fetch log file to disk."""
    FETCH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FETCH_LOG_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def append_fetch_event(event: dict) -> None:
    """Prepend one event and keep at most MAX_EVENTS entries."""
    log = load_fetch_log()
    events = log.get("events", [])
    log["events"] = [event] + events[: MAX_EVENTS - 1]
    _save_fetch_log(log)
