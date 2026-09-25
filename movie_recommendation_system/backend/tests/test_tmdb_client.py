import unittest

import requests

from app.tmdb_client import TMDBClient


class FakeResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload or {}
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError(f"Unexpected HTTP status {self.status_code}")


class TMDBClientTests(unittest.TestCase):
    def test_fetch_movie_normalizes_details_and_uses_api_key(self):
        calls = []
        payload = {
            "id": 550,
            "title": "Fight Club",
            "original_title": "Fight Club",
            "overview": "Overview",
            "tagline": "Tagline",
            "release_date": "1999-10-15",
            "runtime": 139,
            "genres": [{"name": "Drama"}],
            "vote_average": 8.4,
            "vote_count": 30000,
            "poster_path": "/poster.jpg",
            "backdrop_path": "/backdrop.jpg",
            "credits": {
                "cast": [{"name": "Edward Norton"}],
                "crew": [{"name": "David Fincher", "job": "Director"}],
            },
        }

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse(payload)

        client = TMDBClient(
            api_key="test-key", read_token="", request_get=fake_get
        )
        movie = client.fetch_movie(550)

        self.assertEqual(movie["title"], "Fight Club")
        self.assertEqual(movie["year"], 1999)
        self.assertEqual(movie["genres"], ["Drama"])
        self.assertEqual(movie["cast"], ["Edward Norton"])
        self.assertEqual(movie["director"], "David Fincher")
        self.assertEqual(calls[0][1]["params"]["api_key"], "test-key")
        self.assertEqual(calls[0][1]["params"]["append_to_response"], "credits")

        cached = client.fetch_movie(550)
        self.assertIs(cached, movie)
        self.assertEqual(len(calls), 1)

    def test_read_token_takes_precedence_over_api_key(self):
        calls = []

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse({"id": 11, "title": "Star Wars"})

        client = TMDBClient(
            api_key="test-key",
            read_token="test-token",
            request_get=fake_get,
        )
        client.fetch_movie(11)

        self.assertEqual(
            calls[0][1]["headers"]["Authorization"], "Bearer test-token"
        )
        self.assertNotIn("api_key", calls[0][1]["params"])

    def test_not_found_response_is_negatively_cached(self):
        calls = []

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return FakeResponse(status_code=404)

        client = TMDBClient(
            api_key="test-key", read_token="", request_get=fake_get
        )

        self.assertIsNone(client.fetch_movie(999999999))
        self.assertIsNone(client.fetch_movie(999999999))
        self.assertEqual(len(calls), 1)

    def test_unconfigured_client_stays_offline(self):
        client = TMDBClient(api_key="", read_token="")
        self.assertFalse(client.configured)
        self.assertIsNone(client.fetch_movie(550))
        self.assertEqual(client.fetch_movies([550]), {})

    def test_request_errors_do_not_log_the_api_key(self):
        def fake_get(url, **kwargs):
            raise requests.ConnectionError(
                "failed URL https://example.test?api_key=test-key"
            )

        client = TMDBClient(
            api_key="test-key", read_token="", request_get=fake_get
        )
        with self.assertLogs("app.tmdb_client", level="WARNING") as logs:
            self.assertIsNone(client.fetch_movie(550))

        self.assertNotIn("test-key", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
