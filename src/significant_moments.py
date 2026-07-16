"""Detect replay-heavy listening moments and attach cross-era neighbors."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from src.retrieval import Neighbor, find_nearest

DEFAULT_MOMENTS = 12
MIN_PLAYS = 8


@dataclass(frozen=True)
class Moment:
    month: str
    track_id: str
    track_name: str
    artists: str
    play_count: int
    total_ms: int
    reason: str


def detect_significant_moments(
    connection: sqlite3.Connection,
    *,
    limit: int = DEFAULT_MOMENTS,
    min_plays: int = MIN_PLAYS,
) -> list[Moment]:
    """Find each track's strongest replay month, then rank globally."""
    rows = connection.execute(
        """
        WITH monthly_replays AS (
            SELECT
                substr(le.played_at, 1, 7) AS month,
                le.track_id,
                COUNT(*) AS play_count,
                SUM(COALESCE(le.ms_played, t.duration_ms, 0)) AS total_ms,
                ROW_NUMBER() OVER (
                    PARTITION BY le.track_id
                    ORDER BY COUNT(*) DESC, substr(le.played_at, 1, 7)
                ) AS track_rank
            FROM listen_events le
            JOIN tracks t ON t.id = le.track_id
            GROUP BY month, le.track_id
            HAVING COUNT(*) >= ?
        )
        SELECT
            mr.month,
            mr.track_id,
            t.name AS track_name,
            GROUP_CONCAT(ta.artist_name, ', ') AS artists,
            mr.play_count,
            mr.total_ms
        FROM monthly_replays mr
        JOIN tracks t ON t.id = mr.track_id
        LEFT JOIN track_artists ta ON ta.track_id = mr.track_id
        WHERE mr.track_rank = 1
        GROUP BY
            mr.month, mr.track_id, t.name, mr.play_count, mr.total_ms
        ORDER BY mr.play_count DESC, mr.total_ms DESC
        LIMIT ?
        """,
        (min_plays, limit),
    ).fetchall()

    return [
        Moment(
            month=row["month"],
            track_id=row["track_id"],
            track_name=row["track_name"],
            artists=row["artists"] or "",
            play_count=row["play_count"],
            total_ms=row["total_ms"],
            reason=(
                f"Played {row['play_count']} times in {row['month']} "
                f"({row['total_ms'] / 3_600_000:.1f} listening hours)"
            ),
        )
        for row in rows
    ]


def save_moments_with_neighbors(
    connection: sqlite3.Connection,
    moments: list[Moment],
    *,
    neighbors_per_moment: int = 5,
) -> dict[int, list[Neighbor]]:
    """Replace moments and save nearest tracks from other eras."""
    connection.execute("DELETE FROM moment_neighbors")
    connection.execute("DELETE FROM significant_moments")
    connection.commit()

    neighbor_map: dict[int, list[Neighbor]] = {}
    for moment in moments:
        cursor = connection.execute(
            """
            INSERT INTO significant_moments (
                month, track_id, play_count, total_ms, reason
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                moment.month,
                moment.track_id,
                moment.play_count,
                moment.total_ms,
                moment.reason,
            ),
        )
        moment_id = int(cursor.lastrowid)
        neighbors = find_nearest(
            connection,
            moment.track_id,
            k=neighbors_per_moment,
            source_month=moment.month,
            cross_era=True,
        )
        neighbor_map[moment_id] = neighbors
        connection.executemany(
            """
            INSERT INTO moment_neighbors (
                moment_id, neighbor_track_id, rank, similarity
            ) VALUES (?, ?, ?, ?)
            """,
            [
                (moment_id, neighbor.track_id, rank, neighbor.similarity)
                for rank, neighbor in enumerate(neighbors, start=1)
            ],
        )

    connection.commit()
    return neighbor_map
