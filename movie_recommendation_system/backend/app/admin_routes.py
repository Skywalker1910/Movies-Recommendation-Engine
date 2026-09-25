"""Protected administration endpoints for users and model serving controls."""

from __future__ import annotations

import hashlib
import platform
import secrets
import time
from datetime import timedelta

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import or_, text

from .admin_service import (
    DEFAULT_MODEL_CONFIG,
    admin_required,
    create_admin_access_token,
    ensure_default_model_config,
    get_active_model_config,
    get_security_state,
    record_audit,
    revoke_admin_tokens,
    revoke_user_tokens,
)
from .extensions import bcrypt, db
from .models import (
    AdminAccount,
    AdminActivityEvent,
    AdminPasswordResetToken,
    ModelConfigVersion,
    PasswordResetToken,
    User,
    UserSecurityState,
    utc_now,
)


admin_bp = Blueprint("admin", __name__)


def _bounded_int(value, default, minimum, maximum):
    try:
        return min(max(int(value), minimum), maximum)
    except (TypeError, ValueError):
        return default


def _id_list(value, limit=500):
    if not isinstance(value, list):
        raise ValueError("Expected a list of movie IDs")
    result = []
    for item in value:
        try:
            movie_id = int(item)
        except (TypeError, ValueError) as exc:
            raise ValueError("Movie IDs must be integers") from exc
        if movie_id > 0 and movie_id not in result:
            result.append(movie_id)
    if len(result) > limit:
        raise ValueError(f"At most {limit} movie IDs are allowed")
    return result


def _string_list(value, limit=50):
    if not isinstance(value, list):
        raise ValueError("Expected a list of strings")
    result = []
    for item in value:
        entry = str(item).strip()
        if entry and entry not in result:
            result.append(entry)
    if len(result) > limit:
        raise ValueError(f"At most {limit} values are allowed")
    return result


def _serialize_user(user):
    data = user.to_dict()
    data["favoriteMovieCount"] = len(user.favorite_movies)
    data["watchedMovieCount"] = len(user.watched_movies)
    return data


