"""Prepare grounded, provider-neutral LLM narrative jobs."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

BASE_RULES = """
Use only the supplied analytical facts. Do not infer moods, life events,
personality traits, or causes that are not present in the data.
Reference concrete artists, tracks, genres, counts, percentages, and dates.
Avoid vague claims such as "your taste evolved" unless immediately supported
by a specific before/after example. Return only JSON matching the schema.
""".strip()

CHANGE_SCHEMA = {
    "title": "string",
    "date_range": "string",
    "narrative": "string",
    "referenced_genres": ["string"],
    "referenced_tracks": ["string"],
}

CLUSTER_SCHEMA = {
    "label": "string",
    "description": "string",
    "representative_tracks": ["string"],
    "representative_artists": ["string"],
}

MOMENT_SCHEMA = {
    "title": "string",
    "month": "YYYY-MM",
    "note": "string",
    "sounds_like": ["string"],
}

TASTE_DNA_SCHEMA = {
    "headline": "string",
    "summary": "string",
    "core_genres": ["string"],
    "core_artists": ["string"],
    "major_shift_months": ["YYYY-MM"],
}


def prepare_narrative_jobs(connection: sqlite3.Connection) -> dict[str, int]:
    """Create/update every narrative input without calling a model."""
    # Pending jobs are reproducible derived data. Rebuild them so removed or
    # re-ranked source moments cannot leave stale jobs behind.
    connection.execute("DELETE FROM narrative_jobs WHERE status != 'completed'")
    counts = {
        "change_point": _prepare_change_jobs(connection),
        "cluster_label": _prepare_cluster_jobs(connection),
        "significant_moment": _prepare_moment_jobs(connection),
        "taste_dna": _prepare_taste_dna_job(connection),
    }
    connection.commit()
    return counts


def _prepare_change_jobs(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        """
        SELECT id, month, score, before_summary_json, after_summary_json
        FROM change_points
        ORDER BY month
        """
    ).fetchall()
    for row in rows:
        before = json.loads(row["before_summary_json"])
        after = json.loads(row["after_summary_json"])
        payload = {
            "change_month": row["month"],
            "change_score": round(row["score"], 4),
            "before_period": f"{_shift_month(row['month'], -6)} to {_shift_month(row['month'], -1)}",
            "after_period": f"{row['month']} to {_shift_month(row['month'], 5)}",
            "genre_percentages_before": _percentages(before),
            "genre_percentages_after": _percentages(after),
            "largest_genre_deltas": _genre_deltas(before, after),
            "top_tracks_before": _top_tracks(
                connection, _shift_month(row["month"], -6), row["month"]
            ),
            "top_tracks_after": _top_tracks(
                connection, row["month"], _shift_month(row["month"], 6)
            ),
        }
        _upsert_job(
            connection,
            job_type="change_point",
            source_key=row["month"],
            payload=payload,
            instruction=(
                "Write a concise narrative explaining this measured listening shift. "
                "Describe what decreased and increased; do not invent why it happened."
            ),
            schema=CHANGE_SCHEMA,
        )
    return len(rows)


def _prepare_cluster_jobs(connection: sqlite3.Connection) -> int:
    cluster_rows = connection.execute(
        """
        SELECT cluster_id, COUNT(*) AS track_count
        FROM track_analysis
        WHERE cluster_id IS NOT NULL
        GROUP BY cluster_id
        ORDER BY cluster_id
        """
    ).fetchall()
    for cluster in cluster_rows:
        cluster_id = cluster["cluster_id"]
        payload = {
            "cluster_id": cluster_id,
            "track_count": cluster["track_count"],
            "representative_tracks": _cluster_tracks(connection, cluster_id),
            "representative_genres": _cluster_genres(connection, cluster_id),
        }
        _upsert_job(
            connection,
            job_type="cluster_label",
            source_key=str(cluster_id),
            payload=payload,
            instruction=(
                "Give this track cluster a specific, descriptive music label. "
                "Base the label only on its representative tracks, artists, and genres."
            ),
            schema=CLUSTER_SCHEMA,
        )
    return len(cluster_rows)


def _prepare_moment_jobs(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        """
        SELECT
            sm.id,
            sm.month,
            sm.track_id,
            sm.play_count,
            sm.total_ms,
            sm.reason,
            t.name AS track_name,
            GROUP_CONCAT(ta.artist_name, ', ') AS artists
        FROM significant_moments sm
        JOIN tracks t ON t.id = sm.track_id
        LEFT JOIN track_artists ta ON ta.track_id = sm.track_id
        GROUP BY
            sm.id, sm.month, sm.track_id, sm.play_count, sm.total_ms, sm.reason, t.name
        ORDER BY sm.play_count DESC
        """
    ).fetchall()
    for row in rows:
        neighbors = connection.execute(
            """
            SELECT
                t.name,
                GROUP_CONCAT(ta.artist_name, ', ') AS artists,
                mn.similarity
            FROM moment_neighbors mn
            JOIN tracks t ON t.id = mn.neighbor_track_id
            LEFT JOIN track_artists ta ON ta.track_id = t.id
            WHERE mn.moment_id = ?
            GROUP BY mn.rank, t.id, t.name, mn.similarity
            ORDER BY mn.rank
            """,
            (row["id"],),
        ).fetchall()
        payload = {
            "month": row["month"],
            "track": row["track_name"],
            "artists": row["artists"] or "",
            "play_count": row["play_count"],
            "listening_hours": round(row["total_ms"] / 3_600_000, 1),
            "reason": row["reason"],
            "cross_era_neighbors": [
                {
                    "track": neighbor["name"],
                    "artists": neighbor["artists"] or "",
                    "similarity": round(neighbor["similarity"], 3),
                }
                for neighbor in neighbors
            ],
        }
        _upsert_job(
            connection,
            job_type="significant_moment",
            source_key=f"{row['month']}:{row['track_id']}",
            payload=payload,
            instruction=(
                "Write a brief replay-moment note and mention the supplied cross-era "
                "neighbors as tracks with related metadata—not identical sound."
            ),
            schema=MOMENT_SCHEMA,
        )
    return len(rows)


def _prepare_taste_dna_job(connection: sqlite3.Connection) -> int:
    payload = {
        "history_range": dict(
            connection.execute(
                """
                SELECT MIN(substr(played_at, 1, 7)) AS first_month,
                       MAX(substr(played_at, 1, 7)) AS last_month,
                       COUNT(*) AS listens
                FROM listen_events
                """
            ).fetchone()
        ),
        "top_genres": [
            {"genre": row["genre"], "average_percentage": round(row["average"] * 100, 1)}
            for row in connection.execute(
                """
                SELECT genre, AVG(percentage) AS average
                FROM monthly_genre_mix
                WHERE genre != 'unknown'
                GROUP BY genre
                ORDER BY average DESC
                LIMIT 10
                """
            )
        ],
        "top_artists": _top_artists(connection),
        "top_tracks": _top_tracks(connection, "0000-00", "9999-99", limit=10),
        "major_shift_months": [
            row["month"]
            for row in connection.execute(
                "SELECT month FROM change_points ORDER BY month"
            )
        ],
    }
    _upsert_job(
        connection,
        job_type="taste_dna",
        source_key="current",
        payload=payload,
        instruction=(
            "Summarize the listener's enduring musical profile and major measured "
            "changes. Keep it concrete and avoid personality claims."
        ),
        schema=TASTE_DNA_SCHEMA,
    )
    return 1


def _upsert_job(
    connection: sqlite3.Connection,
    *,
    job_type: str,
    source_key: str,
    payload: dict[str, Any],
    instruction: str,
    schema: dict[str, Any],
) -> None:
    prompt = (
        f"{BASE_RULES}\n\nTask:\n{instruction}\n\n"
        f"Analytical input:\n{json.dumps(payload, indent=2)}\n\n"
        f"Required JSON schema:\n{json.dumps(schema, indent=2)}"
    )
    connection.execute(
        """
        INSERT INTO narrative_jobs (
            job_type, source_key, input_json, prompt, output_schema_json
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(job_type, source_key) DO UPDATE SET
            input_json = excluded.input_json,
            prompt = excluded.prompt,
            output_schema_json = excluded.output_schema_json,
            status = CASE
                WHEN narrative_jobs.status = 'completed' THEN 'completed'
                ELSE 'pending'
            END,
            error = NULL
        """,
        (
            job_type,
            source_key,
            json.dumps(payload),
            prompt,
            json.dumps(schema),
        ),
    )


def _top_tracks(
    connection: sqlite3.Connection,
    start_month: str,
    end_month: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT
                t.name AS track,
                GROUP_CONCAT(DISTINCT ta.artist_name) AS artists,
                COUNT(DISTINCT le.id) AS plays
            FROM listen_events le
            JOIN tracks t ON t.id = le.track_id
            LEFT JOIN track_artists ta ON ta.track_id = t.id
            WHERE substr(le.played_at, 1, 7) >= ?
              AND substr(le.played_at, 1, 7) < ?
            GROUP BY t.id, t.name
            ORDER BY plays DESC
            LIMIT ?
            """,
            (start_month, end_month, limit),
        )
    ]


