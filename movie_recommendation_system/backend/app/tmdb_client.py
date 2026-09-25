"""Small TMDB API client with bounded in-memory caching."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import requests


logger = logging.getLogger(__name__)

TMDB_API_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p"

_CACHE_MISS = object()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class TMDBClient:
    """Fetch and normalize movie metadata from TMDB API v3."""

    def __init__(
        self,
        api_key: str | None = None,
        read_token: str | None = None,
        request_get: Callable | None = None,
    ) -> None:
        self.api_key = (
            os.environ.get("TMDB_API_KEY", "") if api_key is None else api_key
        ).strip()
        self.read_token = (
            os.environ.get("TMDB_READ_TOKEN", "")
            if read_token is None
            else read_token
        ).strip()
        self.language = os.environ.get("TMDB_LANGUAGE", "en-US").strip() or "en-US"
        self.timeout = max(_env_float("TMDB_TIMEOUT_SECONDS", 5.0), 0.1)
        self.cache_ttl = max(_env_int("TMDB_CACHE_TTL_SECONDS", 86400), 0)
        self.failure_ttl = max(_env_int("TMDB_FAILURE_TTL_SECONDS", 300), 0)
        self.cache_max_entries = max(_env_int("TMDB_CACHE_MAX_ENTRIES", 2048), 1)
        self.max_workers = min(max(_env_int("TMDB_MAX_WORKERS", 8), 1), 16)
        self._request_get = request_get or requests.get
        self._cache: OrderedDict[int, tuple[float, dict | None]] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._last_health = None

    @property
    def configured(self) -> bool:
        """Return whether either supported TMDB credential is available."""
        return bool(self.api_key or self.read_token)

    def status(self) -> dict:
        """Return safe client configuration and the latest probe result."""
        with self._cache_lock:
            cache_entries = len(self._cache)
        return {
            "configured": self.configured,
            "authentication": (
                "read-token" if self.read_token else "api-key"
                if self.api_key else "none"
            ),
            "language": self.language,
            "timeoutSeconds": self.timeout,
            "cache": {
                "entries": cache_entries,
                "maximumEntries": self.cache_max_entries,
                "successTtlSeconds": self.cache_ttl,
                "failureTtlSeconds": self.failure_ttl,
            },
            "workers": self.max_workers,
            "lastCheck": self._last_health,
        }

    def check_health(self) -> dict:
        """Probe TMDB configuration without exposing credentials."""
        checked_at = time.time()
        if not self.configured:
            result = {
                "healthy": False,
                "configured": False,
                "statusCode": None,
                "latencyMs": None,
                "checkedAt": checked_at,
                "message": "TMDB credentials are not configured",
            }
            self._last_health = result
            return result

        headers = {"accept": "application/json"}
        params = {}
        if self.read_token:
            headers["Authorization"] = f"Bearer {self.read_token}"
        else:
            params["api_key"] = self.api_key
        started = time.perf_counter()
        try:
            response = self._request_get(
                f"{TMDB_API_URL}/configuration",
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            latency = round((time.perf_counter() - started) * 1000, 1)
            result = {
                "healthy": response.ok,
                "configured": True,
                "statusCode": response.status_code,
                "latencyMs": latency,
                "checkedAt": checked_at,
                "message": "TMDB API is reachable" if response.ok else (
                    "TMDB rejected the health probe"
                ),
            }
        except requests.RequestException as exc:
            result = {
                "healthy": False,
                "configured": True,
                "statusCode": None,
                "latencyMs": round((time.perf_counter() - started) * 1000, 1),
                "checkedAt": checked_at,
                "message": f"TMDB request failed ({type(exc).__name__})",
            }
        self._last_health = result
        return result

    def clear_cache(self) -> int:
        with self._cache_lock:
            removed = len(self._cache)
            self._cache.clear()
        return removed

    def _cache_get(self, tmdb_id: int):
        now = time.monotonic()
        with self._cache_lock:
            entry = self._cache.get(tmdb_id)
            if entry is None:
                return _CACHE_MISS
            expires_at, value = entry
            if expires_at <= now:
                del self._cache[tmdb_id]
                return _CACHE_MISS
            self._cache.move_to_end(tmdb_id)
            return value

    def _cache_set(self, tmdb_id: int, value: dict | None) -> None:
        ttl = self.cache_ttl if value is not None else self.failure_ttl
        with self._cache_lock:
            self._cache[tmdb_id] = (time.monotonic() + ttl, value)
            self._cache.move_to_end(tmdb_id)
            while len(self._cache) > self.cache_max_entries:
                self._cache.popitem(last=False)

    @staticmethod
    def _normalize_movie(data: dict) -> dict:
        credits = data.get("credits") or {}
        crew = credits.get("crew") or []
        cast = credits.get("cast") or []
        director = next(
            (
                member.get("name")
                for member in crew
                if member.get("job") == "Director" and member.get("name")
            ),
            None,
        )
        release_date = data.get("release_date") or None
        year = None
        if release_date and len(release_date) >= 4:
            try:
                year = int(release_date[:4])
            except ValueError:
                year = None

        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "original_title": data.get("original_title"),
            "overview": data.get("overview"),
            "tagline": data.get("tagline"),
            "release_date": release_date,
            "year": year,
            "runtime": data.get("runtime"),
            "genres": [
                genre["name"]
                for genre in (data.get("genres") or [])
                if genre.get("name")
            ],
            "vote_average": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
            "popularity": data.get("popularity"),
            "poster_path": data.get("poster_path"),
            "backdrop_path": data.get("backdrop_path"),
            "cast": [member["name"] for member in cast[:5] if member.get("name")],
            "director": director,
            "imdb_id": data.get("imdb_id"),
            "original_language": data.get("original_language"),
            "status": data.get("status"),
            "homepage": data.get("homepage") or None,
            "budget": data.get("budget"),
            "revenue": data.get("revenue"),
            "production_companies": [
                company["name"]
                for company in (data.get("production_companies") or [])
                if company.get("name")
            ],
        }

    def fetch_movie(self, tmdb_id: int) -> dict | None:
        """Return normalized TMDB metadata, using the cache when possible."""
        if not self.configured:
            return None

        try:
            tmdb_id = int(tmdb_id)
        except (TypeError, ValueError):
            return None
        if tmdb_id <= 0:
            return None

        cached = self._cache_get(tmdb_id)
        if cached is not _CACHE_MISS:
            return cached

        headers = {"accept": "application/json"}
        params = {
            "language": self.language,
            "append_to_response": "credits",
        }
        if self.read_token:
            headers["Authorization"] = f"Bearer {self.read_token}"
        else:
            params["api_key"] = self.api_key

        try:
            response = self._request_get(
                f"{TMDB_API_URL}/movie/{tmdb_id}",
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            if response.status_code == 404:
                logger.info("TMDB movie %s was not found", tmdb_id)
                self._cache_set(tmdb_id, None)
                return None
            response.raise_for_status()
            movie = self._normalize_movie(response.json())
            self._cache_set(tmdb_id, movie)
            return movie
        except (requests.RequestException, TypeError, ValueError) as exc:
            # Request exceptions can include the full URL and its api_key query
            # parameter, so diagnostics record only the exception class.
            logger.warning(
                "TMDB request failed for movie %s (%s)",
                tmdb_id,
                type(exc).__name__,
            )
            self._cache_set(tmdb_id, None)
            return None

    def fetch_movies(self, tmdb_ids: list[int]) -> dict[int, dict]:
        """Fetch multiple movies concurrently and return successful results by ID."""
        if not self.configured:
            return {}

        valid_ids = []
        for value in tmdb_ids:
            try:
                tmdb_id = int(value)
            except (TypeError, ValueError):
                continue
            if tmdb_id > 0 and tmdb_id not in valid_ids:
                valid_ids.append(tmdb_id)

        if not valid_ids:
            return {}
        if len(valid_ids) == 1:
            movie = self.fetch_movie(valid_ids[0])
            return {valid_ids[0]: movie} if movie else {}

        results = {}
        with ThreadPoolExecutor(
            max_workers=min(self.max_workers, len(valid_ids)),
            thread_name_prefix="tmdb",
        ) as executor:
            future_to_id = {
                executor.submit(self.fetch_movie, tmdb_id): tmdb_id
                for tmdb_id in valid_ids
            }
            for future in as_completed(future_to_id):
                tmdb_id = future_to_id[future]
                try:
                    movie = future.result()
                except Exception as exc:  # defensive isolation between batch items
                    logger.warning("TMDB batch item %s failed: %s", tmdb_id, exc)
                    continue
                if movie:
                    results[tmdb_id] = movie
        return results
