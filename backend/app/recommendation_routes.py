"""
Recommendation endpoints.

GET  /movies/recommendations?section=recommended|favorites|trending&n=20
     JWT required — returns personalised picks for the current user.

GET  /movies/similar/<tmdb_id>?n=10
     Public — content-based similar movies for any given film.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from .models import User
from .ml_service import get_recommendations

rec_bp = Blueprint("recommendations", __name__)


@rec_bp.route("/recommendations", methods=["GET"])
@jwt_required()
def recommendations():
    user = User.query.get_or_404(int(get_jwt_identity()))

    section = request.args.get("section", "recommended")   # recommended | favorites | trending
    try:
        n   = min(int(request.args.get("n", 20)), 50)
    except (TypeError, ValueError):
        n   = 20

    # Exclude watched movies unless the user has opted in
    exclude = [] if user.include_watched else user.watched_movies

    recs = get_recommendations(
        favorite_movie_tmdb_ids=user.favorite_movies,
        favorite_genres=user.favorite_genres,
        watched_tmdb_ids=exclude,
        movielens_user_id=user.movielens_user_id,
        n=n,
        section=section,
    )
    return jsonify(recs)


@rec_bp.route("/similar/<int:tmdb_id>", methods=["GET"])
def similar_movies(tmdb_id):
    """Content-based similar movies — no auth required."""
    try:
        n = min(int(request.args.get("n", 10)), 30)
    except (TypeError, ValueError):
        n = 10
    recs = get_recommendations(
        favorite_movie_tmdb_ids=[tmdb_id],
        n=n,
        section="favorites",
    )
    return jsonify(recs)
