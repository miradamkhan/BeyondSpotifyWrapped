"""Import Spotify Extended Streaming History into SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src import db

AUDIO_FILE_PATTERN = "Streaming_History_Audio*.json"
OVERLAP_TOLERANCE = timedelta(minutes=2)
EXPORT_IMPORT_KEY = "export_last_import_utc"
EXPORT_PATH_KEY = "export_last_import_path"


def import_export_folder(
    export_root: Path | str,
    *,
    connection: sqlite3.Connection,
    overlap_tolerance: timedelta = OVERLAP_TOLERANCE,
) -> dict[str, int]:
    """Import all Spotify audio history files below an export folder."""
    root = Path(export_root)
    files = sorted(root.rglob(AUDIO_FILE_PATTERN))
    if not files:
        raise FileNotFoundError(f"No {AUDIO_FILE_PATTERN} files found below {root}")

    stats = {
        "files": 0,
        "records": 0,
        "inserted": 0,
        "duplicates": 0,
        "skipped": 0,
    }

    for path in files:
        records = json.loads(path.read_text(encoding="utf-8"))
        stats["files"] += 1

        for record in records:
            stats["records"] += 1
            if _import_record(connection, record, overlap_tolerance=overlap_tolerance):
                stats["inserted"] += 1
            else:
                if _is_track_record(record):
                    stats["duplicates"] += 1
                else:
                    stats["skipped"] += 1

        connection.commit()

    db.set_sync_state(
        connection,
        EXPORT_IMPORT_KEY,
        datetime.now(timezone.utc).isoformat(),
    )
    db.set_sync_state(connection, EXPORT_PATH_KEY, str(root))
    connection.commit()

    return stats


def _import_record(
    connection: sqlite3.Connection,
    record: dict[str, Any],
    *,
    overlap_tolerance: timedelta,
) -> bool:
    """Import one export record.

    Returns True when a listen event is inserted. Returns False for duplicate
    or non-track records.
    """
    if not _is_track_record(record):
        return False

    played_at = record["ts"]
    track_uri = record["spotify_track_uri"]
    track_id = _spotify_id_from_uri(track_uri)
    if not track_id:
        return False

    track = {
        "id": track_id,
        "uri": track_uri,
        "name": record["master_metadata_track_name"],
        "album": {"name": record.get("master_metadata_album_album_name")},
        "artists": [{"name": record["master_metadata_album_artist_name"]}],
    }
    db.upsert_track(connection, track, store_raw=False, replace_artists=False)

    if _has_nearby_duplicate(
        connection,
        track_id=track_id,
        played_at=played_at,
        tolerance=overlap_tolerance,
    ):
        return False

    return db.insert_listen_event(
        connection,
        track_id=track_id,
        played_at=played_at,
        source="export",
        ms_played=record.get("ms_played"),
        skipped=record.get("skipped"),
        reason_start=record.get("reason_start"),
        reason_end=record.get("reason_end"),
        platform=record.get("platform"),
        shuffle=record.get("shuffle"),
        offline=record.get("offline"),
        raw_json=json.dumps(_sanitized_record(record)),
    )


def _is_track_record(record: dict[str, Any]) -> bool:
    """Return True for music-track records, excluding podcasts/audiobooks."""
    return bool(
        record.get("ts")
        and record.get("spotify_track_uri")
        and record.get("master_metadata_track_name")
        and record.get("master_metadata_album_artist_name")
    )


def _spotify_id_from_uri(uri: str) -> str | None:
    """Extract the Spotify id from a URI like spotify:track:<id>."""
    parts = uri.split(":")
    if len(parts) != 3 or parts[0] != "spotify" or parts[1] != "track":
        return None
    return parts[2]


def _has_nearby_duplicate(
    connection: sqlite3.Connection,
    *,
    track_id: str,
    played_at: str,
    tolerance: timedelta,
) -> bool:
    """Detect exact or near-duplicate listen events for export/API overlap."""
    target = _parse_spotify_timestamp(played_at)
    lower = target - tolerance
    upper = target + tolerance

    rows = connection.execute(
        """
        SELECT played_at
        FROM listen_events
        WHERE track_id = ?
        """,
        (track_id,),
    ).fetchall()
    return any(lower <= _parse_spotify_timestamp(row["played_at"]) <= upper for row in rows)


def _parse_spotify_timestamp(value: str) -> datetime:
    """Parse Spotify UTC timestamps with or without fractional seconds."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sanitized_record(record: dict[str, Any]) -> dict[str, Any]:
    """Keep useful raw export fields while dropping direct personal identifiers."""
    return {key: value for key, value in record.items() if key != "ip_addr"}
