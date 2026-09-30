"""Static dashboard generator.

`build_dashboard` collects data (live from TMDB, or from the local SQLite
store with --offline) and writes a single self-contained HTML page into
docs/ so GitHub Pages can serve it for free. All data is embedded as JSON
in the page. No backend, no build step, works from file:// too.
"""

from __future__ import annotations

import datetime
import html
import json
from pathlib import Path

from boxoffice import config, storage

ATTRIBUTION = (
    "This product uses the TMDB API but is not endorsed or certified by TMDB."
)

# Widely reported figures, used only for the --sample design preview.
# Clearly labeled as sample data on the page. Never presented as live data.
SAMPLE_MOVIES = [
    {"tmdb_id": 693134, "title": "Dune: Part Two", "release_date": "2024-03-01",
     "overview": "Paul Atreides unites with the Fremen for war against House Harkonnen.",
     "budget": 190_000_000, "revenue": 714_000_000, "rating": 8.2},
    {"tmdb_id": 872585, "title": "Oppenheimer", "release_date": "2023-07-19",
     "overview": "The story of J. Robert Oppenheimer and the atomic bomb.",
     "budget": 100_000_000, "revenue": 976_000_000, "rating": 8.1},
    {"tmdb_id": 346698, "title": "Barbie", "release_date": "2023-07-19",
     "overview": "Barbie leaves Barbie Land for the real world.",
     "budget": 145_000_000, "revenue": 1_446_000_000, "rating": 7.0},
    {"tmdb_id": 634649, "title": "Spider-Man: No Way Home", "release_date": "2021-12-15",
     "overview": "Peter Parker seeks Doctor Strange's help as villains return.",
     "budget": 200_000_000, "revenue": 1_922_000_000, "rating": 8.0},
    {"tmdb_id": 76600, "title": "Avatar: The Way of Water", "release_date": "2022-12-14",
     "overview": "Jake Sully and Neytiri protect their family on Pandora.",
     "budget": 250_000_000, "revenue": 2_320_000_000, "rating": 7.6},
    {"tmdb_id": 361743, "title": "Top Gun: Maverick", "release_date": "2022-05-24",
     "overview": "Maverick trains a new generation of Top Gun graduates.",
     "budget": 170_000_000, "revenue": 1_495_000_000, "rating": 8.2},
    {"tmdb_id": 414906, "title": "The Batman", "release_date": "2022-03-01",
     "overview": "Batman uncovers corruption in Gotham City.",
     "budget": 200_000_000, "revenue": 772_000_000, "rating": 7.7},
    {"tmdb_id": 545611, "title": "Everything Everywhere All at Once",
     "release_date": "2022-03-24",
     "overview": "A laundromat owner must save the multiverse.",
     "budget": 25_000_000, "revenue": 143_000_000, "rating": 7.8},
]


def seed_sample(conn) -> int:
    """Insert sample movies for a design preview. Returns count."""
    for m in SAMPLE_MOVIES:
        storage.upsert_movie(
            conn,
            tmdb_id=m["tmdb_id"],
            title=m["title"],
            release_date=m["release_date"],
            overview=m["overview"],
            poster_path=None,
            budget=m["budget"],
            revenue=m["revenue"],
            rating=m["rating"],
        )
    conn.commit()
    return len(SAMPLE_MOVIES)


def money(value) -> str:
    """Format dollars compactly: 1.2B, 340M, 12K, or n/a when unknown."""
    if not value:
        return "n/a"
    v = float(value)
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if v >= div:
            s = f"{v / div:.1f}".rstrip("0").rstrip(".")
            return f"${s}{unit}"
    return f"${int(v):,}"


def _movie_dict(row) -> dict:
    return {
        "title": row["title"] or "",
        "release_date": row["release_date"] or "",
        "rating": row["rating"] or 0,
        "poster": config.tmdb_image_url(row["poster_path"], "w342"),
        "revenue": row["revenue"] or 0,
        "budget": row["budget"] or 0,
        "overview": (row["overview"] or "")[:220],
    }


