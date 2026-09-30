# boxoffice-tracker

A box office tracking platform. It pulls movie metadata, snapshots showtimes
and seat availability over time, and aggregates box office grosses. The goal
is demand tracking: which movies are filling seats, and how grosses move day
by day.

Everything here runs on free tiers. No paid API is required for any command.

## What works now

* TMDB client (`boxoffice/providers/tmdb.py`). Real endpoints: now_playing,
  trending, popular, search_movie, movie_details, movie_credits. Auth is
  `Authorization: Bearer <read token>` against `api.themoviedb.org/3`.
  `financials()` surfaces the free budget and revenue fields, and
  `top_grossing_now_playing()` ranks now-playing titles by revenue.
* Showtimes provider (`boxoffice/providers/showtimes.py`). SeatGeekProvider
  implements the free SeatGeek Discovery API: `GET /2/events` with title,
  date, and zip or lat/lon filters. Availability is always recorded as
  unknown because SeatGeek publishes no seat counts.
* Grosses provider (`boxoffice/providers/grosses.py`). TMDBRevenueProvider
  resolves a title and reads the free revenue field from movie_details as a
  worldwide lifetime baseline.
* SQLite snapshot store (`boxoffice/storage.py`). Tables for movies
  (with budget, revenue, rating), showtime snapshots, availability
  snapshots, and grosses.
* CLI (`boxoffice/cli.py`). `snapshot-now-playing` pulls TMDB and stores
  budget, revenue, and rating per movie. `snapshot-showtimes` and
  `snapshot-grosses` use the free providers. `build-dashboard` generates
  the static dashboard. `show` prints recent snapshots.
* Dashboard (`boxoffice/dashboard.py`). Generates a single self-contained
  `docs/index.html`: dark cinematic theme, glassmorphism cards, gradient
  accents, entrance animations, responsive grid, TMDB posters, live search
  filter, animated stat counters, budget vs revenue bars, and an
  availability panel. All data is embedded as JSON. No backend needed.

## Dashboard

Build it and open it:

```bash
python -m boxoffice.cli build-dashboard              # live TMDB data
python -m boxoffice.cli build-dashboard --offline    # local db only
python -m boxoffice.cli build-dashboard --sample     # design preview
```

Then open `docs/index.html` in a browser. The `--sample` build seeds
widely reported figures for eight famous titles and labels the page as a
design preview, so you can see the full layout before the first live run.

GitHub Pages (free hosting): repo Settings > Pages > Deploy from a branch,
choose `main` and the `/docs` folder. Every push that rebuilds
`docs/index.html` updates the site.

The dashboard carries the required TMDB attribution: "This product uses
the TMDB API but is not endorsed or certified by TMDB."

## Honest data-source matrix (free tier)

| Data | Source | Status |
|---|---|---|
| Movie metadata (titles, posters, ratings, release dates) | TMDB | Working |
| Budget and revenue figures | TMDB movie_details fields | Working. Lifetime reported figures, not daily tracking. 0 means unknown |
| Showtimes (theater, time, booking link) | SeatGeek Discovery API | Working on the free tier. Movie coverage is spotty and region dependent |
| Exact seats-booked counts | No public source | Not available. Theaters do not publish this. Track sold-out and availability snapshots as a demand proxy instead |
| Daily and weekend grosses | Box Office Mojo, The Numbers | Neither has an official free API. Needs a licensed feed or permitted collection. TMDB revenue is the free baseline |

Paid upgrades stay documented as stubs: SerpApi Google Movies and
International Showtimes for showtimes, BoxOfficeMojoProvider for grosses.

## Setup

1. Get a TMDB API read access token from your TMDB account settings.
2. Store it in the Secure Vault as `custom.tmdb`. It is never committed.
3. Export it at runtime before running:

```bash
export TMDB_READ_TOKEN=...   # from the vault, not from a file
python -m boxoffice.cli snapshot-now-playing --region US
python -m boxoffice.cli build-dashboard
```

Optional: a free SeatGeek client ID from https://platform.seatgeek.com,
exported as `SEATGEEK_CLIENT_ID`, raises the showtimes rate limit.

Copy `.env.example` to `.env` for local defaults if you want. The `.env`
file is gitignored. Real tokens never go in it in this repo.

Run the tests:

```bash
pip install -r requirements.txt
python -m pytest
```

## Roadmap

1. Daily cron: snapshot now-playing movies plus SeatGeek showtimes for
   tracked titles and locations.
2. Demand view: sold-out rate per movie per day from the snapshots.
3. Wire a licensed or permitted grosses feed and join it with demand.
4. Per-movie detail pages in the dashboard (cast, similar titles).
5. Optional paid upgrades: SerpApi or International Showtimes for denser
   showtime coverage.
