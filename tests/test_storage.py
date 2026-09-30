"""Mocked tests for the SQLite storage layer."""

import tempfile
from pathlib import Path

from boxoffice import storage


def make_db():
    path = Path(tempfile.mkdtemp()) / "test.db"
    return storage.connect(path)


def test_upsert_movie_insert_and_update():
    conn = make_db()
    row_id = storage.upsert_movie(conn, tmdb_id=11, title="A")
    row_id2 = storage.upsert_movie(conn, tmdb_id=11, title="B")
    assert row_id == row_id2
    row = conn.execute("SELECT title FROM movies").fetchone()
    assert row["title"] == "B"
    conn.close()


def test_record_grosses_round_trip():
    from boxoffice.providers.grosses import GrossRecord

    conn = make_db()
    row_id = storage.upsert_movie(conn, tmdb_id=22, title="C")
    records = [
        GrossRecord(
            movie_id=22, movie_title="C", date="2026-09-30",
            period="weekend", gross_usd=1000000, region="domestic",
            source="test",
        )
    ]
    n = storage.record_grosses(conn, row_id, records)
    assert n == 1
    rows = storage.recent_snapshots(conn, "grosses")
    assert rows[0]["gross_usd"] == 1000000
    conn.close()
