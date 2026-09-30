"""Mocked tests for dashboard generation. No network calls."""

import json
import re

from boxoffice import dashboard, storage


def _seed_db(tmp_path):
    db = tmp_path / "dash.db"
    conn = storage.connect(db)
    storage.upsert_movie(
        conn, tmdb_id=550, title="Fight Club", release_date="1999-10-15",
        overview="An office worker forms a fight club.", poster_path="/p.jpg",
        budget=63000000, revenue=100853753, rating=8.4,
    )
    storage.upsert_movie(
        conn, tmdb_id=551, title="Mystery Film", release_date="2026-01-01",
        overview="No figures known.", poster_path=None,
        budget=0, revenue=0, rating=0,
    )
    conn.commit()
    conn.close()
    return db


def test_build_dashboard_offline_writes_html(tmp_path):
    db = _seed_db(tmp_path)
    out = tmp_path / "index.html"
    path = dashboard.build_dashboard(db_path=db, out=out, offline=True)
    text = path.read_text(encoding="utf-8")
    assert "Fight Club" in text
    assert "Mystery Film" in text
    # Required TMDB attribution is present.
    assert "not endorsed or certified by TMDB" in text
    # Poster image host is used.
    assert "image.tmdb.org" in text
    # Embedded JSON payload parses (HTML-unescaped, as a browser would read
    # it via textContent) and carries the stats.
    import html as html_lib

    m = re.search(
        r'<script id="payload" type="application/json">(.*?)</script>',
        text, re.DOTALL,
    )
    payload = json.loads(html_lib.unescape(m.group(1)))
    assert payload["stats"]["now_playing"] == 2
    assert payload["now_playing"][0]["title"] == "Fight Club"
    # No em-dashes in user-facing text.
    assert "\u2014" not in text


def test_money_formats():
    assert dashboard.money(1500000000) == "$1.5B"
    assert dashboard.money(340000000) == "$340M"
    assert dashboard.money(12000) == "$12K"
    assert dashboard.money(0) == "n/a"
    assert dashboard.money(None) == "n/a"


def test_dashboard_escapes_titles(tmp_path):
    db = tmp_path / "x.db"
    conn = storage.connect(db)
    storage.upsert_movie(
        conn, tmdb_id=9, title='<script>alert("x")</script>',
        release_date="2026-01-01",
    )
    conn.commit()
    conn.close()
    out = tmp_path / "index.html"
    dashboard.build_dashboard(db_path=db, out=out, offline=True)
    text = out.read_text(encoding="utf-8")
    assert "<script>alert" not in text
