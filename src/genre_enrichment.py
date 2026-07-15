"""Artist genre enrichment from the MusicBrainz API.

MusicBrainz is free and keyless but rate-limited to ~1 request/second and
requires a descriptive User-Agent. We search each artist by name and store
the top match's community tags (genre labels) in artists.genres_json.

Convention: genres_json is NULL for artists not yet attempted, a JSON list
(possibly empty) once attempted - this makes reruns resumable.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

import requests

MB_SEARCH_URL = "https://musicbrainz.org/ws/2/artist/"
USER_AGENT = "BeyondSpotifyWrapped/0.1 (personal portfolio project)"
RATE_LIMIT_SECONDS = 1.1
MIN_MATCH_SCORE = 85
MAX_GENRES = 8
COMMIT_EVERY = 25


def pending_artists(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Artists without genre data, most-listened first."""
    return connection.execute(
        """
        SELECT a.id, a.name, COUNT(le.id) AS plays
        FROM artists a
        LEFT JOIN track_artists ta ON ta.artist_id = a.id
        LEFT JOIN listen_events le ON le.track_id = ta.track_id
        WHERE a.genres_json IS NULL
        GROUP BY a.id, a.name
        ORDER BY plays DESC, a.name
        """
    ).fetchall()


def fetch_artist_genres(
    session: requests.Session,
    name: str,
) -> tuple[list[str], dict[str, Any]]:
    """Search MusicBrainz for an artist and return (genres, provenance)."""
    response = _get_with_retry(
        session,
        MB_SEARCH_URL,
        params={"query": f'artist:"{name}"', "fmt": "json", "limit": "3"},
    )
    candidates = response.get("artists", [])

    best = None
    for candidate in candidates:
        if int(candidate.get("score", 0)) < MIN_MATCH_SCORE:
            continue
        best = candidate
        break

    if best is None:
        return [], {"source": "musicbrainz", "match": None}

    tags = sorted(
        (t for t in best.get("tags", []) if t.get("count", 0) >= 1),
        key=lambda t: -t["count"],
    )
    genres = [t["name"] for t in tags[:MAX_GENRES]]
    provenance = {
        "source": "musicbrainz",
        "match": {
            "mbid": best.get("id"),
            "name": best.get("name"),
            "score": best.get("score"),
        },
        "tags": tags,
    }
    return genres, provenance


def _get_with_retry(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, str],
    attempts: int = 3,
) -> dict[str, Any]:
    """GET with backoff for MusicBrainz throttling (503) responses."""
    for attempt in range(attempts):
        response = session.get(url, params=params, timeout=20)
        if response.status_code == 503 and attempt < attempts - 1:
            time.sleep(5 * (attempt + 1))
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError("unreachable")


def save_artist_genres(
    connection: sqlite3.Connection,
    artist_id: str,
    genres: list[str],
    provenance: dict[str, Any],
) -> None:
    connection.execute(
        """
        UPDATE artists
        SET genres_json = ?, raw_json = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (json.dumps(genres), json.dumps(provenance), artist_id),
    )


def enrich_genres(
    connection: sqlite3.Connection,
    *,
    limit: int | None = None,
) -> dict[str, int]:
    """Fill genres_json for artists that have not been attempted yet."""
    artists = pending_artists(connection)
    if limit is not None:
        artists = artists[:limit]

    stats = {"attempted": 0, "with_genres": 0, "no_match": 0, "errors": 0}
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    total = len(artists)
    for index, artist in enumerate(artists, start=1):
        try:
            genres, provenance = fetch_artist_genres(session, artist["name"])
        except requests.RequestException as error:
            stats["errors"] += 1
            print(f"  error for {artist['name']!r}: {error}", flush=True)
            time.sleep(RATE_LIMIT_SECONDS)
            continue

        save_artist_genres(connection, artist["id"], genres, provenance)
        stats["attempted"] += 1
        if genres:
            stats["with_genres"] += 1
        else:
            stats["no_match"] += 1

        if index % COMMIT_EVERY == 0 or index == total:
            connection.commit()
            print(
                f"[{index}/{total}] attempted={stats['attempted']} "
                f"with_genres={stats['with_genres']} "
                f"no_match={stats['no_match']} errors={stats['errors']}",
                flush=True,
            )

        time.sleep(RATE_LIMIT_SECONDS)

    connection.commit()
    return stats
