"""TMDB API v4 client using read-access token auth.

Uses Authorization: Bearer <read token> against api.themoviedb.org/3.
Only real TMDB endpoints are used here:
  GET /movie/now_playing
  GET /trending/{media_type}/{time_window}
  GET /movie/popular
  GET /movie/{movie_id}
  GET /movie/{movie_id}/credits
Docs: https://developer.themoviedb.org/reference/intro/getting-started
"""

from __future__ import annotations

import requests

from boxoffice import config


class TMDBClient:
    def __init__(self, read_token: str | None = None, timeout: int = 30):
        token = read_token or config.require_tmdb_token()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json;charset=utf-8",
            }
        )
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{config.TMDB_BASE_URL}{path}"
        params = {"language": config.DEFAULT_LANGUAGE, **(params or {})}
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def now_playing(self, region: str | None = None, page: int = 1) -> dict:
        """Movies currently in theaters. TMDB metadata only, no showtimes."""
        return self._get(
            "/movie/now_playing",
            {"region": region or config.DEFAULT_REGION, "page": page},
        )

    def trending(self, media_type: str = "movie", time_window: str = "day") -> dict:
        """Trending movies. media_type: movie|tv|person|all. window: day|week."""
        return self._get(f"/trending/{media_type}/{time_window}")

    def popular(self, page: int = 1) -> dict:
        """Popular movies list."""
        return self._get("/movie/popular", {"page": page})

    def movie_details(self, movie_id: int) -> dict:
        """Full details for one movie: title, release date, revenue, etc."""
        return self._get(f"/movie/{movie_id}")

    def movie_credits(self, movie_id: int) -> dict:
        """Cast and crew for one movie."""
        return self._get(f"/movie/{movie_id}/credits")


def all_pages(fetch, *args, max_pages: int = 5, **kwargs) -> list[dict]:
    """Collect result lists across pages from a paged TMDB call."""
    items: list[dict] = []
    page = 1
    while page <= max_pages:
        data = fetch(*args, page=page, **kwargs)
        items.extend(data.get("results", []))
        if page >= data.get("total_pages", 1):
            break
        page += 1
    return items
