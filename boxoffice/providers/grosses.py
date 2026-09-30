"""Box office grosses providers.

Honest note: grosses are not available from TMDB as historical box office
data. The reliable public sources are:

  * Box Office Mojo (boxofficemojo.com, an IMDb company)
    Daily and weekend grosses by movie, domestic and worldwide. No official
    public API. Data is gathered by scraping or by third-party wrappers.
    Respect their terms of service and rate limits.

  * The Numbers (the-numbers.com)
    Daily, weekend, and weekly box office tables plus budgets and
    international breakdowns. No official public API. Typically accessed by
    scraping. Respect their terms of service and rate limits.

There is no official free API for either source. Any grosses provider here
must either scrape responsibly or use a licensed feed.
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
        """Return gross records for a movie. Stub raises NotImplementedError."""
        raise NotImplementedError


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
            "documented source."
        )
