"""
User profile routes.

GET  /user/profile           — Get current user data
PUT  /user/profile           — Update name, genres, movies, preferences
PUT  /user/password          — Change password (requires current password)
POST /user/watch             — Add movie to watched list
DELETE /user/watch/<tmdb_id> — Remove movie from watched list
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .extensions import db, bcrypt
from .models import User

user_bp = Blueprint("user", __name__)


def _current_user():
    return User.query.get_or_404(int(get_jwt_identity()))


@user_bp.route("/profile", methods=["GET"])
@jwt_required()
def get_profile():
    return jsonify(_current_user().to_dict())


@user_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    user = _current_user()
    data = request.get_json(silent=True) or {}

    if "firstName" in data:
        user.first_name = data["firstName"].strip()
    if "lastName" in data:
        user.last_name = data["lastName"].strip()
    if "favoriteGenres" in data:
        user.favorite_genres = data["favoriteGenres"]
    if "favoriteMovies" in data:
        user.favorite_movies = data["favoriteMovies"]
    if "preferences" in data:
        prefs = data["preferences"]
        if "includeWatched" in prefs:
            user.include_watched = bool(prefs["includeWatched"])
        if "watchingFrequency" in prefs:
            user.watching_frequency = prefs["watchingFrequency"]

    db.session.commit()
    return jsonify(user.to_dict())


@user_bp.route("/password", methods=["PUT"])
@jwt_required()
def change_password():
    user = _current_user()
    data = request.get_json(silent=True) or {}
    current     = data.get("currentPassword", "")
    new_password = data.get("newPassword", "")

    if not bcrypt.check_password_hash(user.password_hash, current):
        return jsonify({"error": "Current password is incorrect"}), 403
    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters"}), 400

    user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")

    from .admin_service import get_security_state, revoke_user_tokens

    security = get_security_state(user, create=True)
    security.password_reset_required = False
    revoke_user_tokens(user)
    db.session.commit()
    return jsonify({"message": "Password updated successfully"})


@user_bp.route("/watch", methods=["POST"])
@jwt_required()
def mark_watched():
    user = _current_user()
    data = request.get_json(silent=True) or {}
    movie_id = data.get("movieId")
    if movie_id is None:
        return jsonify({"error": "movieId is required"}), 400

    watched = user.watched_movies
    if movie_id not in watched:
        watched.append(movie_id)
        user.watched_movies = watched
        db.session.commit()

    return jsonify({"watchedMovies": user.watched_movies})


@user_bp.route("/watch/<int:movie_id>", methods=["DELETE"])
@jwt_required()
def remove_watched(movie_id):
    user = _current_user()
    watched = user.watched_movies
    if movie_id in watched:
        watched.remove(movie_id)
        user.watched_movies = watched
        db.session.commit()
    return jsonify({"watchedMovies": user.watched_movies})
