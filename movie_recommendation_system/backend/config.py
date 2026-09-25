"""
Multi-environment configuration.

Tech-stack rationale:
  - Flask: lightweight, battle-tested, great ML-library interop (scipy, numpy)
  - Flask-JWT-Extended: stateless auth → horizontal scaling on EC2 / App Service
  - SQLAlchemy: ORM abstraction over SQLite (dev) → PostgreSQL (prod) seamlessly
  - Flask-Bcrypt: industry-standard password hashing (bcrypt cost factor ≥ 12)
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))


class Config:
    """Shared base settings."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-CHANGE-IN-PROD")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT — stateless: no server-side session → scales to 10K+ users easily
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-dev-secret-CHANGE-IN-PROD")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.environ.get("JWT_EXPIRES_HOURS", 24))
    )

    # CORS — comma-separated allowed origins
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

    # Administration uses an independent account store and signing key.
    ADMIN_JWT_SECRET_KEY = os.environ.get(
        "ADMIN_JWT_SECRET_KEY", "admin-jwt-dev-secret-CHANGE-IN-PROD"
    )
    ADMIN_SESSION_HOURS = int(os.environ.get("ADMIN_SESSION_HOURS", 4))
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    PASSWORD_RESET_MINUTES = int(os.environ.get("PASSWORD_RESET_MINUTES", 30))

    # Optional: override ML model directory for cloud deployments (e.g., S3 mount)
    MODELS_DIR = os.environ.get("MODELS_DIR", None)


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///movie_db.sqlite"
    )


class ProductionConfig(Config):
    DEBUG = False
    # On AWS RDS / Azure SQL: export DATABASE_URL=postgresql://user:pass@host/db
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///movie_db.sqlite")
    JWT_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
