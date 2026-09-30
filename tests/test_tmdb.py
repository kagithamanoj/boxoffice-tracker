"""Mocked tests for the TMDB client. No network calls."""

from unittest.mock import MagicMock, patch

from boxoffice.providers.tmdb import TMDBClient, all_pages


def make_client(payload):
    client = TMDBClient(read_token="fake-token-for-tests")
    auth_header = client.session.headers["Authorization"]
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    client.session = MagicMock()
    client.session.get.return_value = resp
    return client, auth_header


def test_now_playing_uses_bearer_and_endpoint():
    client, auth_header = make_client({"results": [], "total_pages": 1})
    client.now_playing(region="US")
    url = client.session.get.call_args.args[0]
    assert url == "https://api.themoviedb.org/3/movie/now_playing"
    assert auth_header == "Bearer fake-token-for-tests"


def test_movie_details_endpoint():
    client, _ = make_client({"id": 1, "title": "Test"})
    data = client.movie_details(1)
    url = client.session.get.call_args.args[0]
    assert url == "https://api.themoviedb.org/3/movie/1"
    assert data["title"] == "Test"


def test_all_pages_collects_results():
    payloads = [
        {"results": [{"id": 1}], "total_pages": 2},
        {"results": [{"id": 2}], "total_pages": 2},
    ]
    calls = []

    def fake_fetch(page=1):
        calls.append(page)
        return payloads[page - 1]

    items = all_pages(fake_fetch, max_pages=5)
    assert [i["id"] for i in items] == [1, 2]
    assert calls == [1, 2]


def test_missing_token_raises_clear_error():
    with patch("boxoffice.config.TMDB_READ_TOKEN", ""):
        try:
            TMDBClient()
        except RuntimeError as exc:
            assert "TMDB_READ_TOKEN" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")
