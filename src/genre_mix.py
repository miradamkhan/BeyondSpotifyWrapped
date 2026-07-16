"""Monthly genre-mix analytics from listen history."""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass

MIN_LISTEN_MS = 30_000
MAX_GENRES_PER_ARTIST = 4
OTHER_GENRE = "unknown"

TAG_STOPLIST = {
    "",
    "seen live",
    "favorites",
    "favourites",
    "spotify",
    "last.fm",
    "file/path",
    "english",
    "american",
    "british",
    "male vocalists",
    "female vocalists",
    "singer-songwriter",
    "cover",
}

TAG_ALIASES = {
    "hip-hop": "hip hop",
    "hiphop": "hip hop",
    "r&b": "rnb",
    "rhythm and blues": "rnb",
    "contemporary r&b": "rnb",
    "edm": "electronic",
    "electronica": "electronic",
    "alt rock": "alternative rock",
    "indie": "indie rock",
    "soundtrack": "film score",
}


@dataclass(frozen=True)
class GenreMixRow:
    month: str
    genre: str
    listen_ms: int
    listen_events: int
    percentage: float


def compute_monthly_genre_mix(
    connection: sqlite3.Connection,
    *,
    min_listen_ms: int = MIN_LISTEN_MS,
) -> list[GenreMixRow]:
    """Compute monthly genre percentages from listen events and artist tags."""
    rows = connection.execute(
        """
        SELECT
            substr(le.played_at, 1, 7) AS month,
            le.ms_played,
            t.duration_ms,
            a.name AS artist_name,
            a.genres_json
        FROM listen_events le
        JOIN tracks t ON t.id = le.track_id
        JOIN track_artists ta ON ta.track_id = t.id
        JOIN artists a ON a.id = ta.artist_id
        WHERE COALESCE(le.ms_played, t.duration_ms, 0) >= ?
        """,
        (min_listen_ms,),
    ).fetchall()

    month_genre_ms: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    month_genre_events: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in rows:
        weight_ms = int(row["ms_played"] or row["duration_ms"] or 0)
        genres = _clean_genres(row["genres_json"], artist_name=row["artist_name"])
        if not genres:
            genres = [OTHER_GENRE]

        # Split each listen across the artist's usable tags so one track does
        # not count as four full listens when an artist has multiple genres.
        split_ms = max(1, round(weight_ms / len(genres)))
        for genre in genres:
            month_genre_ms[row["month"]][genre] += split_ms
            month_genre_events[row["month"]][genre] += 1

    results: list[GenreMixRow] = []
    for month, genre_totals in sorted(month_genre_ms.items()):
        total_ms = sum(genre_totals.values())
        if total_ms == 0:
            continue
        for genre, listen_ms in sorted(genre_totals.items()):
            results.append(
                GenreMixRow(
                    month=month,
                    genre=genre,
                    listen_ms=listen_ms,
                    listen_events=month_genre_events[month][genre],
                    percentage=listen_ms / total_ms,
                )
            )

    return results


def save_monthly_genre_mix(
    connection: sqlite3.Connection,
    rows: list[GenreMixRow],
) -> None:
    """Replace persisted monthly genre-mix rows."""
    connection.execute("DELETE FROM monthly_genre_mix")
    connection.executemany(
        """
        INSERT INTO monthly_genre_mix (
            month, genre, listen_ms, listen_events, percentage, updated_at
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            (row.month, row.genre, row.listen_ms, row.listen_events, row.percentage)
            for row in rows
        ],
    )
    connection.commit()


def top_genres_by_month(
    connection: sqlite3.Connection,
    *,
    top_n: int = 5,
) -> dict[str, list[tuple[str, float]]]:
    """Return top genres per month from persisted monthly_genre_mix."""
    rows = connection.execute(
        """
        SELECT month, genre, percentage
        FROM monthly_genre_mix
        ORDER BY month, percentage DESC
        """
    ).fetchall()
    result: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for row in rows:
        if len(result[row["month"]]) < top_n:
            result[row["month"]].append((row["genre"], row["percentage"]))
    return dict(result)


def _clean_genres(genres_json: str | None, *, artist_name: str) -> list[str]:
    if not genres_json:
        return []

    try:
        raw_genres = json.loads(genres_json)
    except json.JSONDecodeError:
        return []

    cleaned: list[str] = []
    artist_tokens = set(_tokenize(artist_name))
    for tag in raw_genres:
        normalized = _normalize_tag(str(tag))
        if not normalized or normalized in TAG_STOPLIST:
            continue
        if normalized in artist_tokens or normalized == _normalize_tag(artist_name):
            continue
        if normalized not in cleaned:
            cleaned.append(normalized)
        if len(cleaned) >= MAX_GENRES_PER_ARTIST:
            break
    return cleaned


def _normalize_tag(tag: str) -> str:
    normalized = re.sub(r"\s+", " ", tag.casefold().strip())
    normalized = TAG_ALIASES.get(normalized, normalized)
    return normalized


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())
