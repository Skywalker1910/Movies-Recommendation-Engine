"""
ML Recommendation Service — wraps the hybrid model from NB09.

Loading strategy
----------------
Artefacts are loaded lazily on first request and cached in module state.
This avoids a 30-60 s startup cost and allows the web server to respond to
/health probes immediately after launch.

Fallback hierarchy
------------------
1. Full hybrid (FunkSVD + NeuMF + TF-IDF + popularity)  ← preferred
2. FunkSVD + TF-IDF + popularity                         ← if NeuMF unavailable
3. TF-IDF content + popularity                           ← if no ML models at all
4. movie_service.get_trending()                          ← last resort

Recommendation sections
-----------------------
  section="recommended"  → cold-start blend: popularity + genre boost
  section="favorites"    → content-based seeded by favourite movies
  section="trending"     → pure popularity sort (no ML)
"""
import logging
import pathlib
import pickle
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import scipy.sparse as sp

from .movie_service import movie_service

logger = logging.getLogger(__name__)

# ── Path resolution ───────────────────────────────────────────────────────────
# Layout:  <workspace>/movie_recommendation_system/backend/app/ml_service.py
#           parents[3] = <workspace root>
_WORKSPACE = pathlib.Path(__file__).resolve().parents[3]

# Allow env-var override for containerised deployments (e.g. MODELS_DIR=/workspace/models)
import os as _os
MODELS_DIR    = pathlib.Path(_os.environ["MODELS_DIR"]) if _os.environ.get("MODELS_DIR") else _WORKSPACE / "models"
PROCESSED_DIR = pathlib.Path(_os.environ.get("PROCESSED_DIR", "")) if _os.environ.get("PROCESSED_DIR") else _WORKSPACE / "data_science" / "processed"

# Resolve data dir: prefer local, fall back to project-level data/movielens
_LOCAL_DATA   = pathlib.Path(__file__).resolve().parent.parent / "data" / "movies-dataset"
_PROJECT_DATA = _WORKSPACE / "data" / "movielens"
_DOCKER_DATA  = pathlib.Path("/workspace/data/movielens")
if (_LOCAL_DATA / "links.csv").exists():
    DATA_DIR = _LOCAL_DATA
elif _PROJECT_DATA.exists():
    DATA_DIR = _PROJECT_DATA
elif _DOCKER_DATA.exists():
    DATA_DIR = _DOCKER_DATA
else:
    DATA_DIR = _LOCAL_DATA


# ── Pickle stub — must match NB07 class definition ───────────────────────────

class _FunkSVD:
    def __init__(self, n_factors=50, n_epochs=20, lr=0.005, reg=0.02, seed=42):
        self.k, self.epochs, self.lr, self.reg, self.seed = (
            n_factors, n_epochs, lr, reg, seed
        )

    def predict(self, u: int, i: int) -> float:
        p = float(
            self.global_mean + self.bu[u] + self.bi[i] + np.dot(self.P[u], self.Q[i])
        )
        return float(np.clip(p, 0.5, 5.0))


# Trick: register under the name used in the pickle file
import sys as _sys
_mod = type(_sys)("__main__")
_mod.FunkSVD = _FunkSVD
_sys.modules.setdefault("__main__", _mod)
_sys.modules["__main__"].FunkSVD = _FunkSVD


# ── Lazy state ────────────────────────────────────────────────────────────────

_cache = {"loaded": False, "art": None}


