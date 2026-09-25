"""Movie catalog service with optional live TMDB enrichment."""

import ast
import logging
import pathlib

import pandas as pd

from .tmdb_client import TMDBClient, TMDB_IMAGE_URL


logger = logging.getLogger(__name__)

# Prefer the bundled backend data, then the repository data, then the Docker mount.
_LOCAL_DATA = pathlib.Path(__file__).resolve().parent.parent / "data" / "movies-dataset"
_PROJECT_DATA = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "movielens"
_DOCKER_DATA = pathlib.Path("/workspace/data/movielens")

if (_LOCAL_DATA / "movies_metadata.csv").exists():
    DATA_DIR = _LOCAL_DATA
elif _PROJECT_DATA.exists():
    DATA_DIR = _PROJECT_DATA
elif _DOCKER_DATA.exists():
    DATA_DIR = _DOCKER_DATA
else:
    DATA_DIR = _LOCAL_DATA


def _parse_list(raw, key="name", limit=None):
    """Safely parse a JSON-like dataset column into a list of strings."""
    try:
        items = ast.literal_eval(raw)
        names = [item[key] for item in items if key in item]
        return names[:limit] if limit else names
    except Exception:
        return []


def _clean_scalar(value):
    """Convert pandas null values to None without changing valid scalars."""
    if value is None:
        return None
    try:
        return None if pd.isna(value) else value
    except (TypeError, ValueError):
        return value