def _top_artists(
    connection: sqlite3.Connection,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT a.name AS artist, COUNT(DISTINCT le.id) AS plays
            FROM listen_events le
            JOIN track_artists ta ON ta.track_id = le.track_id
            JOIN artists a ON a.id = ta.artist_id
            GROUP BY a.id, a.name
            ORDER BY plays DESC
            LIMIT ?
            """,
            (limit,),
        )
    ]


def _cluster_tracks(
    connection: sqlite3.Connection,
    cluster_id: int,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT
                t.name AS track,
                GROUP_CONCAT(DISTINCT ta.artist_name) AS artists,
                COUNT(DISTINCT le.id) AS plays
            FROM track_analysis analysis
            JOIN tracks t ON t.id = analysis.track_id
            LEFT JOIN track_artists ta ON ta.track_id = t.id
            LEFT JOIN listen_events le ON le.track_id = t.id
            WHERE analysis.cluster_id = ?
            GROUP BY t.id, t.name
            ORDER BY plays DESC
            LIMIT 10
            """,
            (cluster_id,),
        )
    ]


def _cluster_genres(
    connection: sqlite3.Connection,
    cluster_id: int,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT a.genres_json
        FROM track_analysis analysis
        JOIN track_artists ta ON ta.track_id = analysis.track_id
        JOIN artists a ON a.id = ta.artist_id
        WHERE analysis.cluster_id = ? AND a.genres_json IS NOT NULL
        """,
        (cluster_id,),
    ).fetchall()
    counts: dict[str, int] = {}
    for row in rows:
        for genre in json.loads(row["genres_json"]):
            counts[genre] = counts.get(genre, 0) + 1
    return [
        {"genre": genre, "tracks": count}
        for genre, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[
            :10
        ]
    ]


def _percentages(values: dict[str, float]) -> dict[str, float]:
    return {genre: round(value * 100, 1) for genre, value in values.items()}


def _genre_deltas(
    before: dict[str, float],
    after: dict[str, float],
) -> list[dict[str, float | str]]:
    deltas = [
        {
            "genre": genre,
            "before_pct": round(before.get(genre, 0.0) * 100, 1),
            "after_pct": round(after.get(genre, 0.0) * 100, 1),
            "delta_points": round((after.get(genre, 0.0) - before.get(genre, 0.0)) * 100, 1),
        }
        for genre in set(before) | set(after)
        if genre != "unknown"
    ]
    return sorted(deltas, key=lambda item: abs(float(item["delta_points"])), reverse=True)[
        :8
    ]


def _shift_month(month: str, offset: int) -> str:
    year, month_number = map(int, month.split("-"))
    absolute = year * 12 + month_number - 1 + offset
    return f"{absolute // 12:04d}-{absolute % 12 + 1:02d}"
