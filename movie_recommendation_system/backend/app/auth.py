"""
Authentication routes: register, login, current user, and password reset.

POST /auth/register  — Creates user account + returns JWT
POST /auth/login     — Validates credentials + returns JWT
GET  /auth/me        — Returns current user profile (JWT required)
"""
import hashlib
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from .extensions import db, bcrypt
from .models import PasswordResetToken, User, utc_now

auth_bp = Blueprint("auth", __name__)


def _create_user_token(user):
    return create_access_token(
        identity=str(user.id),
        additional_claims={
            "authIssuedAt": utc_now().timestamp(),
            "authScope": "user",
        },
    )


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    first_name         = (data.get("firstName") or "").strip()
    last_name          = (data.get("lastName") or "").strip()
    email              = (data.get("email") or "").strip().lower()
    password           = data.get("password", "")
    favorite_genres    = data.get("favoriteGenres", [])
    favorite_movies    = data.get("favoriteMovies", [])   # list of TMDB ids
    include_watched    = bool(data.get("includeWatched", False))
    watching_frequency = data.get("watchingFrequency", "weekly")

    # ── Validation ─────────────────────────────────────────────────────────
    if not all([first_name, last_name, email, password]):
        return jsonify({"error": "All fields are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists"}), 409

    # ── Create user ─────────────────────────────────────────────────────────
    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
        include_watched=include_watched,
        watching_frequency=watching_frequency,
    )
    user.favorite_genres = favorite_genres
    user.favorite_movies = favorite_movies

    db.session.add(user)
    db.session.commit()

    token = _create_user_token(user)
    return jsonify({"token": token, "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        # Always return the same message to avoid user-enumeration attacks
        return jsonify({"error": "Invalid email or password"}), 401

    from .admin_service import get_security_state

    security = get_security_state(user)
    if security:
        if not security.is_active:
            return jsonify({"error": "This account is inactive"}), 403
        if security.password_reset_required:
            return jsonify({"error": "A password reset is required for this account"}), 403

    token = _create_user_token(user)
    return jsonify({"token": token, "user": user.to_dict()}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict())


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}
    raw_token = data.get("token", "")
    new_password = data.get("newPassword", "")
    if not raw_token or len(new_password) < 8:
        return jsonify({"error": "A valid token and an 8-character password are required"}), 400

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    reset = PasswordResetToken.query.filter_by(
        token_hash=token_hash,
        used_at=None,
    ).first()
    if not reset or reset.expires_at <= utc_now():
        return jsonify({"error": "This reset link is invalid or expired"}), 400

    user = db.session.get(User, reset.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    now = utc_now()
    user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
    PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update(
        {"used_at": now}
    )

    from .admin_service import get_security_state, revoke_user_tokens

    security = get_security_state(user, create=True)
    security.password_reset_required = False
    revoke_user_tokens(user, when=now)
    db.session.commit()
    return jsonify({"message": "Password reset successfully"})
