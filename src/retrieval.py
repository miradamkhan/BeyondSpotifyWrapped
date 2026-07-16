"""Local vector retrieval for cross-era track similarity."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import numpy as np

from src.track_embeddings import EMBEDDINGS_PATH

MIN_ERA_DISTANCE_MONTHS = 6


@dataclass(frozen=True)
class Neighbor:
    track_id: str
    name: str
    artists: str
    similarity: float
    representative_month: str | None


def find_nearest(
    connection: sqlite3.Connection,
    track_id: str,
    *,
    k: int = 5,
    source_month: str | None = None,
    cross_era: bool = True,
) -> list[Neighbor]:
    """Return nearest metadata vectors, optionally from another listening era."""
    if not EMBEDDINGS_PATH.exists():
        raise FileNotFoundError(
            "Track embeddings are missing; run build_track_embeddings.py first"
        )

    archive = np.load(EMBEDDINGS_PATH)
    track_ids = archive["track_ids"].astype(str)
    embeddings = archive["embeddings"]
    index_by_id = {value: index for index, value in enumerate(track_ids)}
    source_index = index_by_id.get(track_id)
    if source_index is None:
        return []

    representative_months = _representative_months(connection)
    equivalent_track_ids = _same_title_track_ids(connection, track_id)
    similarities = embeddings @ embeddings[source_index]
    eligible: list[int] = []
    for index, candidate_id in enumerate(track_ids):
        if index == source_index or candidate_id in equivalent_track_ids:
            continue
        if cross_era and source_month:
            candidate_month = representative_months.get(candidate_id)
            if candidate_month is None:
                continue
            if _month_distance(source_month, candidate_month) < MIN_ERA_DISTANCE_MONTHS:
                continue
        eligible.append(index)

    ranked = sorted(eligible, key=lambda index: similarities[index], reverse=True)[:k]
    metadata = _track_metadata(connection, [track_ids[index] for index in ranked])
    return [
        Neighbor(
            track_id=str(track_ids[index]),
            name=metadata[str(track_ids[index])]["name"],
            artists=metadata[str(track_ids[index])]["artists"],
            similarity=float(similarities[index]),
            representative_month=representative_months.get(str(track_ids[index])),
        )
        for index in ranked
        if str(track_ids[index]) in metadata
    ]


def _representative_months(connection: sqlite3.Connection) -> dict[str, str]:
    """Return each track's most-played month."""
    rows = connection.execute(
        """
        SELECT track_id, substr(played_at, 1, 7) AS month, COUNT(*) AS plays
        FROM listen_events
        GROUP BY track_id, month
        ORDER BY track_id, plays DESC, month
        """
    ).fetchall()
    result: dict[str, str] = {}
    for row in rows:
        result.setdefault(row["track_id"], row["month"])
    return result


def _track_metadata(
    connection: sqlite3.Connection,
    track_ids: list[str],
) -> dict[str, dict[str, str]]:
    if not track_ids:
        return {}
    placeholders = ",".join("?" for _ in track_ids)
    rows = connection.execute(
        f"""
        SELECT
            t.id,
            t.name,
            GROUP_CONCAT(ta.artist_name, ', ') AS artists
        FROM tracks t
        LEFT JOIN track_artists ta ON ta.track_id = t.id
        WHERE t.id IN ({placeholders})
        GROUP BY t.id, t.name
        """,
        track_ids,
    ).fetchall()
    return {
        row["id"]: {"name": row["name"], "artists": row["artists"] or ""}
        for row in rows
    }


def _same_title_track_ids(
    connection: sqlite3.Connection,
    track_id: str,
) -> set[str]:
    """Find alternate Spotify releases carrying the exact same track title."""
    rows = connection.execute(
        """
        SELECT candidate.id
        FROM tracks candidate
        JOIN tracks source
          ON lower(trim(candidate.name)) = lower(trim(source.name))
        WHERE source.id = ?
        """,
        (track_id,),
    ).fetchall()
    return {row["id"] for row in rows}


def _month_distance(left: str, right: str) -> int:
    left_year, left_month = map(int, left.split("-"))
    right_year, right_month = map(int, right.split("-"))
    return abs((left_year * 12 + left_month) - (right_year * 12 + right_month))
