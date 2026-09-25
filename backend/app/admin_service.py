"""Administration security and serving-configuration helpers."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from functools import wraps

import jwt as pyjwt
from flask import current_app, g, jsonify, request

from .extensions import db
from .models import (
    AdminAccount,
    AdminActivityEvent,
    ModelConfigVersion,
    User,
    UserSecurityState,
    UserTokenState,
    utc_now,
)


DEFAULT_MODEL_CONFIG = {
    "popularityWeight": 1.0,
    "funkSvdWeight": 0.35,
    "neuMfWeight": 0.15,
    "genreBoost": 0.25,
    "candidatePoolSize": 400,
    "similarUserCount": 5,
    "minimumSimilarity": 0.0,
}


def get_security_state(user: User, create: bool = False):
    if not user or not user.id:
        return None
    state = db.session.get(UserSecurityState, user.id)
    if state is None and create:
        state = UserSecurityState(user_id=user.id)
        db.session.add(state)
    return state


def revoke_user_tokens(user: User, when=None) -> None:
    state = db.session.get(UserTokenState, user.id)
    if state is None:
        state = UserTokenState(user_id=user.id)
        db.session.add(state)
    state.valid_after = when or utc_now()


def create_admin_access_token(admin: AdminAccount) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(admin.id),
        "typ": "admin",
        "iat": now,
        "adminIssuedAt": now.timestamp(),
        "exp": now + timedelta(
            hours=current_app.config.get("ADMIN_SESSION_HOURS", 4)
        ),
        "jti": secrets.token_urlsafe(16),
    }
    return pyjwt.encode(
        payload,
        current_app.config["ADMIN_JWT_SECRET_KEY"],
        algorithm="HS256",
    )


def revoke_admin_tokens(admin: AdminAccount, when=None) -> None:
    admin.token_valid_after = when or utc_now()


def admin_required(view):
    """Accept only independently signed administrator bearer tokens."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return jsonify({"error": "Administrator authentication required"}), 401
        try:
            payload = pyjwt.decode(
                token,
                current_app.config["ADMIN_JWT_SECRET_KEY"],
                algorithms=["HS256"],
                options={
                    "require": ["exp", "iat", "adminIssuedAt", "sub", "typ"]
                },
            )
            if payload.get("typ") != "admin":
                raise pyjwt.InvalidTokenError("Incorrect token type")
            admin_id = int(payload["sub"])
        except (pyjwt.PyJWTError, TypeError, ValueError):
            return jsonify({"error": "Invalid or expired administrator session"}), 401

        admin = db.session.get(AdminAccount, admin_id)
        if not admin or not admin.is_active:
            return jsonify({"error": "Administrator account is inactive"}), 403
        if admin.password_reset_required:
            return jsonify({"error": "Administrator password setup is required"}), 403
        issued_at = datetime.fromtimestamp(
            float(payload["adminIssuedAt"]), UTC
        ).replace(tzinfo=None)
        if issued_at < admin.token_valid_after:
            return jsonify({"error": "Administrator session has been revoked"}), 401

        g.admin_account = admin
        g.admin_claims = payload
        return view(*args, **kwargs)

    return wrapped


def ensure_default_model_config() -> None:
    if ModelConfigVersion.query.filter_by(is_active=True).first():
        return
    version = ModelConfigVersion(is_active=True, reason="Initial defaults")
    version.config = DEFAULT_MODEL_CONFIG
    db.session.add(version)
    db.session.commit()


def get_active_model_config() -> dict:
    version = ModelConfigVersion.query.filter_by(is_active=True).first()
    config = dict(DEFAULT_MODEL_CONFIG)
    if version:
        config.update(version.config)
    return config


def record_audit(
    admin_id: int,
    action: str,
    target_user_id: int | None = None,
    details: dict | None = None,
) -> None:
    event = AdminActivityEvent(
        admin_id=admin_id,
        target_user_id=target_user_id,
        action=action,
    )
    event.details = details or {}
    db.session.add(event)