def _load():
    if _cache["loaded"]:
        return _cache["art"]

    art = {}
    try:
        logger.info("Loading ML artefacts from %s", MODELS_DIR)

        # ── User-item matrix + mappings (NB06) ───────────────────────────────
        art["user_item"]  = sp.load_npz(MODELS_DIR / "user_item_matrix.npz")
        art["global_mean"] = float(art["user_item"].data.mean())

        with open(MODELS_DIR / "user_id_map.pkl", "rb") as f:
            _u = pickle.load(f)
        with open(MODELS_DIR / "movie_id_map.pkl", "rb") as f:
            _m = pickle.load(f)
        art["user_id_map"]  = _u["user2idx"]
        art["idx_to_user"] = {index: user for user, index in _u["user2idx"].items()}
        art["movie_id_map"] = _m["movie2idx"]
        art["idx_to_movie"] = _m["idx2movie"]

        # ── FunkSVD (NB07) ───────────────────────────────────────────────────
        with open(MODELS_DIR / "funksvd_model.pkl", "rb") as f:
            art["funk"] = pickle.load(f)

        # ── TF-IDF (NB05) ────────────────────────────────────────────────────
        art["tfidf"] = sp.load_npz(MODELS_DIR / "tfidf_matrix.npz")
        with open(MODELS_DIR / "title_to_idx.pkl", "rb") as f:
            art["title_to_idx"] = pickle.load(f)
        # Build reverse mapping: tfidf-row-index → title
        art["idx_to_title"] = {
            (v.iloc[0] if hasattr(v, "iloc") else v): k
            for k, v in art["title_to_idx"].items()
        }

        # ── MovieLens links + master popularity table ─────────────────────────
        links = pd.read_csv(DATA_DIR / "links.csv", usecols=["movieId", "tmdbId"])
        links = links.dropna(subset=["tmdbId"])
        links["tmdbId"]  = links["tmdbId"].astype(int)
        links["movieId"] = links["movieId"].astype(int)
        art["movie2tmdb"] = links.set_index("movieId")["tmdbId"].to_dict()
        art["tmdb2movie"] = links.set_index("tmdbId")["movieId"].to_dict()
        art["links_df"]   = links.rename(columns={"tmdbId": "tmdb_id"})

        master = pd.read_parquet(
            PROCESSED_DIR / "master_movies.parquet",
            columns=["tmdb_id", "title", "bayesian_score"],
        )
        art["master"] = master
        art["bayesian"] = master.set_index("tmdb_id")["bayesian_score"].to_dict()

        # ── NeuMF (NB08) — optional ──────────────────────────────────────────
        try:
            import torch
            import torch.nn as nn

            with open(MODELS_DIR / "ncf_config.pkl",    "rb") as f: ncf_cfg   = pickle.load(f)
            art["ncf_config"] = ncf_cfg
            with open(MODELS_DIR / "ncf_user_enc.pkl",  "rb") as f: art["user_enc"]  = pickle.load(f)
            with open(MODELS_DIR / "ncf_movie_enc.pkl", "rb") as f: art["movie_enc"] = pickle.load(f)

            DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

            class _NeuMF(nn.Module):
                def __init__(self, n_users, n_movies, gmf_dim=32, mlp_dim=64,
                             mlp_layers=(128, 64, 32), dropout=0.2):
                    super().__init__()
                    # Attribute names must match the keys written by notebook 08.
                    self.gmf_user_emb = nn.Embedding(n_users, gmf_dim)
                    self.gmf_item_emb = nn.Embedding(n_movies, gmf_dim)
                    self.mlp_user_emb = nn.Embedding(n_users, mlp_dim)
                    self.mlp_item_emb = nn.Embedding(n_movies, mlp_dim)
                    mlp_in, layers = mlp_dim * 2, []
                    for out in mlp_layers:
                        layers += [nn.Linear(mlp_in, out), nn.ReLU(), nn.Dropout(dropout)]
                        mlp_in = out
                    self.mlp_tower = nn.Sequential(*layers)
                    self.output = nn.Linear(gmf_dim + list(mlp_layers)[-1], 1)

                def forward(self, u, i):
                    g = self.gmf_user_emb(u) * self.gmf_item_emb(i)
                    m = self.mlp_tower(torch.cat([
                        self.mlp_user_emb(u), self.mlp_item_emb(i)
                    ], 1))
                    return 0.5 + 4.5 * torch.sigmoid(
                        self.output(torch.cat([g, m], 1))
                    ).squeeze(1)

            ncf = _NeuMF(**ncf_cfg).to(DEVICE)
            ncf.load_state_dict(
                torch.load(MODELS_DIR / "ncf_model_weights.pt", map_location=DEVICE)
            )
            ncf.eval()
            art["ncf"], art["ncf_device"], art["ncf_ok"] = ncf, DEVICE, True
            logger.info("NeuMF loaded on %s", DEVICE)
        except Exception as e:
            art["ncf_ok"] = False
            art["user_enc"] = art["movie_enc"] = {}
            logger.warning("NeuMF not available: %s", e)

        _cache["art"] = art
        logger.info("ML artefacts ready (global_mean=%.4f)", art["global_mean"])

    except Exception as exc:
        logger.error("ML artefact load failed: %s", exc)
        _cache["art"] = None

    _cache["loaded"] = True
    return _cache["art"]


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _minmax(scores: dict) -> dict:
    if not scores:
        return {}
    vals = np.array(list(scores.values()), dtype=np.float32)
    lo, hi = vals.min(), vals.max()
    if hi == lo:
        return {k: 0.5 for k in scores}
    return {k: float((v - lo) / (hi - lo)) for k, v in scores.items()}


