"""Showtime providers.

Honest note up front: TMDB has no showtimes endpoint and no seat data.
Exact "seats booked" counts are not publicly exposed by theaters, so this
platform tracks sold-out and availability snapshots as a demand proxy.
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import requests

from boxoffice import config

SEATGEEK_BASE = "https://api.seatgeek.com/2"


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
# Paid upgrades (documented, still stubbed)
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


def _title_matches(query: str, title: str) -> bool:
    """True when every significant word of the query appears in the title."""
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2]
    hay = title.lower()
    return bool(words) and all(w in hay for w in words)


class SeatGeekProvider(ShowtimeProvider):
    """Free-tier showtimes from the SeatGeek Discovery API.

    Works without a key for light use; a free client ID from
    https://platform.seatgeek.com raises the rate limit. Set it as
    SEATGEEK_CLIENT_ID.

    Honest limits, stated plainly:
    * SeatGeek is a ticket marketplace, not a theater listings feed. Movie
      screening coverage is spotty and region dependent. Some cities return
      nothing for a title that is clearly playing.
    * SeatGeek does not publish seat counts, so availability is always
      recorded as "unknown" here. The demand proxy is event counts and
      price movement over time, not seats booked.
    * Location should be a US zip code or "lat,lon". Other formats are
      passed through as a city name on a best-effort basis.
    """

    name = "seatgeek"

    def __init__(self, client_id: str | None = None, timeout: int = 30):
        self.client_id = client_id or config.SEATGEEK_CLIENT_ID
        self.timeout = timeout

    def _params(self, movie_title: str, location: str, date: str) -> dict:
        params = {
            "q": movie_title,
            "per_page": 50,
            "datetime_utc.gte": f"{date}T00:00:00",
            "datetime_utc.lte": f"{date}T23:59:59",
        }
        if self.client_id:
            params["client_id"] = self.client_id
        loc = location.strip()
        if re.fullmatch(r"-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?", loc):
            lat, lon = [p.strip() for p in loc.split(",")]
            params.update({"lat": lat, "lon": lon, "range": "30mi"})
        elif re.fullmatch(r"\d{5}", loc):
            params["postal_code"] = loc
        else:
            params["venue.city"] = loc
        return params

    def search_showtimes(
        self, movie_title: str, location: str, date: str
    ) -> list[Showtime]:
        resp = requests.get(
            f"{SEATGEEK_BASE}/events",
            params=self._params(movie_title, location, date),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        events = resp.json().get("events", [])

        showtimes: list[Showtime] = []
        for e in events or []:
            taxonomies = {
                (t.get("name") or "").lower() for t in e.get("taxonomies", [])
            }
            title = e.get("title") or e.get("short_title") or ""
            # Keep film screenings, plus anything whose title matches the
            # query in case the taxonomy is missing or generic.
            if "film" not in taxonomies and not _title_matches(movie_title, title):
                continue
            venue = e.get("venue") or {}
            stats = e.get("stats") or {}
            showtimes.append(
                Showtime(
                    movie_id=0,
                    movie_title=title,
                    theater=venue.get("name") or "",
                    starts_at=e.get("datetime_utc") or "",
                    booking_url=e.get("url") or "",
                    # SeatGeek publishes no seat counts; never guess.
                    availability="unknown",
                    extra={
                        "seatgeek_id": e.get("id"),
                        "venue_city": venue.get("city"),
                        "lowest_price": (stats.get("lowest_price")),
                    },
                )
            )
        return showtimes