@admin_bp.route("/auth/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    admin = AdminAccount.query.filter_by(email=email).first()
    if not admin or not bcrypt.check_password_hash(admin.password_hash, password):
        return jsonify({"error": "Invalid administrator credentials"}), 401
    if not admin.is_active:
        return jsonify({"error": "Administrator account is inactive"}), 403
    if admin.password_reset_required:
        return jsonify({
            "error": "Administrator password setup is required",
            "code": "ADMIN_SETUP_REQUIRED",
        }), 403

    admin.last_login_at = utc_now()
    token = create_admin_access_token(admin)
    record_audit(admin.id, "admin.login")
    db.session.commit()
    return jsonify({"token": token, "admin": admin.to_dict()})


@admin_bp.route("/auth/me", methods=["GET"])
@admin_required
def admin_me():
    return jsonify(g.admin_account.to_dict())


@admin_bp.route("/auth/logout", methods=["POST"])
@admin_required
def admin_logout():
    record_audit(g.admin_account.id, "admin.logout")
    revoke_admin_tokens(g.admin_account)
    db.session.commit()
    return jsonify({"message": "Administrator session closed"})


@admin_bp.route("/auth/reset-password", methods=["POST"])
def reset_admin_password():
    data = request.get_json(silent=True) or {}
    raw_token = data.get("token", "")
    new_password = data.get("newPassword", "")
    if not raw_token or len(new_password) < 12:
        return jsonify({
            "error": "A valid token and a 12-character password are required"
        }), 400

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    reset = AdminPasswordResetToken.query.filter_by(
        token_hash=token_hash,
        used_at=None,
    ).first()
    if not reset or reset.expires_at <= utc_now():
        return jsonify({"error": "This administrator setup link is invalid or expired"}), 400
    admin = db.session.get(AdminAccount, reset.admin_id)
    if not admin:
        return jsonify({"error": "Administrator account not found"}), 404

    now = utc_now()
    admin.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
    admin.password_reset_required = False
    revoke_admin_tokens(admin, when=now)
    AdminPasswordResetToken.query.filter_by(admin_id=admin.id, used_at=None).update(
        {"used_at": now}
    )
    record_audit(admin.id, "admin.password_set")
    db.session.commit()
    return jsonify({"message": "Administrator password set successfully"})


@admin_bp.route("/summary", methods=["GET"])
@admin_required
def summary():
    from .ml_service import get_model_status
    from .movie_service import movie_service

    ensure_default_model_config()
    return jsonify({
        "users": {
            "total": User.query.count(),
            "inactive": UserSecurityState.query.filter_by(is_active=False).count(),
            "passwordResetPending": UserSecurityState.query.filter_by(
                password_reset_required=True
            ).count(),
        },
        "administrators": {
            "total": AdminAccount.query.count(),
            "active": AdminAccount.query.filter_by(is_active=True).count(),
        },
        "integrations": {
            "tmdb": movie_service.tmdb_status()
        },
        "model": get_model_status(load_artifacts=False),
        "modelConfig": get_active_model_config(),
    })


@admin_bp.route("/accounts", methods=["GET"])
@admin_required
def admin_accounts():
    accounts = AdminAccount.query.order_by(AdminAccount.created_at.asc()).all()
    return jsonify([account.to_dict() for account in accounts])


@admin_bp.route("/system/health", methods=["GET"])
@admin_required
def system_health():
    from .ml_service import get_model_status
    from .movie_service import movie_service

    started = current_app.extensions.get("started_at", utc_now())
    database_started = time.perf_counter()
    try:
        db.session.execute(text("SELECT 1"))
        database = {
            "healthy": True,
            "latencyMs": round((time.perf_counter() - database_started) * 1000, 2),
        }
    except Exception as exc:
        db.session.rollback()
        database = {
            "healthy": False,
            "latencyMs": None,
            "message": type(exc).__name__,
        }
    return jsonify({
        "api": {
            "healthy": True,
            "environment": (
                "testing" if current_app.testing else
                "development" if current_app.debug else "production"
            ),
            "python": platform.python_version(),
            "platform": platform.system(),
            "startedAt": started.isoformat(),
            "uptimeSeconds": max(int((utc_now() - started).total_seconds()), 0),
        },
        "database": database,
        "tmdb": movie_service.tmdb_status(),
        "models": get_model_status(load_artifacts=False),
    })


@admin_bp.route("/integrations/tmdb/check", methods=["POST"])
@admin_required
def check_tmdb():
    from .movie_service import movie_service

    result = movie_service.check_tmdb()
    record_audit(
        g.admin_account.id,
        "tmdb.health_checked",
        details={
            "healthy": result["healthy"],
            "statusCode": result["statusCode"],
            "latencyMs": result["latencyMs"],
        },
    )
    db.session.commit()
    return jsonify({**movie_service.tmdb_status(), "probe": result})


@admin_bp.route("/integrations/tmdb/cache", methods=["DELETE"])
@admin_required
def clear_tmdb_cache():
    from .movie_service import movie_service

    removed = movie_service.clear_tmdb_cache()
    record_audit(
        g.admin_account.id,
        "tmdb.cache_cleared",
        details={"entriesRemoved": removed},
    )
    db.session.commit()
    return jsonify({"entriesRemoved": removed, "status": movie_service.tmdb_status()})


@admin_bp.route("/models", methods=["GET"])
@admin_required
def models_inventory():
    from .ml_service import get_model_inventory

    return jsonify(get_model_inventory(load_artifacts=False))


@admin_bp.route("/models/verify", methods=["POST"])
@admin_required
def verify_models():
    from .ml_service import get_model_inventory

    inventory = get_model_inventory(load_artifacts=True)
    record_audit(
        g.admin_account.id,
        "models.verified",
        details={
            "available": sum(model["available"] for model in inventory["models"]),
            "total": len(inventory["models"]),
        },
    )
    db.session.commit()
    return jsonify(inventory)


@admin_bp.route("/users", methods=["GET"])
@admin_required
def users():
    query_text = request.args.get("q", "").strip()
    page = _bounded_int(request.args.get("page"), 1, 1, 100000)
    page_size = _bounded_int(request.args.get("pageSize"), 20, 1, 100)
    query = User.query
    if query_text:
        pattern = f"%{query_text}%"
        query = query.filter(or_(
            User.first_name.ilike(pattern),
            User.last_name.ilike(pattern),
            User.email.ilike(pattern),
        ))
    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )
    return jsonify({
        "items": [_serialize_user(user) for user in pagination.items],
        "page": pagination.page,
        "pageSize": pagination.per_page,
        "pages": pagination.pages,
        "total": pagination.total,
    })


