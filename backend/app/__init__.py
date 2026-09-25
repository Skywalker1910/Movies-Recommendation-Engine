"""
Application factory — creates a fully configured Flask instance.

Blueprint layout:
  /auth   → auth.py         (register, login, /me)
  /user   → user_routes.py  (profile CRUD, watch history)
  /movies → movie_routes.py (search, details, trending, batch)
  /movies → recommendation_routes.py (/recommendations, /similar/:id)
  /admin  → admin_routes.py   (users, ML diagnostics, model controls, audit)
"""
import truststore

truststore.inject_into_ssl()

from flask import Flask, jsonify
from flask_cors import CORS
from .extensions import db, jwt, bcrypt


def create_app(env: str = "development") -> Flask:
    app = Flask(__name__)
    from .models import utc_now

    app.extensions["started_at"] = utc_now()

    # Load config
    from config import config as cfg_map
    app.config.from_object(cfg_map.get(env, cfg_map["default"]))

    # Initialise extensions
    CORS(app, origins=app.config.get("CORS_ORIGINS", ["http://localhost:3000"]))
    db.init_app(app)
    jwt.init_app(app)
    bcrypt.init_app(app)

    @jwt.token_in_blocklist_loader
    def token_is_revoked(_header, payload):
        from .admin_service import get_security_state
        from .models import User, UserTokenState

        try:
            user_id = int(payload.get("sub"))
        except (TypeError, ValueError):
            return True
        user = db.session.get(User, user_id)
        if not user:
            return True
        security = get_security_state(user)
        if security and (not security.is_active or security.password_reset_required):
            return True
        token_state = db.session.get(UserTokenState, user_id)
        if token_state:
            issued_at = payload.get("authIssuedAt")
            if issued_at is None or float(issued_at) < token_state.valid_after.timestamp():
                return True
        return False

    @jwt.revoked_token_loader
    def revoked_token(_header, _payload):
        return jsonify({"error": "This session is no longer valid"}), 403

    # Register blueprints
    from .auth import auth_bp
    from .user_routes import user_bp
    from .movie_routes import movie_bp
    from .recommendation_routes import rec_bp
    from .admin_routes import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(user_bp, url_prefix="/user")
    app.register_blueprint(movie_bp, url_prefix="/movies")
    app.register_blueprint(rec_bp, url_prefix="/movies")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    from .admin_cli import register_admin_commands

    register_admin_commands(app)

    # Health / readiness probe (used by AWS ALB / Azure App Service)
    @app.route("/health")
    def health():
        from .movie_service import movie_service

        return jsonify({
            "status": "ok",
            "env": env,
            "integrations": {
                "tmdb": "configured" if movie_service.tmdb_enabled else "disabled"
            },
        })

    # Global error handlers
    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(_e):
        return jsonify({"error": "Internal server error"}), 500

    # Create DB tables on first run
    with app.app_context():
        db.create_all()
        from .admin_service import ensure_default_model_config

        ensure_default_model_config()

    return app

