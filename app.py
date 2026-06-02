"""Flask routes only — no business logic."""

from flask import Flask, Response, jsonify, render_template, request

from exporter import VALID_DATASETS, build_export
from favorites import get_favorites, is_valid_client_id, toggle_favorite
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
    q = str(q).strip()
    if not q:
        return jsonify({"error": "Query parameter 'q' is required."}), 400
    if len(q) > MAX_QUERY_LENGTH:
        return jsonify({"error": f"Query must be at most {MAX_QUERY_LENGTH} characters."}), 400
    return jsonify(filter_cache(q))


@app.route("/export/csv")
def export_csv():
    """Download cached coins and/or news as CSV (or ZIP for both)."""
    dataset = request.args.get("dataset", "").strip().lower()
    if dataset not in VALID_DATASETS:
        return jsonify({"error": "dataset must be coins, news, or all."}), 400

    content, filename, mimetype = build_export(dataset)
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/favorites")
def favorites_list():
    """Return the current client's starred coin ids (ordered)."""
    client_id = request.headers.get("X-Client-Id", "").strip().lower()
    if not is_valid_client_id(client_id):
        return jsonify({"error": "Valid X-Client-Id header is required."}), 400
    return jsonify({"favorites": get_favorites(client_id)})


@app.route("/favorites/<coin_id>", methods=["POST"])
def favorites_toggle(coin_id):
    """Toggle a coin in the client's favorites and persist to data/favorites.json."""
    client_id = request.headers.get("X-Client-Id", "").strip().lower()
    if not is_valid_client_id(client_id):
        return jsonify({"error": "Valid X-Client-Id header is required."}), 400

    coin_id = str(coin_id).strip().lower()
    try:
        favorites, is_favorited = toggle_favorite(client_id, coin_id)
        return jsonify({"favorites": favorites, "is_favorited": is_favorited})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400



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
