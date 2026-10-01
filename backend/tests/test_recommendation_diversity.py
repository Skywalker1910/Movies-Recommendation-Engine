"""
Diagnostic test: verify that different user preferences produce different recommendations.

Reproduces the bug where two very different user profiles get identical recommendations
via the /movies/preview endpoint.
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        with app.app_context():
            yield c


PROFILE_A = {
    "genres": ["Action", "Thriller", "War", "Science Fiction"],
    "movies": ["Interstellar", "Inglourious Basterds", "Mission: Impossible", "Dunkirk"],
}

PROFILE_B = {
    "genres": ["Drama", "Family", "Fantasy", "Horror"],
    "movies": ["Moana", "Minions", "Knocked Up", "Johnny English", "Hancock"],
}


def _search_movie_ids(client, titles):
    """Search for each title and return the first match's TMDB ID."""
    ids = []
    for title in titles:
        resp = client.get(f"/movies/search?q={title}&limit=1")
        data = resp.get_json()
        if data and len(data) > 0:
            ids.append(data[0]["id"])
            print(f"  Found '{title}' -> TMDB ID {data[0]['id']}")
        else:
            print(f"  WARNING: '{title}' not found in movie catalog")
    return ids


def _call_preview(client, genres, movie_ids, n=12):
    resp = client.post("/movies/preview", json={
        "genres": genres,
        "movieIds": movie_ids,
        "n": n,
    })
    return resp.get_json()


def test_preview_different_profiles_different_results(client):
    """Two very different taste profiles must NOT return the same movies."""
    print("\n=== Resolving movie IDs for Profile A ===")
    ids_a = _search_movie_ids(client, PROFILE_A["movies"])
    print(f"\n=== Resolving movie IDs for Profile B ===")
    ids_b = _search_movie_ids(client, PROFILE_B["movies"])

    assert ids_a, "Profile A: no movies resolved"
    assert ids_b, "Profile B: no movies resolved"

    print(f"\n=== Calling /movies/preview for Profile A ===")
    print(f"  Genres: {PROFILE_A['genres']}")
    print(f"  Movie IDs: {ids_a}")
    recs_a = _call_preview(client, PROFILE_A["genres"], ids_a)

    print(f"\n=== Calling /movies/preview for Profile B ===")
    print(f"  Genres: {PROFILE_B['genres']}")
    print(f"  Movie IDs: {ids_b}")
    recs_b = _call_preview(client, PROFILE_B["genres"], ids_b)

    titles_a = [r["title"] for r in recs_a] if isinstance(recs_a, list) else []
    titles_b = [r["title"] for r in recs_b] if isinstance(recs_b, list) else []

    print(f"\n=== Profile A recommendations ({len(titles_a)}) ===")
    for i, r in enumerate(recs_a if isinstance(recs_a, list) else []):
        score = r.get("scoreComponents", {})
        print(f"  {i+1}. {r['title']} | final={score.get('final', '?')} "
              f"content={score.get('content', '?')} pop={score.get('popularity', '?')} "
              f"genreMult={score.get('genreMultiplier', '?')} | {r.get('reason', '')}")

    print(f"\n=== Profile B recommendations ({len(titles_b)}) ===")
    for i, r in enumerate(recs_b if isinstance(recs_b, list) else []):
        score = r.get("scoreComponents", {})
        print(f"  {i+1}. {r['title']} | final={score.get('final', '?')} "
              f"content={score.get('content', '?')} pop={score.get('popularity', '?')} "
              f"genreMult={score.get('genreMultiplier', '?')} | {r.get('reason', '')}")

    overlap = set(titles_a) & set(titles_b)
    print(f"\n=== Overlap Analysis ===")
    print(f"  Profile A unique: {len(set(titles_a) - set(titles_b))}")
    print(f"  Profile B unique: {len(set(titles_b) - set(titles_a))}")
    print(f"  Shared: {len(overlap)} / {max(len(titles_a), len(titles_b))}")
    if overlap:
        print(f"  Overlapping titles: {sorted(overlap)}")

    assert titles_a != titles_b, (
        f"Both profiles returned identical recommendations!\n"
        f"A: {titles_a}\nB: {titles_b}"
    )
    assert len(overlap) < len(titles_a) * 0.5, (
        f"Too much overlap ({len(overlap)}/{len(titles_a)}): {sorted(overlap)}"
    )


