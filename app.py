"""Flask routes only — no business logic."""

from flask import Flask, jsonify, render_template, request

from fetcher import (
    MAX_QUERY_LENGTH,
    VALID_CHART_DAYS,
    fetch_coin_chart,
    fetch_coin_detail,
    filter_cache,
    format_last_updated,
    is_valid_coin_id,
    load_cache,
)
from scheduler import init_scheduler

app = Flask(__name__)


@app.route("/")
def index():
    cache = load_cache()
    last_updated = cache.get("last_updated")
    return render_template(
        "index.html",
        coins=cache.get("coins", []),
        news=cache.get("news", []),
        last_updated=last_updated,
        last_updated_display=format_last_updated(last_updated),
        stale=cache.get("stale", False),
        fetch_errors=cache.get("fetch_errors", []),
        pick_of_day=cache.get("pick_of_day"),
    )


@app.route("/search")
def search():
    q = request.args.get("q", "")
    if q is None:
        q = ""
    q = str(q).strip()
    if not q:
        return jsonify({"error": "Query parameter 'q' is required."}), 400
    if len(q) > MAX_QUERY_LENGTH:
        return jsonify({"error": f"Query must be at most {MAX_QUERY_LENGTH} characters."}), 400

    result = filter_cache(q)
    return jsonify(result)


@app.route("/coin/<coin_id>")
def coin_detail(coin_id):
    """Return coin description and citations for the detail modal (no chart)."""
    coin_id = str(coin_id).strip().lower()
    if not is_valid_coin_id(coin_id):
        return jsonify({"error": "Invalid coin id."}), 400

    try:
        return jsonify(fetch_coin_detail(coin_id))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/coin/<coin_id>/chart")
def coin_chart(coin_id):
    """Return price history for one coin — separate route so chart range changes are cheap."""
    coin_id = str(coin_id).strip().lower()
    if not is_valid_coin_id(coin_id):
        return jsonify({"error": "Invalid coin id."}), 400

    days_raw = request.args.get("days", "7")
    try:
        days = int(days_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "Query parameter 'days' must be an integer."}), 400
    if days not in VALID_CHART_DAYS:
        return jsonify({"error": f"days must be one of {sorted(VALID_CHART_DAYS)}."}), 400

    try:
        return jsonify(fetch_coin_chart(coin_id, days))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@app.errorhandler(404)
def not_found(_error):
    return (
        render_template("_error.html", code=404, message="Page not found."),
        404,
    )


@app.errorhandler(500)
def server_error(_error):
    return (
        render_template(
            "_error.html",
            code=500,
            message="Something went wrong. Please try again later.",
        ),
        500,
    )


init_scheduler(app)
