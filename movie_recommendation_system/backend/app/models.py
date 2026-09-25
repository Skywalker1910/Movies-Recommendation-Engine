"""
SQLAlchemy ORM models.

User schema stores:
  - Auth credentials (hashed password)
  - Onboarding data (genres + movies)
  - Watch history
  - Preferences
  - Optional MovieLens user ID mapping (for users who are in the training data)

JSON columns use TEXT for SQLite/PostgreSQL portability.
On PostgreSQL in production, consider migrating to JSONB for indexing.
"""
import json
from datetime import UTC, datetime
from .extensions import db


def utc_now():
    """Return a naive UTC timestamp compatible with existing database columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    id           = db.Column(db.Integer, primary_key=True)
    first_name   = db.Column(db.String(100), nullable=False)
    last_name    = db.Column(db.String(100), nullable=False)
    email        = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # JSON-encoded lists (TEXT works in both SQLite dev + PostgreSQL prod)
    _favorite_genres = db.Column("favorite_genres", db.Text, default="[]")
    _favorite_movies = db.Column("favorite_movies", db.Text, default="[]")  # TMDB ids
    _watched_movies  = db.Column("watched_movies",  db.Text, default="[]")  # TMDB ids

    # Preferences set during onboarding
    include_watched    = db.Column(db.Boolean, default=False)
    watching_frequency = db.Column(db.String(50), default="weekly")

    # Optional mapping to a MovieLens userId in the training dataset.
    # Set this if you want to personalise recs using the trained hybrid model.
    movielens_user_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # ── JSON column helpers ─────────────────────────────────────────────────

    @property
    def favorite_genres(self):
        return json.loads(self._favorite_genres or "[]")

    @favorite_genres.setter
    def favorite_genres(self, value):
        self._favorite_genres = json.dumps(value)

    @property
    def favorite_movies(self):
        return json.loads(self._favorite_movies or "[]")

    @favorite_movies.setter
    def favorite_movies(self, value):
        self._favorite_movies = json.dumps(value)

    @property
    def watched_movies(self):
        return json.loads(self._watched_movies or "[]")

    @watched_movies.setter
    def watched_movies(self, value):
        self._watched_movies = json.dumps(value)

    # ── Serialisation ───────────────────────────────────────────────────────

    def to_dict(self):
        from .admin_service import get_security_state

        security = get_security_state(self)
        return {
            "id": self.id,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "email": self.email,
            "favoriteGenres": self.favorite_genres,
            "favoriteMovies": self.favorite_movies,
            "watchedMovies": self.watched_movies,
            "preferences": {
                "includeWatched": self.include_watched,
                "watchingFrequency": self.watching_frequency,
            },
            "movielensUserId": self.movielens_user_id,
            "isActive": security.is_active if security else True,
            "passwordResetRequired": (
                security.password_reset_required if security else False
            ),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class UserRole(db.Model):
    """Legacy role records retained only for database compatibility."""

    __tablename__ = "user_roles"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    role = db.Column(db.String(30), primary_key=True)
    granted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)


class UserSecurityState(db.Model):
    __tablename__ = "user_security_states"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    password_reset_required = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class UserTokenState(db.Model):
    __tablename__ = "user_token_states"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    valid_after = db.Column(db.DateTime, default=utc_now, nullable=False)


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)


class AdminAccount(db.Model):
    """Administrator identity stored independently from application users."""

    __tablename__ = "admin_accounts"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    password_reset_required = db.Column(db.Boolean, default=False, nullable=False)
    token_valid_after = db.Column(db.DateTime, default=utc_now, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "displayName": self.display_name,
            "isActive": self.is_active,
            "passwordResetRequired": self.password_reset_required,
            "lastLoginAt": (
                self.last_login_at.isoformat() if self.last_login_at else None
            ),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class AdminPasswordResetToken(db.Model):
    __tablename__ = "admin_password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(
        db.Integer, db.ForeignKey("admin_accounts.id"), nullable=False, index=True
    )
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)


class ModelConfigVersion(db.Model):
    __tablename__ = "model_config_versions"

    id = db.Column(db.Integer, primary_key=True)
    config_json = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False, index=True)
    reason = db.Column(db.String(500), default="")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    @property
    def config(self):
        return json.loads(self.config_json or "{}")

    @config.setter
    def config(self, value):
        self.config_json = json.dumps(value, sort_keys=True)

    def to_dict(self):
        return {
            "id": self.id,
            "config": self.config,
            "isActive": self.is_active,
            "reason": self.reason or "",
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class AdminAuditEvent(db.Model):
    """Legacy user-linked audit records retained for database compatibility."""

    __tablename__ = "admin_audit_events"

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    details_json = db.Column(db.Text, default="{}", nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    @property
    def details(self):
        return json.loads(self.details_json or "{}")

    @details.setter
    def details(self, value):
        self.details_json = json.dumps(value, sort_keys=True)

    def to_dict(self):
        return {
            "id": self.id,
            "adminUserId": self.admin_user_id,
            "targetUserId": self.target_user_id,
            "action": self.action,
            "details": self.details,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class AdminActivityEvent(db.Model):
    """Audit records owned by isolated administrator identities."""

    __tablename__ = "admin_activity_events"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(
        db.Integer, db.ForeignKey("admin_accounts.id"), nullable=False, index=True
    )
    target_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    action = db.Column(db.String(100), nullable=False, index=True)
    details_json = db.Column(db.Text, default="{}", nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    @property
    def details(self):
        return json.loads(self.details_json or "{}")

    @details.setter
    def details(self, value):
        self.details_json = json.dumps(value, sort_keys=True)

    def to_dict(self):
        return {
            "id": self.id,
            "adminId": self.admin_id,
            "targetUserId": self.target_user_id,
            "action": self.action,
            "details": self.details,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
