# boxoffice-tracker

A box office tracking platform. It pulls movie metadata, snapshots showtimes
and seat availability over time, and aggregates box office grosses. The goal
is demand tracking: which movies are filling seats, and how grosses move day
by day.

## What works now

* TMDB client (`boxoffice/providers/tmdb.py`). Real endpoints: now_playing,
  trending, popular, movie_details, movie_credits. Auth is
  `Authorization: Bearer <read token>` against `api.themoviedb.org/3`.
* SQLite snapshot store (`boxoffice/storage.py`). Tables for movies,
  showtime snapshots, availability snapshots, and grosses.
* CLI (`boxoffice/cli.py`). `snapshot-now-playing` pulls TMDB and stores it.
  `show` prints recent snapshots.

## What is stubbed

* Showtimes provider. The stub raises `NotImplementedError` with setup steps.
* Grosses provider. Same: stub with setup steps.

## Honest data-source matrix

| Data | Source | Status |
|---|---|---|
| Movie metadata (titles, posters, release dates, revenue field) | TMDB | Working |
| Showtimes (theater, time, booking link) | SerpApi Google Movies / International Showtimes / SeatGeek | Pick one, not wired yet |
| Exact seats-booked counts | No public source | Not available. Theaters do not publish this. Track sold-out and availability snapshots as a demand proxy instead |
| Box office grosses (daily, weekend, worldwide) | Box Office Mojo, The Numbers | Neither has an official free API. Needs a licensed feed or permitted collection |

TMDB is metadata only. It has no showtimes endpoint and no seat data.

## Setup

1. Get a TMDB API read access token from your TMDB account settings.
2. Store it in the Secure Vault as `custom.tmdb`. It is never committed.
3. Export it at runtime before running:

```bash
export TMDB_READ_TOKEN=...   # from the vault, not from a file
python -m boxoffice.cli snapshot-now-playing --region US
```

Copy `.env.example` to `.env` for local defaults if you want. The `.env`
file is gitignored. Real tokens never go in it in this repo.

Run the tests:

```bash
pip install -r requirements.txt
python -m pytest
```

## Roadmap

1. Choose a showtime data source (SerpApi, International Showtimes, or
   SeatGeek) and implement `search_showtimes`.
2. Add a daily cron that snapshots now-playing movies plus showtimes for
   tracked titles and locations.
3. Build a demand view: sold-out rate per movie per day from the snapshots.
4. Wire a grosses feed and join it with the demand signals.
5. Small dashboard on top of the SQLite store.
