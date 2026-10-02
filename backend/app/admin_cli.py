"""Interactive provisioning commands for isolated administrator accounts."""

import click
import random

from .admin_service import record_audit, revoke_admin_tokens
from .extensions import bcrypt, db
from .models import AdminAccount, User


def register_admin_commands(app):
    @app.cli.command("create-admin")
    @click.option("--email", prompt="Administrator email")
    @click.option("--name", prompt="Display name")
    @click.password_option(confirmation_prompt=True)
    def create_admin(email, name, password):
        """Create or securely re-provision an administrator account."""
        email = email.strip().lower()
        name = name.strip()
        if "@" not in email or not name:
            raise click.ClickException("A valid email and display name are required")
        if len(password) < 12:
            raise click.ClickException("Administrator passwords require 12 characters")

        admin = AdminAccount.query.filter_by(email=email).first()
        action = "admin.reprovisioned" if admin else "admin.provisioned"
        if admin is None:
            admin = AdminAccount(email=email, display_name=name, password_hash="")
            db.session.add(admin)
            db.session.flush()
        admin.display_name = name
        admin.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        admin.is_active = True
        admin.password_reset_required = False
        revoke_admin_tokens(admin)
        record_audit(admin.id, action)
        db.session.commit()
        click.echo(f"Administrator ready: {admin.email}")

    @app.cli.command("seed-synthetic-users")
    @click.option("--count", default=20, help="Number of synthetic users to create")
    def seed_synthetic_users(count):
        """Create synthetic users mapped to MovieLens user IDs for better CF.

        These users have realistic genre preferences and favorite movies
        drawn from the MovieLens dataset, enabling collaborative filtering
        to work with production accounts.
        """
        import pathlib, pickle, pandas as pd

        _WORKSPACE = pathlib.Path(__file__).resolve().parents[2]
        models_dir = pathlib.Path(app.config.get("MODELS_DIR", "")) or _WORKSPACE / "models"
        data_dir = _WORKSPACE / "data" / "movielens"
        if not data_dir.exists():
            data_dir = pathlib.Path("/workspace/data/movielens")

        try:
            with open(models_dir / "user_id_map.pkl", "rb") as f:
                u_map = pickle.load(f)
            user2idx = u_map["user2idx"]
        except Exception as e:
            raise click.ClickException(f"Cannot load user_id_map.pkl: {e}")

        try:
            links = pd.read_csv(data_dir / "links.csv", usecols=["movieId", "tmdbId"])
            links = links.dropna(subset=["tmdbId"])
            links["tmdbId"] = links["tmdbId"].astype(int)
            movie2tmdb = links.set_index("movieId")["tmdbId"].to_dict()
        except Exception as e:
            raise click.ClickException(f"Cannot load links.csv: {e}")

        try:
            import scipy.sparse as sp
            ui_matrix = sp.load_npz(models_dir / "user_item_matrix.npz")
        except Exception as e:
            raise click.ClickException(f"Cannot load user_item_matrix.npz: {e}")

        with open(models_dir / "movie_id_map.pkl", "rb") as f:
            m_map = pickle.load(f)
        idx2movie = m_map["idx2movie"]

        genre_pools = {
            "Action Fan":     (["Action", "Thriller", "Adventure"], "en"),
            "Comedy Lover":   (["Comedy", "Romance", "Family"], "en"),
            "Sci-Fi Geek":    (["Science Fiction", "Fantasy", "Adventure"], "en"),
            "Drama Buff":     (["Drama", "History", "War"], "en"),
            "Horror Fan":     (["Horror", "Thriller", "Mystery"], "en"),
            "Animation Fan":  (["Animation", "Family", "Comedy"], "en"),
            "Documentary":    (["Documentary", "History", "Drama"], "en"),
            "Bollywood Fan":  (["Drama", "Romance", "Music"], "hi"),
            "K-Drama Fan":    (["Drama", "Romance", "Comedy"], "ko"),
            "Anime Fan":      (["Animation", "Action", "Fantasy"], "ja"),
        }

        all_ml_users = list(user2idx.keys())
        rng = random.Random(42)
        rng.shuffle(all_ml_users)

        created = 0
        pool_names = list(genre_pools.keys())

        for i in range(min(count, len(all_ml_users))):
            ml_uid = all_ml_users[i]
            pool_name = pool_names[i % len(pool_names)]
            genres, lang = genre_pools[pool_name]

            if User.query.filter_by(movielens_user_id=ml_uid).first():
                continue

            email = f"synthetic.user.{ml_uid}@movielens.local"
            if User.query.filter_by(email=email).first():
                continue

            u_idx = user2idx[ml_uid]
            row = ui_matrix[u_idx]
            if row.nnz == 0:
                continue

            rated_items = row.nonzero()[1]
            ratings = row.data
            top_indices = rated_items[ratings.argsort()[::-1]][:10]

            fav_tmdb = []
            for item_idx in top_indices:
                mid = idx2movie.get(item_idx)
                if mid and mid in movie2tmdb:
                    fav_tmdb.append(movie2tmdb[mid])
                if len(fav_tmdb) >= 5:
                    break

            user = User(
                first_name=pool_name.split()[0],
                last_name=f"User{ml_uid}",
                email=email,
                password_hash=bcrypt.generate_password_hash(
                    f"synthetic-{ml_uid}-{rng.randint(1000,9999)}"
                ).decode("utf-8"),
                movielens_user_id=ml_uid,
            )
            user.favorite_genres = genres
            user.favorite_movies = fav_tmdb
            user.preferred_languages = [lang]

            db.session.add(user)
            created += 1

        db.session.commit()
        click.echo(f"Created {created} synthetic users (mapped to MovieLens IDs)")
