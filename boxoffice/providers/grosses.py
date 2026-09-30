"""Box office grosses providers.

Honest note: neither Box Office Mojo nor The Numbers offers an official
free API, so daily tracked grosses need a licensed feed or permitted
collection. What IS free and official: TMDB's revenue and budget fields
on movie_details. Those are lifetime reported figures, not daily tracking,
so they work as a baseline, not a time series.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GrossRecord:
    movie_id: int
    movie_title: str
    date: str  # YYYY-MM-DD
    period: str  # daily | weekend | weekly | total
    gross_usd: int
    region: str = "domestic"
    source: str = ""
    extra: dict = field(default_factory=dict)


class GrossesProvider(ABC):
    """Interface every box office grosses source must implement."""

    name: str = "base"

    @abstractmethod
    def fetch_grosses(self, movie_title: str) -> list[GrossRecord]:
        """Return gross records for a movie."""
        raise NotImplementedError


class TMDBRevenueProvider(GrossesProvider):
    """Free grosses baseline from TMDB's official revenue field.

    Resolves a title with /search/movie, then reads revenue from
    movie_details. Emits one "total" record per movie with region
    "worldwide". TMDB reports 0 when it does not know the figure, and a
    0 revenue yields no records rather than a fake zero gross.
    """

    name = "tmdb_revenue"

    def __init__(self, client=None):
        if client is None:
            from boxoffice.providers.tmdb import TMDBClient

            client = TMDBClient()
        self.client = client

    def fetch_grosses(self, movie_title: str) -> list[GrossRecord]:
        results = self.client.search_movie(movie_title).get("results", [])
        if not results:
            return []
        best = results[0]
        details = self.client.movie_details(best["id"])
        revenue = details.get("revenue") or 0
        if not revenue:
            return []
        return [
            GrossRecord(
                movie_id=best["id"],
                movie_title=details.get("title") or movie_title,
                date=(details.get("release_date") or "")[:10],
                period="total",
                gross_usd=int(revenue),
                region="worldwide",
                source="tmdb",
                extra={"budget": details.get("budget") or 0},
            )
        ]


class BoxOfficeMojoProvider(GrossesProvider):
    """Stub. Wire up when a licensed or permitted feed is available."""

    name = "boxofficemojo"

    def fetch_grosses(self, movie_title: str) -> list[GrossRecord]:
        raise NotImplementedError(
            "BoxOfficeMojoProvider is not wired yet. Box Office Mojo has no "
            "official public API. To enable it: 1) confirm you are allowed to "
            "collect data from boxofficemojo.com under their terms of "
            "service, 2) implement fetch_grosses() to pull daily or weekend "
            "tables, 3) map rows to GrossRecord and store them via "
            "boxoffice.storage. The Numbers (the-numbers.com) is the other "
            "documented source. For a free baseline today, use "
            "TMDBRevenueProvider instead."
        )