@admin_bp.route("/users/<int:user_id>", methods=["GET"])
@admin_required
def user_detail(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(_serialize_user(user))


@admin_bp.route("/users/<int:user_id>", methods=["PATCH"])
@admin_required
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.get_json(silent=True) or {}
    changed = []

    try:
        if "firstName" in data:
            value = str(data["firstName"]).strip()
            if not value:
                raise ValueError("First name cannot be empty")
            user.first_name = value[:100]
            changed.append("firstName")
        if "lastName" in data:
            value = str(data["lastName"]).strip()
            if not value:
                raise ValueError("Last name cannot be empty")
            user.last_name = value[:100]
            changed.append("lastName")
        if "email" in data:
            email = str(data["email"]).strip().lower()
            if "@" not in email:
                raise ValueError("A valid email address is required")
            duplicate = User.query.filter(User.email == email, User.id != user.id).first()
            if duplicate:
                return jsonify({"error": "That email address is already in use"}), 409
            user.email = email[:255]
            changed.append("email")
        if "favoriteGenres" in data:
            user.favorite_genres = _string_list(data["favoriteGenres"])
            changed.append("favoriteGenres")
        if "favoriteMovies" in data:
            user.favorite_movies = _id_list(data["favoriteMovies"])
            changed.append("favoriteMovies")
        if "watchedMovies" in data:
            user.watched_movies = _id_list(data["watchedMovies"])
            changed.append("watchedMovies")
        if "movielensUserId" in data:
            raw_id = data["movielensUserId"]
            user.movielens_user_id = int(raw_id) if raw_id not in (None, "") else None
            if user.movielens_user_id is not None and user.movielens_user_id <= 0:
                raise ValueError("MovieLens user ID must be positive")
            changed.append("movielensUserId")
        if "preferences" in data:
            preferences = data["preferences"] or {}
            if "includeWatched" in preferences:
                user.include_watched = bool(preferences["includeWatched"])
            if "watchingFrequency" in preferences:
                frequency = preferences["watchingFrequency"]
                if frequency not in {"daily", "weekly", "monthly"}:
                    raise ValueError("Invalid watching frequency")
                user.watching_frequency = frequency
            changed.append("preferences")
        if "isActive" in data:
            active = bool(data["isActive"])
            security = get_security_state(user, create=True)
            security.is_active = active
            changed.append("isActive")
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400

    record_audit(
        g.admin_account.id,
        "user.updated",
        target_user_id=user.id,
        details={"fields": sorted(set(changed))},
    )
    db.session.commit()
    return jsonify(_serialize_user(user))


@admin_bp.route("/users/<int:user_id>/password-reset", methods=["POST"])
@admin_required
def create_password_reset(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    now = utc_now()
    PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update(
        {"used_at": now}
    )
    raw_token = secrets.token_urlsafe(32)
    expires_at = now + timedelta(
        minutes=current_app.config.get("PASSWORD_RESET_MINUTES", 30)
    )
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=expires_at,
    )
    db.session.add(reset)
    security = get_security_state(user, create=True)
    security.password_reset_required = True
    revoke_user_tokens(user, when=now)
    record_audit(
        g.admin_account.id,
        "user.password_reset_created",
        target_user_id=user.id,
        details={"expiresAt": expires_at.isoformat()},
    )
    db.session.commit()

    reset_url = (
        f"{current_app.config['FRONTEND_URL']}/reset-password?token={raw_token}"
    )
    return jsonify({
        "resetUrl": reset_url,
        "expiresAt": expires_at.isoformat(),
        "message": "Reset link created. It is displayed only in this response.",
    }), 201


@admin_bp.route("/users/<int:user_id>/ml-profile", methods=["GET"])
@admin_required
def user_ml_profile(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    from .ml_service import get_user_ml_profile

    return jsonify(get_user_ml_profile(user.movielens_user_id))


@admin_bp.route("/users/<int:user_id>/recommendations", methods=["GET"])
@admin_required
def user_recommendations(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    from .ml_service import get_recommendations

    limit = _bounded_int(request.args.get("n"), 10, 1, 30)
    excluded = [] if user.include_watched else user.watched_movies
    return jsonify(get_recommendations(
        favorite_movie_tmdb_ids=user.favorite_movies,
        favorite_genres=user.favorite_genres,
        watched_tmdb_ids=excluded,
        movielens_user_id=user.movielens_user_id,
        n=limit,
    ))


def _validated_model_config(payload):
    base = get_active_model_config()
    base.update(payload or {})
    float_ranges = {
        "popularityWeight": (0.0, 5.0),
        "funkSvdWeight": (0.0, 5.0),
        "neuMfWeight": (0.0, 5.0),
        "genreBoost": (0.0, 2.0),
        "minimumSimilarity": (0.0, 1.0),
    }
    int_ranges = {
        "candidatePoolSize": (50, 2000),
        "similarUserCount": (1, 25),
    }
    result = {}
    for field, (minimum, maximum) in float_ranges.items():
        try:
            value = float(base[field])
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"{field} must be numeric") from exc
        if not minimum <= value <= maximum:
            raise ValueError(f"{field} must be between {minimum} and {maximum}")
        result[field] = value
    for field, (minimum, maximum) in int_ranges.items():
        try:
            value = int(base[field])
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"{field} must be an integer") from exc
        if not minimum <= value <= maximum:
            raise ValueError(f"{field} must be between {minimum} and {maximum}")
        result[field] = value
    if not any(result[field] > 0 for field in (
        "popularityWeight", "funkSvdWeight", "neuMfWeight"
    )):
        raise ValueError("At least one ranking weight must be greater than zero")
    return result


@admin_bp.route("/model-config", methods=["GET"])
@admin_required
def model_config():
    ensure_default_model_config()
    versions = ModelConfigVersion.query.order_by(
        ModelConfigVersion.created_at.desc()
    ).limit(20).all()
    return jsonify({
        "active": next((version.to_dict() for version in versions if version.is_active), None),
        "versions": [version.to_dict() for version in versions],
        "defaults": DEFAULT_MODEL_CONFIG,
    })


@admin_bp.route("/model-config/versions", methods=["POST"])
@admin_required
def create_model_config():
    data = request.get_json(silent=True) or {}
    try:
        config = _validated_model_config(data.get("config"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    activate = bool(data.get("activate", True))
    if activate:
        ModelConfigVersion.query.filter_by(is_active=True).update(
            {"is_active": False}
        )
    version = ModelConfigVersion(
        is_active=activate,
        reason=str(data.get("reason", "")).strip()[:500],
    )
    version.config = config
    db.session.add(version)
    db.session.flush()
    record_audit(
        g.admin_account.id,
        "model_config.created",
        details={"versionId": version.id, "activated": activate},
    )
    db.session.commit()
    return jsonify(version.to_dict()), 201


@admin_bp.route("/model-config/versions/<int:version_id>/activate", methods=["POST"])
@admin_required
def activate_model_config(version_id):
    version = db.session.get(ModelConfigVersion, version_id)
    if not version:
        return jsonify({"error": "Configuration version not found"}), 404
    ModelConfigVersion.query.filter_by(is_active=True).update({"is_active": False})
    version.is_active = True
    record_audit(
        g.admin_account.id,
        "model_config.activated",
        details={"versionId": version.id},
    )
    db.session.commit()
    return jsonify(version.to_dict())


@admin_bp.route("/audit-log", methods=["GET"])
@admin_required
def audit_log():
    limit = _bounded_int(request.args.get("limit"), 50, 1, 200)
    events = AdminActivityEvent.query.order_by(
        AdminActivityEvent.created_at.desc()
    ).limit(limit).all()
    user_ids = {event.target_user_id for event in events if event.target_user_id}
    admin_ids = {event.admin_id for event in events}
    names = {
        user.id: f"{user.first_name} {user.last_name}".strip()
        for user in User.query.filter(User.id.in_(user_ids)).all()
    } if user_ids else {}
    admin_names = {
        admin.id: admin.display_name
        for admin in AdminAccount.query.filter(AdminAccount.id.in_(admin_ids)).all()
    } if admin_ids else {}
    items = []
    for event in events:
        item = event.to_dict()
        item["adminName"] = admin_names.get(event.admin_id)
        item["targetName"] = names.get(event.target_user_id)
        items.append(item)
    return jsonify(items)
