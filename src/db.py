"""SQLite database setup for the listening history data foundation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "beyond_spotify_wrapped.sqlite3"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY,
    uri TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    album_id TEXT,
    album_name TEXT,
    album_release_date TEXT,
    album_release_date_precision TEXT,
    duration_ms INTEGER,
    explicit INTEGER NOT NULL DEFAULT 0,
    is_local INTEGER NOT NULL DEFAULT 0,
    is_playable INTEGER,
    disc_number INTEGER,
    track_number INTEGER,
    spotify_url TEXT,
    isrc TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artists (
    id TEXT PRIMARY KEY,
    uri TEXT UNIQUE,
    name TEXT NOT NULL,
    spotify_url TEXT,
    genres_json TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS track_artists (
    track_id TEXT NOT NULL,
    artist_id TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    artist_order INTEGER NOT NULL,
    PRIMARY KEY (track_id, artist_order),
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS listen_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id TEXT NOT NULL,
    played_at TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('export', 'api')),
    ms_played INTEGER,
    context_type TEXT,
    context_uri TEXT,
    context_url TEXT,
    skipped INTEGER,
    reason_start TEXT,
    reason_end TEXT,
    platform TEXT,
    shuffle INTEGER,
    offline INTEGER,
    raw_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_listen_events_track_played_at
ON listen_events(track_id, played_at);

CREATE INDEX IF NOT EXISTS idx_listen_events_played_at
ON listen_events(played_at);

CREATE INDEX IF NOT EXISTS idx_listen_events_source
ON listen_events(source);

CREATE TABLE IF NOT EXISTS sync_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with the project defaults enabled."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    """Create the database schema if it does not already exist."""
    path = Path(db_path)
    with connect(path) as connection:
        connection.executescript(SCHEMA)
    return path


def _to_int_bool(value: Any) -> int | None:
    """Coerce a truthy/None value into SQLite-friendly 0/1/NULL."""
    if value is None:
        return None
    return 1 if value else 0


def upsert_track(
    connection: sqlite3.Connection,
    track: dict[str, Any],
    *,
    store_raw: bool = True,
) -> str | None:
    """Insert or update a track row from a Spotify track object.

    Returns the track id, or None for local/invalid tracks that cannot be
    keyed (Spotify local files have no stable id).
    """
    track_id = track.get("id")
    if not track_id:
        return None

    album = track.get("album") or {}
    external_ids = track.get("external_ids") or {}
    external_urls = track.get("external_urls") or {}

    connection.execute(
        """
        INSERT INTO tracks (
            id, uri, name, album_id, album_name, album_release_date,
            album_release_date_precision, duration_ms, explicit, is_local,
            is_playable, disc_number, track_number, spotify_url, isrc, raw_json,
            updated_at
        ) VALUES (
            :id, :uri, :name, :album_id, :album_name, :album_release_date,
            :album_release_date_precision, :duration_ms, :explicit, :is_local,
            :is_playable, :disc_number, :track_number, :spotify_url, :isrc,
            :raw_json, CURRENT_TIMESTAMP
        )
        ON CONFLICT(id) DO UPDATE SET
            uri = excluded.uri,
            name = excluded.name,
            album_id = excluded.album_id,
            album_name = excluded.album_name,
            album_release_date = excluded.album_release_date,
            album_release_date_precision = excluded.album_release_date_precision,
            duration_ms = excluded.duration_ms,
            explicit = excluded.explicit,
            is_local = excluded.is_local,
            is_playable = excluded.is_playable,
            disc_number = excluded.disc_number,
            track_number = excluded.track_number,
            spotify_url = excluded.spotify_url,
            isrc = COALESCE(excluded.isrc, tracks.isrc),
            raw_json = COALESCE(excluded.raw_json, tracks.raw_json),
            updated_at = CURRENT_TIMESTAMP
        """,
        {
            "id": track_id,
            "uri": track.get("uri") or f"spotify:track:{track_id}",
            "name": track.get("name") or "",
            "album_id": album.get("id"),
            "album_name": album.get("name"),
            "album_release_date": album.get("release_date"),
            "album_release_date_precision": album.get("release_date_precision"),
            "duration_ms": track.get("duration_ms"),
            "explicit": _to_int_bool(track.get("explicit")) or 0,
            "is_local": _to_int_bool(track.get("is_local")) or 0,
            "is_playable": _to_int_bool(track.get("is_playable")),
            "disc_number": track.get("disc_number"),
            "track_number": track.get("track_number"),
            "spotify_url": external_urls.get("spotify"),
            "isrc": external_ids.get("isrc"),
            "raw_json": json.dumps(track) if store_raw else None,
        },
    )

    _upsert_track_artists(connection, track_id, track.get("artists") or [])
    return track_id


def _upsert_track_artists(
    connection: sqlite3.Connection,
    track_id: str,
    artists: list[dict[str, Any]],
) -> None:
    """Replace the ordered artist links for a track."""
    connection.execute("DELETE FROM track_artists WHERE track_id = ?", (track_id,))
    for order, artist in enumerate(artists):
        artist_id = artist.get("id")
        artist_name = artist.get("name") or ""
        if artist_id:
            _upsert_artist_stub(connection, artist)
        connection.execute(
            """
            INSERT INTO track_artists (track_id, artist_id, artist_name, artist_order)
            VALUES (?, ?, ?, ?)
            """,
            (track_id, artist_id or "", artist_name, order),
        )


def _upsert_artist_stub(
    connection: sqlite3.Connection,
    artist: dict[str, Any],
) -> None:
    """Insert a minimal artist row from an embedded artist object.

    Genres are not populated here (the current API tier omits them); a later
    enrichment step fills genres_json from a fallback source.
    """
    artist_id = artist.get("id")
    if not artist_id:
        return
    external_urls = artist.get("external_urls") or {}
    connection.execute(
        """
        INSERT INTO artists (id, uri, name, spotify_url, updated_at)
        VALUES (:id, :uri, :name, :spotify_url, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            uri = excluded.uri,
            name = excluded.name,
            spotify_url = excluded.spotify_url,
            updated_at = CURRENT_TIMESTAMP
        """,
        {
            "id": artist_id,
            "uri": artist.get("uri") or f"spotify:artist:{artist_id}",
            "name": artist.get("name") or "",
            "spotify_url": external_urls.get("spotify"),
        },
    )


def insert_listen_event(
    connection: sqlite3.Connection,
    *,
    track_id: str,
    played_at: str,
    source: str,
    ms_played: int | None = None,
    context_type: str | None = None,
    context_uri: str | None = None,
    context_url: str | None = None,
    skipped: Any = None,
    reason_start: str | None = None,
    reason_end: str | None = None,
    platform: str | None = None,
    shuffle: Any = None,
    offline: Any = None,
    raw_json: str | None = None,
) -> bool:
    """Insert a listen event, ignoring exact (track_id, played_at) duplicates.

    Returns True if a new row was inserted, False if it was a duplicate.
    """
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO listen_events (
            track_id, played_at, source, ms_played, context_type, context_uri,
            context_url, skipped, reason_start, reason_end, platform, shuffle,
            offline, raw_json
        ) VALUES (
            :track_id, :played_at, :source, :ms_played, :context_type,
            :context_uri, :context_url, :skipped, :reason_start, :reason_end,
            :platform, :shuffle, :offline, :raw_json
        )
        """,
        {
            "track_id": track_id,
            "played_at": played_at,
            "source": source,
            "ms_played": ms_played,
            "context_type": context_type,
            "context_uri": context_uri,
            "context_url": context_url,
            "skipped": _to_int_bool(skipped),
            "reason_start": reason_start,
            "reason_end": reason_end,
            "platform": platform,
            "shuffle": _to_int_bool(shuffle),
            "offline": _to_int_bool(offline),
            "raw_json": raw_json,
        },
    )
    return cursor.rowcount > 0


def get_sync_state(
    connection: sqlite3.Connection,
    key: str,
    default: str | None = None,
) -> str | None:
    """Read a value from the sync_state key/value table."""
    row = connection.execute(
        "SELECT value FROM sync_state WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else default


def set_sync_state(
    connection: sqlite3.Connection,
    key: str,
    value: str,
) -> None:
    """Write a value into the sync_state key/value table."""
    connection.execute(
        """
        INSERT INTO sync_state (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value),
    )
