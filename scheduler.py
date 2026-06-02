"""Background cache refresh every 15 minutes."""

import os
from functools import partial

from apscheduler.schedulers.background import BackgroundScheduler

from fetcher import refresh_cache

_scheduler: BackgroundScheduler | None = None


def _should_start_scheduler(app) -> bool:
    """Avoid double scheduler when Flask debug reloader spawns a child process."""
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return False
    return True


def init_scheduler(app) -> None:
    """Start APScheduler with 15-minute refresh and an immediate startup refresh."""
    global _scheduler
    if not _should_start_scheduler(app):
        return
    if _scheduler is not None:
        return

    refresh_cache(trigger="startup")

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        partial(refresh_cache, trigger="scheduler"),
        "interval",
        minutes=15,
        id="cache_refresh",
        replace_existing=True,
    )
    _scheduler.start()