def test_content_scoring_seeds_resolve(client):
    """Verify that selected movies actually resolve to TF-IDF seeds."""
    from app.ml_service import _load, _score_content
    from app.movie_service import movie_service

    print("\n=== Checking TF-IDF title resolution ===")

    art = _load()
    assert art is not None, "ML artifacts failed to load"
    title_to_idx = art["title_to_idx"]
    tmdb2movie = art["tmdb2movie"]

    test_movies = PROFILE_A["movies"] + PROFILE_B["movies"]
    for title in test_movies:
        resp = client.get(f"/movies/search?q={title}&limit=1")
        data = resp.get_json()
        if not data:
            print(f"  FAIL: '{title}' not in movie catalog")
            continue
        tmdb_id = data[0]["id"]
        movie = movie_service.get_by_id(tmdb_id, enrich=False)
        catalog_title = movie.get("title", "") if movie else ""
        in_tfidf = catalog_title in title_to_idx
        in_ml = tmdb_id in tmdb2movie
        mid = tmdb2movie.get(tmdb_id)
        print(f"  '{title}' -> TMDB {tmdb_id} -> catalog_title='{catalog_title}' "
              f"-> in_tfidf={in_tfidf} in_ml_mapping={in_ml} movieId={mid}")

    # Check how many titles from the catalog exist in TF-IDF index
    sample_tmdb_ids = list(art["tmdb2movie"].keys())[:20]
    resolved = 0
    for tmdb_id in sample_tmdb_ids:
        movie = movie_service.get_by_id(int(tmdb_id), enrich=False)
        if movie and movie.get("title", "") in title_to_idx:
            resolved += 1
    print(f"\n  TF-IDF resolution rate (sample of 20): {resolved}/20")
    print(f"  Total titles in TF-IDF index: {len(title_to_idx)}")
    print(f"  Total TMDB->MovieLens mappings: {len(tmdb2movie)}")


def test_candidate_pool_differs(client):
    """Verify candidate pools are different for different genre selections."""
    from app.ml_service import _load, _diversified_candidate_pool

    art = _load()
    assert art is not None

    print("\n=== Resolving movie IDs ===")
    ids_a = _search_movie_ids(client, PROFILE_A["movies"])
    ids_b = _search_movie_ids(client, PROFILE_B["movies"])

    pool_a = set(_diversified_candidate_pool(
        art, PROFILE_A["genres"], ids_a, set(), n=400,
        user_id=hash(tuple(sorted(ids_a))),
    ))
    pool_b = set(_diversified_candidate_pool(
        art, PROFILE_B["genres"], ids_b, set(), n=400,
        user_id=hash(tuple(sorted(ids_b))),
    ))

    shared = pool_a & pool_b
    print(f"\n=== Candidate Pool Analysis ===")
    print(f"  Pool A size: {len(pool_a)}")
    print(f"  Pool B size: {len(pool_b)}")
    print(f"  Shared candidates: {len(shared)}")
    print(f"  Overlap: {len(shared) / max(len(pool_a), 1) * 100:.1f}%")
    print(f"  A-only: {len(pool_a - pool_b)}")
    print(f"  B-only: {len(pool_b - pool_a)}")


def test_genre_index_coverage(client):
    """Check how many movies are indexed per genre."""
    from app.ml_service import _load

    art = _load()
    assert art is not None

    print("\n=== Genre Index Coverage ===")
    genre_index = art.get("genre_index", {})
    all_genres = PROFILE_A["genres"] + PROFILE_B["genres"]
    for genre in sorted(set(all_genres)):
        count = len(genre_index.get(genre, []))
        print(f"  {genre}: {count} movies")
    print(f"\n  Total genres indexed: {len(genre_index)}")
    print(f"  All genre sizes: {', '.join(f'{g}: {len(v)}' for g, v in sorted(genre_index.items()))}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
