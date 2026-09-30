"""Showtime providers.

Honest note up front: TMDB has no showtimes endpoint and no seat data.
Exact "seats booked" counts are not publicly exposed by theaters, so this
platform tracks sold-out and availability snapshots as a demand proxy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Showtime:
    movie_id: int
    movie_title: str
    theater: str
    starts_at: str  # ISO 8601
    screen: str = ""
    booking_url: str = ""
    availability: str = "unknown"  # available | limited | sold_out | unknown
    extra: dict = field(default_factory=dict)


class ShowtimeProvider(ABC):
    """Interface every showtime source must implement."""

    name: str = "base"

    @abstractmethod
    def search_showtimes(
        self, movie_title: str, location: str, date: str
    ) -> list[Showtime]:
        """Return showtimes for a movie near a location on a date.

        location: zip code or "lat,lon". date: YYYY-MM-DD.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Real options worth wiring up (documented, not yet implemented)
# ---------------------------------------------------------------------------
#
# 1. SerpApi Google Movies results
#    Paid API. Endpoint: https://serpapi.com/search.json with
#    engine=google_movies and q=<movie title>. Returns theaters and
#    showtimes for a query location. Good US coverage. Needs a SERPAPI_KEY.
#
# 2. International Showtimes API
#    Paid API at api.internationalshowtimes.com. Endpoints under /v4:
#    GET /v4/movies, GET /v4/showtimes?movie_id=...&location=...,
#    GET /v4/cinemas. Good international coverage. Needs an API key.
#
# 3. SeatGeek events API
#    Free tier available at platform.seatgeek.com. GET /2/events with
#    q=<movie title> returns events including some movie screenings.
#    Coverage for movies is spotty. Needs SEATGEEK_CLIENT_ID.


class SeatGeekProvider(ShowtimeProvider):
    """Stub. Wire up when you decide on a showtime data source."""

    name = "seatgeek"

    def __init__(self, client_id: str | None = None):
        self.client_id = client_id

    def search_showtimes(
        self, movie_title: str, location: str, date: str
    ) -> list[Showtime]:
        raise NotImplementedError(
            "SeatGeekProvider is not wired yet. To enable it: "
            "1) create a free app at https://platform.seatgeek.com to get a "
            "client ID, 2) implement search_showtimes() using GET "
            "https://api.seatgeek.com/2/events?q=<title> with the client ID, "
            "3) map events to Showtime records and store them via "
            "boxoffice.storage. Or pick a different source from the options "
            "listed at the top of boxoffice/providers/showtimes.py."
        )
