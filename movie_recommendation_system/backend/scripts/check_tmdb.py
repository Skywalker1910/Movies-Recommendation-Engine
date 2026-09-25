"""Verify TMDB configuration through the Flask movie endpoint."""

import sys

import requests

from app import create_app


def main() -> int:
    app = create_app("testing")
    client = app.test_client()

    health = client.get("/health").get_json()
    if health.get("integrations", {}).get("tmdb") != "configured":
        print("TMDB is not configured in backend/.env")
        return 1

    response = client.get("/movies/550")
    if response.status_code != 200:
        print(f"Movie endpoint returned HTTP {response.status_code}")
        return 1

    movie = response.get_json()
    if movie.get("metadata_source") != "tmdb":
        print("TMDB did not return live metadata; the endpoint used its local fallback")
        return 1
    if not movie.get("poster_url"):
        print("TMDB returned no poster for the smoke-test movie")
        return 1

    poster_response = requests.get(movie["poster_url"], timeout=10)
    poster_response.raise_for_status()

    print(f"Title: {movie['title']}")
    print(f"Metadata source: {movie['metadata_source']}")
    print(f"Poster HTTP status: {poster_response.status_code}")
    print(f"Backdrop available: {bool(movie.get('backdrop_url'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