def _score_funk(user_id, mids, art) -> dict:
    if user_id not in art["user_id_map"]:
        return {}
    row    = art["user_id_map"][user_id]
    scores = {
        m: art["funk"].predict(row, art["movie_id_map"][m])
        if m in art["movie_id_map"] else art["global_mean"]
        for m in mids
    }
    return _minmax(scores)


def _score_ncf(user_id, mids, art) -> dict:
    if not art.get("ncf_ok") or user_id not in art.get("user_enc", {}):
        return {}
    import torch
    u_idx = art["user_enc"][user_id]
    known = [m for m in mids if m in art["movie_enc"]]
    scores = {m: art["global_mean"] for m in mids if m not in art["movie_enc"]}
    if known:
        with torch.no_grad():
            u_t = torch.full((len(known),), u_idx, dtype=torch.long, device=art["ncf_device"])
            m_t = torch.tensor([art["movie_enc"][m] for m in known], dtype=torch.long, device=art["ncf_device"])
            for m, p in zip(known, art["ncf"](u_t, m_t).cpu().tolist()):
                scores[m] = p
    return _minmax(scores)


def _score_pop(mids, art) -> dict:
    scores = {
        m: art["bayesian"].get(art["movie2tmdb"].get(m, -1), 0.0)
        for m in mids
    }
    return _minmax(scores)


def _candidate_pool(art, seen_tmdb: set, n: int = 300) -> list:
    """Top-N unseen MovieLens movieIds sorted by bayesian_score."""
    cands = (
        art["master"]
        .merge(art["links_df"][["tmdb_id", "movieId"]], on="tmdb_id", how="inner")
        .sort_values("bayesian_score", ascending=False)
    )
    cands = cands[~cands["tmdb_id"].isin(seen_tmdb)]
    return cands["movieId"].head(n).tolist()


def _serving_config() -> dict:
    from .admin_service import DEFAULT_MODEL_CONFIG, get_active_model_config

    try:
        return get_active_model_config()
    except RuntimeError:
        return dict(DEFAULT_MODEL_CONFIG)


def get_model_status(load_artifacts: bool = False) -> dict:
    """Return model availability without forcing a costly load unless requested."""
    art = _load() if load_artifacts else _cache.get("art")
    if art is None:
        return {
            "artifactsLoaded": bool(_cache.get("loaded")),
            "artifactsAvailable": False if _cache.get("loaded") else None,
            "funkSvdAvailable": False,
            "neuMfAvailable": False,
            "contentModelAvailable": False,
        }
    return {
        "artifactsLoaded": True,
        "artifactsAvailable": True,
        "funkSvdAvailable": "funk" in art,
        "neuMfAvailable": bool(art.get("ncf_ok")),
        "contentModelAvailable": "tfidf" in art,
        "trainingUsers": len(art.get("user_id_map", {})),
        "trainingMovies": len(art.get("movie_id_map", {})),
        "globalMeanRating": round(float(art.get("global_mean", 0)), 4),
    }


