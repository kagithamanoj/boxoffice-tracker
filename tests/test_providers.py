"""Mocked tests for new provider logic. No network calls."""

from unittest.mock import MagicMock

from boxoffice.providers.grosses import TMDBRevenueProvider
from boxoffice.providers.showtimes import SeatGeekProvider, _title_matches
from boxoffice.providers.tmdb import TMDBClient


def test_title_matches():
    assert _title_matches("Dune Part Two", "Dune: Part Two (2024)")
    assert _title_matches("Dune", "Dune: Part Two")
    assert not _title_matches("Dune Part Two", "Oppenheimer")
    assert not _title_matches("It", "It")  # short words are ignored


def test_seatgeek_params_zip_and_latlon():
    p = SeatGeekProvider(client_id="cid")
    z = p._params("Dune", "75234", "2026-10-01")
    assert z["postal_code"] == "75234"
    assert z["client_id"] == "cid"
    assert z["datetime_utc.gte"] == "2026-10-01T00:00:00"
    ll = p._params("Dune", "32.9,-96.9", "2026-10-01")
    assert ll["lat"] == "32.9" and ll["lon"] == "-96.9"


def test_seatgeek_maps_film_events_and_skips_concerts():
    provider = SeatGeekProvider()
    payload = {
        "events": [
            {
                "id": 1,
                "title": "Dune: Part Two",
                "datetime_utc": "2026-10-01T19:00:00",
                "url": "https://seatgeek.com/e/1",
                "venue": {"name": "AMC Northpark", "city": "Dallas"},
                "taxonomies": [{"name": "film"}],
                "stats": {"lowest_price": 12},
            },
            {
                "id": 2,
                "title": "Taylor Swift",
                "datetime_utc": "2026-10-01T20:00:00",
                "url": "https://seatgeek.com/e/2",
                "venue": {"name": "Arena", "city": "Dallas"},
                "taxonomies": [{"name": "concert"}],
                "stats": {},
            },
        ]
    }
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    provider_get = MagicMock(return_value=resp)

    import boxoffice.providers.showtimes as st

    orig = st.requests.get
    st.requests.get = provider_get
    try:
        out = provider.search_showtimes("Dune Part Two", "75234", "2026-10-01")
    finally:
        st.requests.get = orig

    assert len(out) == 1
    s = out[0]
    assert s.theater == "AMC Northpark"
    assert s.starts_at == "2026-10-01T19:00:00"
    # SeatGeek publishes no seat counts; never guess availability.
    assert s.availability == "unknown"
    assert s.extra["seatgeek_id"] == 1


def test_tmdb_revenue_provider_emits_worldwide_total():
    client = MagicMock()
    client.search_movie.return_value = {"results": [{"id": 550}]}
    client.movie_details.return_value = {
        "id": 550,
        "title": "Fight Club",
        "release_date": "1999-10-15",
        "budget": 63000000,
        "revenue": 100853753,
    }
    records = TMDBRevenueProvider(client=client).fetch_grosses("Fight Club")
    assert len(records) == 1
    g = records[0]
    assert g.period == "total" and g.region == "worldwide"
    assert g.gross_usd == 100853753 and g.source == "tmdb"


def test_tmdb_revenue_provider_skips_zero_revenue():
    client = MagicMock()
    client.search_movie.return_value = {"results": [{"id": 1}]}
    client.movie_details.return_value = {
        "id": 1, "title": "Unknown", "revenue": 0, "budget": 0,
    }
    assert TMDBRevenueProvider(client=client).fetch_grosses("Unknown") == []


def test_top_grossing_ranks_by_revenue():
    client = TMDBClient(read_token="fake")
    client.now_playing = MagicMock(
        return_value={"results": [{"id": 1}, {"id": 2}, {"id": 3}]}
    )
    fins = {
        1: {"budget": 10, "revenue": 30, "profit": 20},
        2: {"budget": 10, "revenue": 90, "profit": 80},
        3: {"budget": 0, "revenue": 0, "profit": None},
    }
    client.financials = MagicMock(side_effect=lambda i: fins[i])
    top = client.top_grossing_now_playing(limit=2, pause=0)
    assert [m["id"] for m in top] == [2, 1]
    assert top[0]["profit"] == 80
