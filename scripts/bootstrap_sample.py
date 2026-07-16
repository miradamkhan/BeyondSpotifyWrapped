"""Bootstrap a demo database from anonymized sample_data.

This lets anyone clone the repo and explore the dashboard without Spotify
credentials or a personal export. It:
  1. Imports sample_data listens
  2. Seeds synthetic artist genres (no MusicBrainz calls)
  3. Builds genre mix, change points, and track embeddings
  4. Prepares narrative jobs and fills deterministic stub narratives
     (so the UI works without Ollama; replace later with generate_narratives.py)

WARNING: Uses the default local SQLite path under data/ and replaces analytics
tables. Do not run this over a DB you care about without a backup.

Usage:
    python scripts/bootstrap_sample.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import db
from src.change_detection import (
    detect_change_points,
    load_monthly_genre_matrix,
    save_change_points,
)
from src.export_parser import import_export_folder
from src.genre_mix import compute_monthly_genre_mix, save_monthly_genre_mix
from src.narrative_pipeline import prepare_narrative_jobs
from src.significant_moments import (
    detect_significant_moments,
    save_moments_with_neighbors,
)
from src.track_embeddings import run_embedding_pipeline

SAMPLE_ROOT = REPO_ROOT / "sample_data"

ARTIST_GENRES = {
    "Northline Collective": ["indie electronic", "dream pop", "ambient pop"],
    "Juniper Circuit": ["indie pop", "synthpop", "bedroom pop"],
    "Harbor Atlas": ["indie folk", "chamber pop", "acoustic"],
    "Velvet Meter": ["hip hop", "trap", "pop rap"],
    "Cedar Frequency": ["ambient", "downtempo", "electronic"],
    "Marble District": ["pop rap", "rnb", "contemporary r&b"],
    "Paper Lanterns": ["indie folk", "singer-songwriter", "folk pop"],
    "Ozone Room": ["electronic", "house", "dance"],
}


def seed_genres(connection) -> int:
    updated = 0
    for name, genres in ARTIST_GENRES.items():
        cursor = connection.execute(
            """
            UPDATE artists
            SET genres_json = ?, raw_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE name = ?
            """,
            (
                json.dumps(genres),
                json.dumps({"source": "sample_seed", "tags": genres}),
                name,
            ),
        )
        updated += cursor.rowcount
    connection.commit()
    return updated


def stub_narratives(connection) -> int:
    """Fill pending narrative jobs with deterministic demo text."""
    rows = connection.execute(
        """
        SELECT id, job_type, source_key, input_json, output_schema_json
        FROM narrative_jobs
        WHERE status = 'pending'
        """
    ).fetchall()

    for row in rows:
        payload = json.loads(row["input_json"])
        job_type = row["job_type"]
        if job_type == "taste_dna":
            response = {
                "headline": "Synthetic eras of trap-pop into indie electronic",
                "summary": (
                    "This sample archive moves from Velvet Meter / Marble District "
                    "replay density into Juniper Circuit and Paper Lanterns eras, "
                    "with Ozone Room electronic spikes in the middle years."
                ),
                "core_genres": ["hip hop", "indie pop", "electronic", "indie folk"],
                "core_artists": list(ARTIST_GENRES.keys())[:5],
                "major_shift_months": payload.get("major_shift_months", []),
            }
        elif job_type == "change_point":
            month = payload.get("change_month", row["source_key"])
            deltas = payload.get("largest_genre_deltas", [])[:3]
            delta_text = ", ".join(
                f"{d['genre']} {d['before_pct']}%→{d['after_pct']}%" for d in deltas
            ) or "genre shares rebalanced"
            response = {
                "title": f"Sample shift around {month}",
                "date_range": f"{payload.get('before_period')} → {payload.get('after_period')}",
                "narrative": (
                    f"Measured listening mix changed near {month}. "
                    f"Largest deltas: {delta_text}."
                ),
                "referenced_genres": [d["genre"] for d in deltas],
                "referenced_tracks": [
                    t.get("track", "") for t in payload.get("top_tracks_after", [])[:3]
                ],
            }
        elif job_type == "cluster_label":
            tracks = payload.get("representative_tracks", [])
            genres = payload.get("representative_genres", [])
            label = genres[0]["genre"] if genres else f"Cluster {payload.get('cluster_id')}"
            response = {
                "label": str(label).title(),
                "description": (
                    f"Sample cluster with {payload.get('track_count', 0)} tracks "
                    f"anchored by metadata neighbors."
                ),
                "representative_tracks": [
                    t.get("track", "") for t in tracks[:5] if t.get("track")
                ],
                "representative_artists": [
                    t.get("artists", "") for t in tracks[:5] if t.get("artists")
                ],
            }
        else:  # significant_moment
            response = {
                "title": f"Replay pocket: {payload.get('track', 'Unknown')}",
                "month": payload.get("month", ""),
                "note": (
                    f"{payload.get('track')} by {payload.get('artists')} logged "
                    f"{payload.get('play_count')} plays ({payload.get('listening_hours')}h)."
                ),
                "sounds_like": [
                    f"{n.get('track')} — {n.get('artists')}"
                    for n in payload.get("cross_era_neighbors", [])[:5]
                ],
            }

        connection.execute(
            """
            UPDATE narrative_jobs
            SET status = 'completed',
                model = 'sample-stub',
                response_json = ?,
                error = NULL,
                generated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(response), row["id"]),
        )

    connection.commit()
    return len(rows)