def collect(db_path=None, offline: bool = False, sample: bool = False) -> dict:
    """Gather everything the dashboard needs. Live TMDB unless offline.

    sample=True seeds widely reported figures for a design preview and
    flags the payload so the page labels it as sample data.
    """
    conn = storage.connect(db_path)
    now_playing: list[dict] = []
    trending: list[dict] = []

    if sample:
        seed_sample(conn)

    if not offline:
        from boxoffice.providers.tmdb import TMDBClient

        client = TMDBClient()
        ranked = client.top_grossing_now_playing(limit=20)
        ids = []
        for m in ranked:
            storage.upsert_movie(
                conn,
                tmdb_id=m["id"],
                title=m.get("title", ""),
                release_date=m.get("release_date"),
                overview=m.get("overview"),
                poster_path=m.get("poster_path"),
                budget=m.get("budget"),
                revenue=m.get("revenue"),
                rating=m.get("vote_average"),
            )
            ids.append(m["id"])
        conn.commit()
        rows = [
            conn.execute(
                "SELECT * FROM movies WHERE tmdb_id = ?", (i,)
            ).fetchone()
            for i in ids
        ]
        now_playing = [_movie_dict(r) for r in rows if r]
        for t in client.trending("movie", "week").get("results", [])[:12]:
            trending.append(
                {
                    "title": t.get("title") or t.get("name") or "",
                    "rating": round(t.get("vote_average") or 0, 1),
                    "poster": config.tmdb_image_url(
                        t.get("poster_path"), "w342"
                    ),
                }
            )
    else:
        rows = conn.execute(
            "SELECT * FROM movies ORDER BY first_seen_at DESC LIMIT 20"
        ).fetchall()
        now_playing = [_movie_dict(r) for r in rows]
    all_rows = conn.execute("SELECT * FROM movies").fetchall()
    ratings = [r["rating"] for r in all_rows if r["rating"]]
    total_revenue = sum(r["revenue"] or 0 for r in all_rows)

    top = sorted(now_playing, key=lambda m: m["revenue"], reverse=True)[:8]
    bars = [m for m in top if m["budget"] or m["revenue"]]

    show_counts = {
        r["availability"]: r["c"]
        for r in conn.execute(
            "SELECT availability, COUNT(*) c FROM showtime_snapshots "
            "GROUP BY availability"
        ).fetchall()
    }
    avail_counts = {
        r["status"]: r["c"]
        for r in conn.execute(
            "SELECT status, COUNT(*) c FROM availability_snapshots "
            "GROUP BY status"
        ).fetchall()
    }
    conn.close()

    return {
        "generated_at": datetime.datetime.now(
            datetime.timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC"),
        "sample": sample,
        "stats": {
            "now_playing": len(now_playing),
            "trending": len(trending),
            "avg_rating": round(sum(ratings) / len(ratings), 1) if ratings else 0,
            "total_revenue": total_revenue,
        },
        "now_playing": now_playing,
        "trending": trending,
        "bars": bars,
        "show_counts": show_counts,
        "avail_counts": avail_counts,
    }


def _poster_card(m: dict, i: int) -> str:
    title = html.escape(m["title"])
    search = html.escape((m["title"] + " " + m["overview"]).lower())
    poster = m["poster"]
    if poster:
        img = (
            f'<img class="poster" src="{html.escape(poster)}" '
            f'alt="{title} poster" loading="lazy">'
        )
    else:
        img = f'<div class="poster poster-fallback">{title}</div>'
    rating = f'{m["rating"]:.1f}' if m["rating"] else "n/a"
    return f"""
    <article class="movie-card rise" style="animation-delay:{i * 45}ms"
             data-search="{search}">
      <div class="poster-wrap">{img}
        <span class="rating-badge">{rating}</span>
      </div>
      <div class="card-body">
        <h3>{title}</h3>
        <p class="muted">{html.escape(m["release_date"] or "date tbd")}</p>
        <p class="money">Revenue <strong>{money(m["revenue"])}</strong></p>
      </div>
    </article>"""


def _trend_chip(t: dict, i: int) -> str:
    title = html.escape(t["title"])
    poster = t["poster"]
    img = (
        f'<img src="{html.escape(poster)}" alt="{title} poster" loading="lazy">'
        if poster
        else f'<div class="chip-fallback">{title}</div>'
    )
    return f"""
    <div class="trend-chip rise" style="animation-delay:{i * 40}ms">
      {img}
      <div class="chip-body"><strong>{title}</strong>
      <span class="muted">{t["rating"]:.1f} rating</span></div>
    </div>"""


def _bar_row(m: dict, i: int, scale: float) -> str:
    title = html.escape(m["title"])
    bw = (m["budget"] / scale * 100) if scale else 0
    rw = (m["revenue"] / scale * 100) if scale else 0
    return f"""
    <div class="bar-row rise" style="animation-delay:{i * 60}ms">
      <div class="bar-label">{title}</div>
      <div class="bar-lines">
        <div class="bar-line"><span class="bar-tag">Budget</span>
          <div class="track"><div class="fill budget" data-w="{bw:.1f}"></div></div>
          <span class="bar-val">{money(m["budget"])}</span></div>
        <div class="bar-line"><span class="bar-tag">Revenue</span>
          <div class="track"><div class="fill revenue" data-w="{rw:.1f}"></div></div>
          <span class="bar-val">{money(m["revenue"])}</span></div>
      </div>
    </div>"""


def render(data: dict) -> str:
    """Render the full dashboard HTML from collected data."""
    s = data["stats"]
    cards = "\n".join(_poster_card(m, i) for i, m in enumerate(data["now_playing"]))
    if not cards:
        cards = (
            '<p class="muted empty">No movies stored yet. Run '
            "<code>snapshot-now-playing</code> or rebuild without --offline.</p>"
        )
    chips = "\n".join(_trend_chip(t, i) for i, t in enumerate(data["trending"]))
    if not chips:
        chips = '<p class="muted empty">Trending needs a live TMDB fetch.</p>'

    scale = max(
        [max(m["budget"], m["revenue"]) for m in data["bars"]] or [1]
    )
    bars = "\n".join(_bar_row(m, i, scale) for i, m in enumerate(data["bars"]))
    if not bars:
        bars = (
            '<p class="muted empty">Budget and revenue figures are still '
            "loading for these titles.</p>"
        )

    counts = {**data["show_counts"], **data["avail_counts"]}
    if counts:
        pills = "\n".join(
            f'<span class="pill">{html.escape(k)}: <strong>{v}</strong></span>'
            for k, v in sorted(counts.items())
        )
    else:
        pills = (
            '<p class="muted empty">No availability snapshots yet. Theaters do '
            "not publish seat counts, so this panel tracks sold out and "
            "availability signals over time once snapshots exist.</p>"
        )

    payload = html.escape(json.dumps(data))
    banner = ""
    if data.get("sample"):
        banner = (
            '<div class="sample-banner">Sample data for design preview. '
            "Rebuild without --sample for live figures.</div>"
        )
    return PAGE.replace("__CARDS__", cards).replace("__CHIPS__", chips).replace(
        "__BARS__", bars
    ).replace("__PILLS__", pills).replace("__PAYLOAD__", payload).replace(
        "__GENERATED__", html.escape(data["generated_at"])
    ).replace("__SAMPLE_BANNER__", banner).replace(
        "__STAT_NOW__", str(s["now_playing"])
    ).replace(
        "__STAT_TREND__", str(s["trending"])
    ).replace(
        "__STAT_RATING__", f'{s["avg_rating"]:.1f}'
    ).replace(
        "__STAT_REVENUE__", money(s["total_revenue"])
    ).replace(
        "__ATTRIBUTION__", html.escape(ATTRIBUTION)
    )


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Box Office Tracker</title>
<style>
:root{
  --bg0:#070b16; --bg1:#0d1428;
  --card:rgba(255,255,255,.045); --border:rgba(255,255,255,.09);
  --text:#eef2ff; --muted:#9aa4c0;
  --gold:#f5c518; --violet:#8b5cf6; --cyan:#22d3ee;
  --radius:18px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{
  font-family:-apple-system,BlinkMacSystemFont,"Inter","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:var(--text); min-height:100vh;
  background:
    radial-gradient(900px 480px at 12% -8%, rgba(139,92,246,.22), transparent 60%),
    radial-gradient(800px 420px at 88% 4%, rgba(34,211,238,.14), transparent 60%),
    radial-gradient(700px 500px at 50% 110%, rgba(245,197,24,.08), transparent 60%),
    linear-gradient(180deg,var(--bg1),var(--bg0));
  padding:0 20px 60px;
}
.wrap{max-width:1180px;margin:0 auto}
.hero{padding:64px 0 10px;text-align:center}
.hero .kicker{letter-spacing:.35em;text-transform:uppercase;font-size:12px;color:var(--cyan)}
.sample-banner{display:inline-block;margin-top:14px;padding:8px 18px;border-radius:999px;
  background:rgba(245,197,24,.12);border:1px solid rgba(245,197,24,.45);color:var(--gold);
  font-size:.85rem;font-weight:600}
.hero h1{font-size:clamp(2.4rem,6vw,4.2rem);font-weight:800;line-height:1.05;margin:14px 0 10px}
.hero h1 .grad{background:linear-gradient(92deg,var(--gold),#ff8a3d 55%,var(--violet));
  -webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{color:var(--muted);font-size:1.05rem}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:34px 0}
.stat{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:22px;backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  transition:transform .25s ease, box-shadow .25s ease}
.stat:hover{transform:translateY(-4px);box-shadow:0 18px 40px rgba(0,0,0,.45)}
.stat .num{font-size:2rem;font-weight:800}
.stat .num.gold{color:var(--gold)} .stat .num.cyan{color:var(--cyan)}
.stat .lbl{color:var(--muted);font-size:.85rem;margin-top:6px;text-transform:uppercase;letter-spacing:.12em}
section{margin:44px 0}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin-bottom:18px}
.sec-head h2{font-size:1.5rem;font-weight:750}
.sec-head .muted{font-size:.9rem}
.muted{color:var(--muted)} .empty{padding:26px;text-align:center}
.search{width:100%;max-width:420px;padding:12px 18px;border-radius:999px;
  background:rgba(255,255,255,.06);border:1px solid var(--border);color:var(--text);
  font-size:1rem;outline:none;transition:border-color .2s, box-shadow .2s}
.search:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(34,211,238,.18)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:18px}
.movie-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  overflow:hidden;backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  transition:transform .28s ease, box-shadow .28s ease, border-color .28s ease}
.movie-card:hover{transform:translateY(-8px) scale(1.015);
  box-shadow:0 24px 55px rgba(0,0,0,.55), 0 0 0 1px rgba(245,197,24,.25);
  border-color:rgba(245,197,24,.35)}