def get_model_inventory(load_artifacts: bool = False) -> dict:
    """Describe every component used by the live recommendation pipeline."""
    status = get_model_status(load_artifacts=load_artifacts)
    art = _cache.get("art") or {}
    config = _serving_config()

    def artifact(path):
        present = path.exists()
        details = {"name": path.name, "present": present}
        if present:
            stat = path.stat()
            details.update({
                "sizeBytes": stat.st_size,
                "modifiedAt": datetime.fromtimestamp(
                    stat.st_mtime, UTC
                ).isoformat(),
            })
        return details

    funk = art.get("funk")
    models = [
        {
            "key": "popularity",
            "name": "Bayesian Popularity",
            "category": "baseline",
            "purpose": "Candidate ranking and cold-start fallback",
            "available": (PROCESSED_DIR / "master_movies.parquet").exists(),
            "loaded": bool(art),
            "configuration": {"weight": config["popularityWeight"]},
            "artifacts": [artifact(PROCESSED_DIR / "master_movies.parquet")],
        },
        {
            "key": "funk_svd",
            "name": "FunkSVD",
            "category": "collaborative filtering",
            "purpose": "Personalized rating prediction",
            "available": status["funkSvdAvailable"] if load_artifacts else (
                MODELS_DIR / "funksvd_model.pkl"
            ).exists(),
            "loaded": bool(status["funkSvdAvailable"]),
            "configuration": {
                "weight": config["funkSvdWeight"],
                "factors": getattr(funk, "k", None),
                "epochs": getattr(funk, "epochs", None),
                "learningRate": getattr(funk, "lr", None),
                "regularization": getattr(funk, "reg", None),
            },
            "artifacts": [
                artifact(MODELS_DIR / "funksvd_model.pkl"),
                artifact(MODELS_DIR / "user_item_matrix.npz"),
                artifact(MODELS_DIR / "user_id_map.pkl"),
                artifact(MODELS_DIR / "movie_id_map.pkl"),
            ],
        },
        {
            "key": "neumf",
            "name": "NeuMF",
            "category": "neural collaborative filtering",
            "purpose": "Non-linear user-item interaction scoring",
            "available": status["neuMfAvailable"] if load_artifacts else all(
                (MODELS_DIR / name).exists() for name in (
                    "ncf_model_weights.pt", "ncf_config.pkl",
                    "ncf_user_enc.pkl", "ncf_movie_enc.pkl",
                )
            ),
            "loaded": bool(status["neuMfAvailable"]),
            "configuration": {
                "weight": config["neuMfWeight"],
                **(art.get("ncf_config") or {}),
            },
            "artifacts": [
                artifact(MODELS_DIR / "ncf_model_weights.pt"),
                artifact(MODELS_DIR / "ncf_config.pkl"),
                artifact(MODELS_DIR / "ncf_user_enc.pkl"),
                artifact(MODELS_DIR / "ncf_movie_enc.pkl"),
            ],
        },
        {
            "key": "tfidf",
            "name": "TF-IDF Content Similarity",
            "category": "content based",
            "purpose": "Recommendations related to favorite titles",
            "available": status["contentModelAvailable"] if load_artifacts else all(
                (MODELS_DIR / name).exists()
                for name in ("tfidf_matrix.npz", "title_to_idx.pkl")
            ),
            "loaded": bool(status["contentModelAvailable"]),
            "configuration": {"similarity": "cosine"},
            "artifacts": [
                artifact(MODELS_DIR / "tfidf_matrix.npz"),
                artifact(MODELS_DIR / "title_to_idx.pkl"),
            ],
        },
        {
            "key": "hybrid_ranker",
            "name": "Hybrid Ranker",
            "category": "ensemble",
            "purpose": "Blends available scores and genre preference signals",
            "available": True,
            "loaded": True,
            "configuration": config,
            "artifacts": [],
        },
        {
            "key": "user_similarity",
            "name": "User Similarity Diagnostics",
            "category": "diagnostic",
            "purpose": "Nearest-user inspection for mapped MovieLens accounts",
            "available": (MODELS_DIR / "user_item_matrix.npz").exists(),
            "loaded": bool(art),
            "configuration": {
                "method": "cosine",
                "neighbors": config["similarUserCount"],
                "minimumSimilarity": config["minimumSimilarity"],
            },
            "artifacts": [artifact(MODELS_DIR / "user_item_matrix.npz")],
        },
    ]
    return {
        "status": status,
        "activeConfig": config,
        "models": models,
        "pipeline": [
            "candidate_pool", "component_scoring", "score_normalization",
            "weighted_blend", "genre_boost", "rank_and_enrich",
        ],
    }


