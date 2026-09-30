"""SQLite snapshot store.

Demand is tracked over time: each run writes timestamped snapshots of
movies, showtimes, availability, and grosses. Later analysis reads the
history back out.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from boxoffice import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY,
    tmdb_id INTEGER UNIQUE,
    title TEXT NOT NULL,
    release_date TEXT,
    overview TEXT,
    poster_path TEXT,
    budget INTEGER,
    revenue INTEGER,
    rating REAL,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS showtime_snapshots (
    id INTEGER PRIMARY KEY,
    captured_at TEXT NOT NULL DEFAULT (datetime('now')),
    movie_id INTEGER NOT NULL REFERENCES movies(id),
    theater TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    screen TEXT,
    booking_url TEXT,
    availability TEXT NOT NULL DEFAULT 'unknown',
    provider TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS availability_snapshots (
    id INTEGER PRIMARY KEY,
    captured_at TEXT NOT NULL DEFAULT (datetime('now')),
    movie_id INTEGER NOT NULL REFERENCES movies(id),
    theater TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    seats_available INTEGER,
    seats_total INTEGER,
    status TEXT NOT NULL DEFAULT 'unknown',
    provider TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS grosses (
    id INTEGER PRIMARY KEY,
    captured_at TEXT NOT NULL DEFAULT (datetime('now')),
    movie_id INTEGER NOT NULL REFERENCES movies(id),
    date TEXT NOT NULL,
    period TEXT NOT NULL,
    gross_usd INTEGER NOT NULL,
    region TEXT NOT NULL DEFAULT 'domestic',
    source TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_showtimes_movie
    ON showtime_snapshots(movie_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_availability_movie
    ON availability_snapshots(movie_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_grosses_movie
    ON grosses(movie_id, date);
"""


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or config.DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA foreign_keys = ON")
    # Migrate databases created before budget/revenue/rating existed.
    for column, coltype in (
        ("budget", "INTEGER"),
        ("revenue", "INTEGER"),
        ("rating", "REAL"),
    ):
        try:
            conn.execute(f"ALTER TABLE movies ADD COLUMN {column} {coltype}")
        except sqlite3.OperationalError:
            pass  # column already there
    return conn


def upsert_movie(conn: sqlite3.Connection, tmdb_id: int, **fields) -> int:
    """Insert or update a movie. Returns the local row id."""
    conn.execute(
        """
        INSERT INTO movies
            (tmdb_id, title, release_date, overview, poster_path,
             budget, revenue, rating)
        VALUES
            (:tmdb_id, :title, :release_date, :overview, :poster_path,
             :budget, :revenue, :rating)
        ON CONFLICT(tmdb_id) DO UPDATE SET
            title = excluded.title,
            release_date = excluded.release_date,
            overview = excluded.overview,
            poster_path = excluded.poster_path,
            budget = excluded.budget,
            revenue = excluded.revenue,
            rating = excluded.rating
        """,
        {
            "tmdb_id": tmdb_id,
            "title": fields.get("title", ""),
            "release_date": fields.get("release_date"),
            "overview": fields.get("overview"),
            "poster_path": fields.get("poster_path"),
            "budget": fields.get("budget"),
            "revenue": fields.get("revenue"),
            "rating": fields.get("rating"),
        },
    )
    row = conn.execute(
        "SELECT id FROM movies WHERE tmdb_id = ?", (tmdb_id,)
    ).fetchone()
    return row["id"]


def record_showtimes(
    conn: sqlite3.Connection, movie_row_id: int, showtimes, provider: str
) -> int:
    count = 0
    for s in showtimes:
        conn.execute(
            """
            INSERT INTO showtime_snapshots
                (movie_id, theater, starts_at, screen, booking_url,
                 availability, provider)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                movie_row_id,
                s.theater,
                s.starts_at,
                s.screen,
                s.booking_url,
                s.availability,
                provider,
            ),
        )
        count += 1
    return count


def record_availability(
    conn: sqlite3.Connection, movie_row_id: int, records, provider: str
) -> int:
    """records: iterable of (theater, starts_at, seats_available, seats_total, status)."""
    count = 0
    for theater, starts_at, available, total, status in records:
        conn.execute(
            """
            INSERT INTO availability_snapshots
                (movie_id, theater, starts_at, seats_available,
                 seats_total, status, provider)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (movie_row_id, theater, starts_at, available, total, status, provider),
        )
        count += 1
    return count


def record_grosses(
    conn: sqlite3.Connection, movie_row_id: int, records
) -> int:
    """records: iterable of GrossRecord."""
    count = 0
    for g in records:
        conn.execute(
            """
            INSERT INTO grosses
                (movie_id, date, period, gross_usd, region, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                movie_row_id,
                g.date,
                g.period,
                g.gross_usd,
                g.region,
                g.source or "unknown",
            ),
        )
        count += 1
    return count


def recent_snapshots(conn: sqlite3.Connection, table: str, limit: int = 20):
    allowed = {"showtime_snapshots", "availability_snapshots", "grosses"}
    if table not in allowed:
        raise ValueError(f"unknown snapshot table: {table}")
    return conn.execute(
        f"SELECT * FROM {table} ORDER BY captured_at DESC LIMIT ?", (limit,)
    ).fetchall()
