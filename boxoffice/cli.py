"""CLI for boxoffice-tracker.

Commands:
  snapshot-now-playing   Pull TMDB now_playing and store movie records.
  snapshot-showtimes     Pull showtimes from SeatGeek (free tier).
  snapshot-grosses       Pull grosses from TMDB revenue data (free).
  build-dashboard        Generate the static dashboard into docs/index.html.
  show                   Print recent snapshots from the SQLite store.
"""

from __future__ import annotations

import argparse
import sys
import time

from boxoffice import config, storage
from boxoffice.dashboard import build_dashboard
from boxoffice.providers.grosses import (
    BoxOfficeMojoProvider,
    GrossesProvider,
    TMDBRevenueProvider,
)
from boxoffice.providers.showtimes import SeatGeekProvider
from boxoffice.providers.tmdb import TMDBClient, all_pages


def cmd_snapshot_now_playing(args) -> int:
    client = TMDBClient()
    movies = all_pages(
        client.now_playing, region=args.region, max_pages=args.pages
    )
    conn = storage.connect(args.db)
    count = 0
    for m in movies:
        budget = revenue = rating = None
        if args.financials:
            try:
                fin = client.financials(m["id"])
                budget, revenue = fin["budget"], fin["revenue"]
                time.sleep(0.3)  # stay under the free-tier rate limit
            except Exception as exc:
                print(f"warning: financials failed for {m['id']}: {exc}",
                      file=sys.stderr)
        rating = m.get("vote_average")
        storage.upsert_movie(
            conn,
            tmdb_id=m["id"],
            title=m.get("title", ""),
            release_date=m.get("release_date"),
            overview=m.get("overview"),
            poster_path=m.get("poster_path"),
            budget=budget,
            revenue=revenue,
            rating=rating,
        )
        count += 1
    conn.commit()
    conn.close()
    print(f"stored {count} now-playing movies in {args.db}")
    return 0


def cmd_snapshot_showtimes(args) -> int:
    provider = SeatGeekProvider()
    try:
        showtimes = provider.search_showtimes(args.movie, args.location, args.date)
    except Exception as exc:
        print(f"showtimes fetch failed: {exc}", file=sys.stderr)
        return 2
    conn = storage.connect(args.db)
    movie_row_id = storage.upsert_movie(
        conn, tmdb_id=0, title=args.movie
    )
    n = storage.record_showtimes(conn, movie_row_id, showtimes, provider.name)
    conn.commit()
    conn.close()
    print(f"stored {n} showtime snapshots in {args.db}")
    return 0


def cmd_snapshot_grosses(args) -> int:
    if args.provider == "boxofficemojo":
        provider: GrossesProvider = BoxOfficeMojoProvider()
    else:
        provider = TMDBRevenueProvider()
    try:
        records = provider.fetch_grosses(args.movie)
    except NotImplementedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    conn = storage.connect(args.db)
    tmdb_id = records[0].movie_id if records else 0
    movie_row_id = storage.upsert_movie(conn, tmdb_id=tmdb_id, title=args.movie)
    n = storage.record_grosses(conn, movie_row_id, records)
    conn.commit()
    conn.close()
    print(f"stored {n} gross records in {args.db} (provider: {provider.name})")
    return 0


def cmd_show(args) -> int:
    conn = storage.connect(args.db)
    rows = storage.recent_snapshots(conn, args.table, args.limit)
    for row in rows:
        print(dict(row))
    conn.close()
    return 0


def cmd_build_dashboard(args) -> int:
    try:
        out = build_dashboard(
            db_path=args.db,
            out=args.out,
            offline=args.offline or args.sample,
            sample=args.sample,
        )
    except RuntimeError as exc:
        # Live mode needs the token; fall back hint when it is missing.
        print(f"dashboard build failed: {exc}", file=sys.stderr)
        return 2
    print(f"dashboard written to {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="boxoffice", description=__doc__)
    parser.add_argument("--db", default=config.DB_PATH,
                        help="SQLite db path (default: boxoffice.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("snapshot-now-playing",
                       help="Store TMDB now_playing movies")
    p.add_argument("--region", default=config.DEFAULT_REGION)
    p.add_argument("--pages", type=int, default=2)
    p.add_argument("--financials", dest="financials", action="store_true",
                   default=True, help="fetch budget/revenue per movie (default)")
    p.add_argument("--no-financials", dest="financials", action="store_false",
                   help="skip per-movie details calls")
    p.set_defaults(func=cmd_snapshot_now_playing)

    p = sub.add_parser("snapshot-showtimes",
                       help="Store showtimes from SeatGeek (free tier)")
    p.add_argument("--movie", required=True)
    p.add_argument("--location", required=True,
                   help="zip code or 'lat,lon'")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.set_defaults(func=cmd_snapshot_showtimes)

    p = sub.add_parser("snapshot-grosses",
                       help="Store grosses from a provider")
    p.add_argument("--movie", required=True)
    p.add_argument("--provider", default="tmdb",
                   choices=["tmdb", "boxofficemojo"],
                   help="tmdb uses the free TMDB revenue field")
    p.set_defaults(func=cmd_snapshot_grosses)

    p = sub.add_parser("build-dashboard",
                       help="Generate the static dashboard into docs/")
    p.add_argument("--out", default="docs/index.html",
                   help="output HTML path (default: docs/index.html)")
    p.add_argument("--offline", action="store_true",
                   help="render from the local db only, no TMDB calls")
    p.add_argument("--sample", action="store_true",
                   help="seed sample figures for a design preview")
    p.set_defaults(func=cmd_build_dashboard)

    p = sub.add_parser("show", help="Print recent snapshots")
    p.add_argument("--table", required=True,
                   choices=["showtime_snapshots", "availability_snapshots",
                            "grosses"])
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