def main() -> None:
    if not SAMPLE_ROOT.exists():
        raise SystemExit(
            "sample_data/ missing. Run: python scripts/generate_sample_data.py"
        )

    print("Initializing database…")
    db.init_db()
    connection = db.connect()
    try:
        # Fresh demo analytics: clear listens/tracks so sample is clean.
        connection.executescript(
            """
            DELETE FROM moment_neighbors;
            DELETE FROM significant_moments;
            DELETE FROM narrative_jobs;
            DELETE FROM track_analysis;
            DELETE FROM change_points;
            DELETE FROM monthly_genre_mix;
            DELETE FROM listen_events;
            DELETE FROM track_artists;
            DELETE FROM tracks;
            DELETE FROM artists;
            """
        )
        connection.commit()

        print("Importing sample_data…")
        stats = import_export_folder(SAMPLE_ROOT, connection=connection)
        print(
            f"  files={stats['files']} inserted={stats['inserted']} "
            f"skipped={stats['skipped']}"
        )

        print("Seeding synthetic genres…")
        print(f"  artists updated={seed_genres(connection)}")

        print("Building monthly genre mix…")
        mix = compute_monthly_genre_mix(connection)
        save_monthly_genre_mix(connection, mix)
        print(f"  rows={len(mix)}")

        print("Detecting change points…")
        matrix = load_monthly_genre_matrix(connection)
        points = detect_change_points(matrix)
        save_change_points(connection, points)
        print(f"  points={len(points)}")

        print("Embedding + clustering tracks…")
        emb = run_embedding_pipeline(connection)
        print(f"  tracks={emb['tracks']} clusters={emb['clusters']}")

        print("Preparing significant moments + narrative jobs…")
        moments = detect_significant_moments(connection, min_plays=5)
        save_moments_with_neighbors(connection, moments)
        job_counts = prepare_narrative_jobs(connection)
        print(f"  moments={len(moments)} jobs={job_counts}")

        print("Writing stub narratives for demo UI…")
        print(f"  stubbed={stub_narratives(connection)}")
    finally:
        connection.close()

    print(
        "\nSample bootstrap complete.\n"
        "Next:\n"
        "  python scripts/run_api.py\n"
        "  cd frontend && npm install && npm run dev\n"
        "Optional real LLM text:\n"
        "  python scripts/generate_narratives.py --retry-failed\n"
        "  (or delete completed sample stubs and regenerate)"
    )


if __name__ == "__main__":
    main()