.poster-wrap{position:relative;aspect-ratio:2/3;background:#141b33;overflow:hidden}
.poster{width:100%;height:100%;object-fit:cover;display:block;transition:transform .4s ease}
.movie-card:hover .poster{transform:scale(1.06)}
.poster-fallback{display:flex;align-items:center;justify-content:center;height:100%;
  padding:20px;text-align:center;color:var(--muted);font-weight:700}
.rating-badge{position:absolute;top:10px;left:10px;background:rgba(7,11,22,.82);
  border:1px solid rgba(245,197,24,.55);color:var(--gold);font-weight:800;font-size:.85rem;
  padding:5px 10px;border-radius:999px;backdrop-filter:blur(6px)}
.card-body{padding:14px 14px 16px}
.card-body h3{font-size:1rem;font-weight:700;line-height:1.3;margin-bottom:6px}
.card-body .muted{font-size:.82rem}
.card-body .money{margin-top:8px;font-size:.85rem;color:var(--muted)}
.card-body .money strong{color:var(--gold)}
.strip{display:flex;gap:14px;overflow-x:auto;padding:6px 2px 16px;scroll-snap-type:x mandatory}
.strip::-webkit-scrollbar{height:8px}
.strip::-webkit-scrollbar-thumb{background:rgba(255,255,255,.14);border-radius:99px}
.trend-chip{flex:0 0 300px;display:flex;gap:12px;align-items:center;
  background:var(--card);border:1px solid var(--border);border-radius:14px;padding:10px;
  scroll-snap-align:start;backdrop-filter:blur(12px);
  transition:transform .25s ease, border-color .25s ease}
.trend-chip:hover{transform:translateY(-4px);border-color:rgba(34,211,238,.4)}
.trend-chip img{width:56px;height:84px;object-fit:cover;border-radius:8px}
.chip-fallback{width:56px;height:84px;border-radius:8px;background:#1a2340;
  display:flex;align-items:center;justify-content:center;font-size:.6rem;color:var(--muted);
  text-align:center;padding:4px}
.chip-body strong{display:block;font-size:.92rem;margin-bottom:4px}
.chip-body .muted{font-size:.8rem}
.bar-row{background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:16px 18px;margin-bottom:12px;backdrop-filter:blur(12px)}
.bar-label{font-weight:700;margin-bottom:10px}
.bar-line{display:grid;grid-template-columns:64px 1fr 76px;align-items:center;gap:10px;margin:7px 0}
.bar-tag{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.track{height:10px;border-radius:99px;background:rgba(255,255,255,.08);overflow:hidden}
.fill{height:100%;width:0;border-radius:99px;transition:width 1.1s cubic-bezier(.2,.7,.2,1)}
.fill.budget{background:linear-gradient(90deg,#6d28d9,var(--violet))}
.fill.revenue{background:linear-gradient(90deg,#b98a12,var(--gold))}
.bar-val{font-size:.85rem;font-weight:700;text-align:right}
.panel{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:24px;backdrop-filter:blur(14px)}
.pill{display:inline-block;margin:6px 8px 6px 0;padding:9px 16px;border-radius:999px;
  background:rgba(255,255,255,.06);border:1px solid var(--border);font-size:.9rem}
.pill strong{color:var(--cyan)}
footer{margin-top:56px;text-align:center;color:var(--muted);font-size:.82rem;line-height:1.7}
@keyframes rise{from{opacity:0;transform:translateY(26px)}to{opacity:1;transform:none}}
.rise{animation:rise .65s cubic-bezier(.2,.7,.2,1) both}
@media (max-width:680px){
  .stats{grid-template-columns:repeat(2,1fr)}
  .bar-line{grid-template-columns:56px 1fr 64px}
  .hero{padding-top:44px}
}
</style>
</head>
<body>
<div class="wrap">

  <header class="hero rise">
    <div class="kicker">Demand tracking</div>
    <h1>Box Office <span class="grad">Tracker</span></h1>
    <p>Now playing, trending, budgets and revenue. Snapshot generated __GENERATED__.</p>
    __SAMPLE_BANNER__
  </header>

  <div class="stats">
    <div class="stat rise" style="animation-delay:60ms">
      <div class="num gold" data-count="__STAT_NOW__">0</div>
      <div class="lbl">Now playing</div>
    </div>
    <div class="stat rise" style="animation-delay:120ms">
      <div class="num cyan" data-count="__STAT_TREND__">0</div>
      <div class="lbl">Trending this week</div>
    </div>
    <div class="stat rise" style="animation-delay:180ms">
      <div class="num" data-count="__STAT_RATING__" data-dec="1">0</div>
      <div class="lbl">Average rating</div>
    </div>
    <div class="stat rise" style="animation-delay:240ms">
      <div class="num gold">__STAT_REVENUE__</div>
      <div class="lbl">Tracked revenue</div>
    </div>
  </div>

  <section>
    <div class="sec-head">
      <h2>Now Playing</h2>
      <input id="search" class="search" type="search"
             placeholder="Filter movies by title" aria-label="Filter movies">
    </div>
    <div class="grid" id="grid">__CARDS__</div>
  </section>

  <section>
    <div class="sec-head"><h2>Trending This Week</h2>
      <span class="muted">TMDB trending movies</span></div>
    <div class="strip">__CHIPS__</div>
  </section>

  <section>
    <div class="sec-head"><h2>Budget vs Revenue</h2>
      <span class="muted">Top titles by reported revenue</span></div>
    __BARS__
  </section>

  <section>
    <div class="sec-head"><h2>Availability Signals</h2>
      <span class="muted">Snapshot counts by status</span></div>
    <div class="panel">__PILLS__</div>
  </section>

  <footer>
    <p>__ATTRIBUTION__</p>
    <p>Poster images via TMDB. Availability is a demand proxy: theaters do not
    publish seat counts. Generated __GENERATED__.</p>
  </footer>

</div>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
// Animated counters
document.querySelectorAll("[data-count]").forEach(function(el){
  var target = parseFloat(el.getAttribute("data-count")) || 0;
  var dec = parseInt(el.getAttribute("data-dec") || "0", 10);
  var start = null, dur = 900;
  function tick(t){
    if(!start) start = t;
    var p = Math.min((t - start) / dur, 1);
    var eased = 1 - Math.pow(1 - p, 3);
    el.textContent = (target * eased).toFixed(dec);
    if(p < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
});
// Bar fills animate on load
requestAnimationFrame(function(){
  requestAnimationFrame(function(){
    document.querySelectorAll(".fill").forEach(function(f){
      f.style.width = f.getAttribute("data-w") + "%";
    });
  });
});
// Live search filter
var input = document.getElementById("search");
input.addEventListener("input", function(){
  var q = input.value.trim().toLowerCase();
  document.querySelectorAll(".movie-card").forEach(function(card){
    var hit = !q || card.getAttribute("data-search").indexOf(q) !== -1;
    card.style.display = hit ? "" : "none";
  });
});
</script>
</body>
</html>
"""


def build_dashboard(
    db_path=None,
    out: str | Path = "docs/index.html",
    offline: bool = False,
    sample: bool = False,
) -> Path:
    """Collect data and write the dashboard HTML. Returns the output path."""
    data = collect(db_path=db_path, offline=offline, sample=sample)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(data), encoding="utf-8")
    return out_path