class MovieService:
    """Load the recommendation catalog once and enrich responses through TMDB."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ready = False
            cls._instance._tmdb = TMDBClient()
        return cls._instance

    @property
    def tmdb_enabled(self) -> bool:
        return self._tmdb.configured

    def tmdb_status(self) -> dict:
        return self._tmdb.status()

    def check_tmdb(self) -> dict:
        return self._tmdb.check_health()

    def clear_tmdb_cache(self) -> int:
        return self._tmdb.clear_cache()

    def _load(self):
        if self._ready:
            return
        try:
            self._load_movies()
            self._load_credits()
            self._ready = True
            logger.info("MovieService ready: %d movies loaded", len(self.df))
        except Exception as exc:
            logger.error("MovieService load error: %s", exc)
            self.df = pd.DataFrame()
            self._by_id = {}
            self._credits = {}
            self._ready = True

    def _load_movies(self):
        desired_columns = [
            "id",
            "title",
            "overview",
            "genres",
            "vote_average",
            "vote_count",
            "release_date",
            "poster_path",
            "backdrop_path",
            "tagline",
            "runtime",
        ]
        header = pd.read_csv(
            DATA_DIR / "movies_metadata.csv", nrows=0, low_memory=False
        ).columns.tolist()
        usecols = [column for column in desired_columns if column in header]

        self.df = pd.read_csv(
            DATA_DIR / "movies_metadata.csv",
            usecols=usecols,
            low_memory=False,
        )
        self.df["id"] = pd.to_numeric(self.df["id"], errors="coerce")
        self.df["vote_average"] = pd.to_numeric(
            self.df["vote_average"], errors="coerce"
        ).fillna(0)
        self.df["vote_count"] = pd.to_numeric(
            self.df["vote_count"], errors="coerce"
        ).fillna(0)
        self.df.dropna(subset=["id", "title"], inplace=True)
        self.df["id"] = self.df["id"].astype(int)

        self.df["genres_list"] = self.df["genres"].apply(
            lambda value: _parse_list(value) if pd.notna(value) else []
        )
        self.df["year"] = (
            pd.to_datetime(self.df["release_date"], errors="coerce")
            .dt.year.fillna(0)
            .astype(int)
        )
        self.df["year"] = self.df["year"].replace(0, None)
        self._by_id = {
            int(row["id"]): row.to_dict() for _, row in self.df.iterrows()
        }

    def _load_credits(self):
        credits = pd.read_csv(DATA_DIR / "credits.csv")
        credits["id"] = pd.to_numeric(credits["id"], errors="coerce")
        credits.dropna(subset=["id"], inplace=True)
        credits["id"] = credits["id"].astype(int)

        self._credits = {}
        for _, row in credits.iterrows():
            cast = _parse_list(row.get("cast", "[]"), key="name", limit=5)
            try:
                crew = ast.literal_eval(row.get("crew", "[]"))
                director = next(
                    (
                        member["name"]
                        for member in crew
                        if member.get("job") == "Director"
                    ),
                    None,
                )
            except Exception:
                director = None
            self._credits[int(row["id"])] = {
                "cast": cast,
                "director": director,
            }

    def _to_dict(self, row: dict, live: dict | None = None) -> dict:
        tmdb_id = int(row["id"])
        poster = _clean_scalar(row.get("poster_path"))
        backdrop = _clean_scalar(row.get("backdrop_path"))
        local_runtime = _clean_scalar(row.get("runtime"))
        local_release_date = _clean_scalar(row.get("release_date"))

        movie = {
            "id": tmdb_id,
            "title": str(_clean_scalar(row.get("title")) or ""),
            "overview": str(_clean_scalar(row.get("overview")) or ""),
            "genres": row.get("genres_list", []) or [],
            "vote_average": round(float(row.get("vote_average") or 0), 1),
            "vote_count": int(row.get("vote_count") or 0),
            "year": _clean_scalar(row.get("year")),
            "release_date": str(local_release_date or ""),
            "tagline": str(_clean_scalar(row.get("tagline")) or ""),
            "runtime": int(local_runtime) if local_runtime else None,
            "metadata_source": "dataset",
        }
        credits = self._credits.get(tmdb_id, {})
        movie["cast"] = credits.get("cast", [])
        movie["director"] = credits.get("director")

        if live:
            # A successful TMDB response is authoritative for current artwork.
            poster = live.get("poster_path")
            backdrop = live.get("backdrop_path")
            for field in (
                "title",
                "overview",
                "tagline",
                "release_date",
                "year",
                "runtime",
                "vote_average",
                "vote_count",
            ):
                value = live.get(field)
                if value not in (None, ""):
                    movie[field] = value
            if live.get("genres"):
                movie["genres"] = live["genres"]
            if live.get("cast"):
                movie["cast"] = live["cast"]
            if live.get("director"):
                movie["director"] = live["director"]
            for field in (
                "original_title",
                "original_language",
                "status",
                "homepage",
                "imdb_id",
                "budget",
                "revenue",
                "popularity",
                "production_companies",
            ):
                movie[field] = live.get(field)
            movie["metadata_source"] = "tmdb"

        movie["vote_average"] = round(float(movie.get("vote_average") or 0), 1)
        movie["vote_count"] = int(movie.get("vote_count") or 0)
        movie["poster_url"] = (
            f"{TMDB_IMAGE_URL}/w500{poster}" if poster else None
        )
        movie["backdrop_url"] = (
            f"{TMDB_IMAGE_URL}/w1280{backdrop}" if backdrop else None
        )
        movie["tmdb_url"] = f"https://www.themoviedb.org/movie/{tmdb_id}"
        return movie

    def _serialize_many(self, rows: list[dict], enrich: bool = True) -> list:
        if not rows:
            return []
        live_by_id = {}
        if enrich and self.tmdb_enabled:
            live_by_id = self._tmdb.fetch_movies(
                [int(row["id"]) for row in rows]
            )
        movies = [
            self._to_dict(row, live_by_id.get(int(row["id"])))
            for row in rows
        ]
        return [movie for movie in movies if movie.get("title")]

    def search(self, query: str, limit: int = 10) -> list:
        self._load()
        if not query or self.df.empty:
            return []
        mask = self.df["title"].str.contains(
            query, case=False, na=False, regex=False
        )
        results = (
            self.df[mask]
            .sort_values("vote_count", ascending=False)
            .head(limit)
        )
        return self._serialize_many(results.to_dict("records"))

    def get_by_id(self, tmdb_id: int, enrich: bool = True) -> dict | None:
        self._load()
        tmdb_id = int(tmdb_id)
        row = self._by_id.get(tmdb_id)
        live = (
            self._tmdb.fetch_movie(tmdb_id)
            if enrich and self.tmdb_enabled
            else None
        )
        if not row and not live:
            return None
        row = row or {"id": tmdb_id, "title": live.get("title", "")}
        return self._to_dict(row, live)

    def get_by_ids(self, tmdb_ids: list, enrich: bool = True) -> list:
        self._load()
        rows = []
        for value in tmdb_ids:
            try:
                tmdb_id = int(value)
            except (TypeError, ValueError):
                continue
            row = self._by_id.get(tmdb_id)
            if row:
                rows.append(row)
            elif enrich and self.tmdb_enabled:
                rows.append({"id": tmdb_id, "title": ""})
        return self._serialize_many(rows, enrich=enrich)

    def get_trending(self, limit: int = 20) -> list:
        """Return local Bayesian-ranked movies with live TMDB presentation data."""
        self._load()
        if self.df.empty:
            return []
        frame = self.df.copy()
        frame = frame[frame["vote_count"] > 100]
        frame["_score"] = frame["vote_average"] * (frame["vote_count"] ** 0.4)
        top = frame.sort_values("_score", ascending=False).head(limit)
        return self._serialize_many(top.to_dict("records"))


movie_service = MovieService()
