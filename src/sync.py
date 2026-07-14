"""Ongoing data sync from the Spotify recently-played endpoint.

Spotify only returns the last ~50 plays and only keeps a short rolling window,
so this is meant to run frequently (nightly at minimum) to avoid gaps. Each
run is incremental: it uses a stored cursor so it only pulls listens newer
than what is already in the database.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import spotipy

from src import db
from src.spotify_client import get_client

CURSOR_KEY = "recently_played_after_ms"
LAST_SYNC_KEY = "recently_played_last_sync_utc"


def _played_at_to_ms(played_at: str) -> int:
    """Convert an ISO-8601 played_at timestamp to Unix milliseconds."""
    normalized = played_at.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).timestamp() * 1000)


def sync_recently_played(
    connection,
    client: spotipy.Spotify,
    *,
    max_pages: int = 10,
) -> dict[str, int]:
    """Pull recent listens into the database.

    Returns a small stats dict: fetched, inserted, duplicates.
    """
    after = db.get_sync_state(connection, CURSOR_KEY)
    after_ms = int(after) if after else None

    fetched = 0
    inserted = 0
    duplicates = 0
    max_played_ms = after_ms or 0

    for _ in range(max_pages):
        response = client.current_user_recently_played(limit=50, after=after_ms)
        items = response.get("items", [])
        if not items:
            break

        for item in items:
            track = item.get("track") or {}
            played_at = item.get("played_at")
            if not played_at:
                continue

            track_id = db.upsert_track(connection, track)
            if track_id is None:
                continue

            context = item.get("context") or {}
            was_inserted = db.insert_listen_event(
                connection,
                track_id=track_id,
                played_at=played_at,
                source="api",
                ms_played=track.get("duration_ms"),
                context_type=context.get("type"),
                context_uri=context.get("uri"),
                context_url=(context.get("external_urls") or {}).get("spotify"),
                raw_json=json.dumps(item),
            )
            fetched += 1
            if was_inserted:
                inserted += 1
            else:
                duplicates += 1

            max_played_ms = max(max_played_ms, _played_at_to_ms(played_at))

        # Advance the cursor to just past the newest item we've seen so the
        # next page/run only returns strictly newer listens.
        next_after = max_played_ms + 1
        if next_after == after_ms:
            break
        after_ms = next_after

        # recently-played keeps only a small rolling window; a short page
        # means we've caught up.
        if len(items) < 50:
            break

    if max_played_ms:
        db.set_sync_state(connection, CURSOR_KEY, str(max_played_ms))
    db.set_sync_state(
        connection,
        LAST_SYNC_KEY,
        datetime.now(timezone.utc).isoformat(),
    )
    connection.commit()

    return {"fetched": fetched, "inserted": inserted, "duplicates": duplicates}


def run_once() -> dict[str, int]:
    """Initialize the DB, build a client, and run a single sync pass."""
    db.init_db()
    connection = db.connect()
    try:
        client = get_client()
        stats = sync_recently_played(connection, client)
    finally:
        connection.close()
    return stats


if __name__ == "__main__":
    result = run_once()
    print(
        f"Sync complete: fetched={result['fetched']} "
        f"inserted={result['inserted']} duplicates={result['duplicates']}"
    )
