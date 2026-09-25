"""
Movie routes.

GET /movies/search?q=&limit=    — Title search (used by onboarding autocomplete)
GET /movies/trending?limit=     — Top movies by popularity
GET /movies/<tmdb_id>           — Full movie metadata + cast
POST /movies/batch              — Bulk fetch {ids: [tmdb_id, ...]}
"""
from flask import Blueprint, request, jsonify
from .movie_service import movie_service

movie_bp = Blueprint("movies", __name__)


@movie_bp.route("/search", methods=["GET"])
def search():
    q     = request.args.get("q", "").strip()
    try:
        limit = min(int(request.args.get("limit", 10)), 50)
    except (TypeError, ValueError):
        limit = 10
    return jsonify(movie_service.search(q, limit=limit))


@movie_bp.route("/trending", methods=["GET"])
def trending():
    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except (TypeError, ValueError):
        limit = 20
    return jsonify(movie_service.get_trending(limit=limit))


@movie_bp.route("/<int:tmdb_id>", methods=["GET"])
def get_movie(tmdb_id):
    movie = movie_service.get_by_id(tmdb_id)
    if not movie:
        return jsonify({"error": "Movie not found"}), 404
    return jsonify(movie)


@movie_bp.route("/batch", methods=["POST"])
def batch():
    data = request.get_json(silent=True) or {}
    ids  = data.get("ids", [])
    if not ids:
        return jsonify([])
    return jsonify(movie_service.get_by_ids(ids[:100]))  # hard cap