def get_user_ml_profile(movielens_user_id: int | None) -> dict:
    """Calculate read-only collaborative-filtering diagnostics for one user."""
    if movielens_user_id in (None, ""):
        return {
            "mapped": False,
            "movieLensUserId": None,
            "message": "No MovieLens user is mapped to this account",
            "model": get_model_status(load_artifacts=False),
            "similarUsers": [],
        }

    status = get_model_status(load_artifacts=True)
    if not status.get("artifactsAvailable"):
        return {
            "mapped": False,
            "movieLensUserId": movielens_user_id,
            "message": "Model artifacts are unavailable",
            "model": status,
            "similarUsers": [],
        }
    try:
        movielens_user_id = int(movielens_user_id)
    except (TypeError, ValueError):
        movielens_user_id = -1
    art = _cache["art"]
    row_index = art["user_id_map"].get(movielens_user_id)
    if row_index is None:
        return {
            "mapped": False,
            "movieLensUserId": movielens_user_id,
            "message": "The mapped MovieLens user is not present in the training artifacts",
            "model": status,
            "similarUsers": [],
        }

    matrix = art["user_item"].tocsr()
    user_vector = matrix.getrow(row_index)
    user_norm = float(np.sqrt(user_vector.multiply(user_vector).sum()))
    if art.get("user_norms") is None:
        art["user_norms"] = np.sqrt(matrix.multiply(matrix).sum(axis=1)).A1
    norms = art["user_norms"]
    similarities = np.zeros(matrix.shape[0], dtype=np.float32)
    if user_norm > 0:
        products = matrix.dot(user_vector.T).toarray().ravel()
        denominator = norms * user_norm
        np.divide(products, denominator, out=similarities, where=denominator > 0)
    similarities[row_index] = -1

    config = _serving_config()
    minimum = float(config["minimumSimilarity"])
    candidate_indices = np.where(
        (similarities >= minimum) & (similarities > 0)
    )[0]
    count = int(config["similarUserCount"])
    ordered = candidate_indices[np.argsort(similarities[candidate_indices])[-count:]][::-1]
    similar_users = [
        {
            "movieLensUserId": int(art["idx_to_user"].get(int(index), -1)),
            "similarity": round(float(similarities[index]), 4),
        }
        for index in ordered
    ]
    return {
        "mapped": True,
        "movieLensUserId": movielens_user_id,
        "ratingCount": int(user_vector.nnz),
        "meanRating": round(float(user_vector.data.mean()), 3) if user_vector.nnz else None,
        "catalogCoverage": round(float(user_vector.nnz / matrix.shape[1]), 6),
        "similarityMethod": "cosine",
        "similarUsers": similar_users,
        "model": status,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def get_recommendations(
    favorite_movie_tmdb_ids: list = None,
    favorite_genres: list = None,
    watched_tmdb_ids: list = None,
    movielens_user_id: int | None = None,
    n: int = 20,
    section: str = "recommended",
) -> list:
    """
    Return n movie dicts enriched with recommendationScore and reason.

    Parameters
    ----------
    favorite_movie_tmdb_ids : user's saved TMDB movie IDs
    favorite_genres         : user's genre preferences
    watched_tmdb_ids        : TMDB IDs to exclude (already watched)
    n                       : number of results
    section                 : "recommended" | "favorites" | "trending"
    """
    if section == "trending":
        return movie_service.get_trending(limit=n)

    if section == "favorites" and favorite_movie_tmdb_ids:
        result = _recs_by_favorites(favorite_movie_tmdb_ids, watched_tmdb_ids or [], n)
        return result or _cold_start(
            favorite_movie_tmdb_ids,
            favorite_genres or [],
            watched_tmdb_ids or [],
            n,
            movielens_user_id,
        )

    return _cold_start(
        favorite_movie_tmdb_ids or [],
        favorite_genres or [],
        watched_tmdb_ids or [],
        n,
        movielens_user_id,
    )


def _cold_start(fav_tmdb, fav_genres, watched_tmdb, n, movielens_user_id=None) -> list:
    """Blend available personalized scores with popularity and genre signals."""
    art = _load()
    if art is None:
        return movie_service.get_trending(limit=n)

    config = _serving_config()
    seen   = set(watched_tmdb)
    cands  = _candidate_pool(art, seen, n=int(config["candidatePoolSize"]))
    if not cands:
        return movie_service.get_trending(limit=n)

    s_pop  = _score_pop(cands, art)
    s_funk = _score_funk(movielens_user_id, cands, art) if movielens_user_id else {}
    s_ncf = _score_ncf(movielens_user_id, cands, art) if movielens_user_id else {}

    boost = float(config["genreBoost"])
    genre_boost = {}
    if fav_genres:
        for mid in cands:
            tmdb = art["movie2tmdb"].get(mid)
            if not tmdb:
                continue
            movie = movie_service.get_by_id(int(tmdb), enrich=False)
            if movie and any(g in fav_genres for g in movie.get("genres", [])):
                genre_boost[mid] = boost

    final = {
        movie_id: (
            float(config["popularityWeight"]) * s_pop.get(movie_id, 0)
            + float(config["funkSvdWeight"]) * s_funk.get(movie_id, 0)
            + float(config["neuMfWeight"]) * s_ncf.get(movie_id, 0)
            + genre_boost.get(movie_id, 0)
        )
        for movie_id in cands
    }
    top   = sorted(final, key=final.get, reverse=True)[:n]

    ranked_movies = []
    for mid in top:
        tmdb = art["movie2tmdb"].get(mid)
        if not tmdb:
            continue
        ranked_movies.append((int(tmdb), mid))

    movies_by_id = {
        movie["id"]: movie
        for movie in movie_service.get_by_ids(
            [tmdb_id for tmdb_id, _ in ranked_movies]
        )
    }
    result = []
    for tmdb_id, mid in ranked_movies:
        movie = movies_by_id.get(tmdb_id)
        if not movie:
            continue
        movie["recommendationScore"] = round(final[mid], 4)
        movie["scoreComponents"] = {
            "popularity": round(float(s_pop.get(mid, 0)), 4),
            "funkSvd": round(float(s_funk.get(mid, 0)), 4) if s_funk else None,
            "neuMf": round(float(s_ncf.get(mid, 0)), 4) if s_ncf else None,
            "genreBoost": round(float(genre_boost.get(mid, 0)), 4),
            "final": round(float(final[mid]), 4),
        }
        movie["reason"] = (
            "Personalized from your MovieLens profile"
            if s_funk or s_ncf
            else "Matches your genre preferences"
            if mid in genre_boost
            else "Popular and highly rated"
        )
        result.append(movie)

    return result[:n]


def _recs_by_favorites(fav_tmdb, watched_tmdb, n) -> list:
    """Content-based recommendations seeded by the user's favourite movies."""
    from sklearn.metrics.pairwise import cosine_similarity as cos_sim

    art = _load()
    if art is None:
        return []

    seen  = set(watched_tmdb)
    seeds = [t for t in fav_tmdb if t not in seen][:3]
    if not seeds:
        return []

    tfidf        = art["tfidf"]
    title_to_idx = art["title_to_idx"]
    idx_to_title = art["idx_to_title"]

    agg_sim     = None
    seed_titles = []

    for tmdb_id in seeds:
        movie = movie_service.get_by_id(int(tmdb_id), enrich=False)
        if not movie:
            continue
        title = movie.get("title", "")
        if title not in title_to_idx:
            continue
        idx = title_to_idx[title]
        if hasattr(idx, "iloc"):
            idx = idx.iloc[0]
        sim = cos_sim(tfidf[int(idx)], tfidf).flatten()
        agg_sim = sim if agg_sim is None else agg_sim + sim
        seed_titles.append(title)

    if agg_sim is None:
        return []

    reason = f"Because you liked {seed_titles[0]}" if seed_titles else "Based on your favourites"
    scored = sorted(enumerate(agg_sim), key=lambda x: x[1], reverse=True)

    excluded = set(fav_tmdb) | seen
    ranked_movies = []
    for row_idx, score in scored:
        if len(ranked_movies) >= n:
            break
        title = idx_to_title.get(row_idx)
        if not title:
            continue
        # Find tmdb_id from movie_service
        matches = movie_service.df[movie_service.df["title"] == title]
        if matches.empty:
            continue
        tmdb_id = int(matches.iloc[0]["id"])
        if tmdb_id in excluded:
            continue
        ranked_movies.append((tmdb_id, score))

    movies_by_id = {
        movie["id"]: movie
        for movie in movie_service.get_by_ids(
            [tmdb_id for tmdb_id, _ in ranked_movies]
        )
    }
    result = []
    for tmdb_id, score in ranked_movies:
        movie = movies_by_id.get(tmdb_id)
        if not movie:
            continue
        movie["recommendationScore"] = round(float(score), 4)
        movie["scoreComponents"] = {
            "contentSimilarity": round(float(score), 4),
            "final": round(float(score), 4),
        }
        movie["reason"] = reason
        result.append(movie)

    return result
