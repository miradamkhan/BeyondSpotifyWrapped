"""Generate anonymized fake Spotify Extended Streaming History for demos.

Run:
    python scripts/generate_sample_data.py

Writes sample_data/Spotify Extended Streaming History/Streaming_History_Audio_sample.json
with synthetic artists/tracks and no personal identifiers.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "sample_data" / "Spotify Extended Streaming History"
OUT_FILE = OUT_DIR / "Streaming_History_Audio_sample.json"

# Synthetic catalog — intentionally fake names/IDs so nothing personal ships.
CATALOG = [
    {
        "artist": "Northline Collective",
        "album": "Grid Signal",
        "tracks": ["Amber Hours", "Relay", "Soft Static", "Afterglow Lane"],
        "uri_prefix": "aaaaaaaaaaaaaaaaaaaaaaaaa",
    },
    {
        "artist": "Juniper Circuit",
        "album": "Neon Orchard",
        "tracks": ["Leaf Code", "Patio Rain", "Copper Sky", "Weekend Drift"],
        "uri_prefix": "bbbbbbbbbbbbbbbbbbbbbbbbb",
    },
    {
        "artist": "Harbor Atlas",
        "album": "Tide Maps",
        "tracks": ["Dock Lights", "Brine", "Ferry Window", "Low Tide"],
        "uri_prefix": "ccccccccccccccccccccccccc",
    },
    {
        "artist": "Velvet Meter",
        "album": "Pulse Drafts",
        "tracks": ["Redline", "Night Bus", "Glass Floor", "Echo Tax"],
        "uri_prefix": "ddddddddddddddddddddddddd",
    },
    {
        "artist": "Cedar Frequency",
        "album": "Cabin Modem",
        "tracks": ["Pine Cache", "Modem Hymn", "Trailhead", "Snow Buffer"],
        "uri_prefix": "eeeeeeeeeeeeeeeeeeeeeeeee",
    },
    {
        "artist": "Marble District",
        "album": "Lobby Tapes",
        "tracks": ["Escalator", "Keycard", "Atrium", "Closing Shift"],
        "uri_prefix": "fffffffffffffffffffffffff",
    },
    {
        "artist": "Paper Lanterns",
        "album": "Quiet Festival",
        "tracks": ["Kite String", "Folded Note", "Parade Rest", "Lantern Out"],
        "uri_prefix": "ggggggggggggggggggggggggg",
    },
    {
        "artist": "Ozone Room",
        "album": "HVAC Dreams",
        "tracks": ["Filter Change", "Blue Vent", "Recirc", "Ceiling Hum"],
        "uri_prefix": "hhhhhhhhhhhhhhhhhhhhhhhhh",
    },
]

# Era weights: early hip-hop/trap-leaning artists → later indie/electronic lean.
ERA_WEIGHTS = [
    # 2023: Velvet Meter + Marble District heavy
    {"Velvet Meter": 0.35, "Marble District": 0.3, "Harbor Atlas": 0.15, "Northline Collective": 0.1, "Juniper Circuit": 0.05, "Cedar Frequency": 0.05},
    # 2024: shift toward Juniper / Ozone
    {"Juniper Circuit": 0.3, "Ozone Room": 0.25, "Velvet Meter": 0.15, "Paper Lanterns": 0.15, "Harbor Atlas": 0.1, "Cedar Frequency": 0.05},
    # 2025: Paper Lanterns + Cedar + Northline
    {"Paper Lanterns": 0.3, "Cedar Frequency": 0.25, "Northline Collective": 0.2, "Juniper Circuit": 0.15, "Ozone Room": 0.05, "Harbor Atlas": 0.05},
]


def _track_uri(artist_entry: dict, track_index: int) -> str:
    # Spotify IDs are 22 chars; keep the track index in the final characters.
    suffix = f"{track_index:02d}"
    prefix = artist_entry["uri_prefix"][: 22 - len(suffix)]
    return f"spotify:track:{prefix}{suffix}"


def _pick_artist(weights: dict[str, float], rng: random.Random) -> dict:
    artists = list(weights.keys())
    probs = [weights[name] for name in artists]
    chosen = rng.choices(artists, weights=probs, k=1)[0]
    return next(item for item in CATALOG if item["artist"] == chosen)


def generate_records(seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    start = datetime(2023, 1, 5, 12, 0, tzinfo=timezone.utc)
    end = datetime(2025, 12, 15, 22, 0, tzinfo=timezone.utc)
    cursor = start
    records: list[dict] = []
    event_id = 0

    while cursor < end:
        month = cursor.month
        year = cursor.year
        if year == 2023:
            weights = ERA_WEIGHTS[0]
        elif year == 2024:
            weights = ERA_WEIGHTS[1]
        else:
            weights = ERA_WEIGHTS[2]

        # Heavier listening on weekends
        plays_today = rng.randint(4, 18) if cursor.weekday() >= 5 else rng.randint(1, 10)
        for _ in range(plays_today):
            artist = _pick_artist(weights, rng)
            track_index = rng.randrange(len(artist["tracks"]))
            track_name = artist["tracks"][track_index]
            duration = rng.randint(140_000, 260_000)
            # Mostly completed listens, some skips
            skipped = rng.random() < 0.12
            ms_played = rng.randint(8_000, 45_000) if skipped else duration
            cursor = cursor + timedelta(seconds=ms_played / 1000 + rng.randint(5, 120))
            if cursor > end:
                break
            records.append(
                {
                    "ts": cursor.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "platform": rng.choice(["windows", "android", "osx"]),
                    "ms_played": ms_played,
                    "conn_country": "US",
                    "ip_addr": "0.0.0.0",
                    "master_metadata_track_name": track_name,
                    "master_metadata_album_artist_name": artist["artist"],
                    "master_metadata_album_album_name": artist["album"],
                    "spotify_track_uri": _track_uri(artist, track_index),
                    "episode_name": None,
                    "episode_show_name": None,
                    "spotify_episode_uri": None,
                    "audiobook_title": None,
                    "audiobook_uri": None,
                    "audiobook_chapter_uri": None,
                    "audiobook_chapter_title": None,
                    "reason_start": "trackdone" if event_id else "playbtn",
                    "reason_end": "fwdbtn" if skipped else "trackdone",
                    "shuffle": rng.random() < 0.55,
                    "skipped": skipped,
                    "offline": False,
                    "offline_timestamp": None,
                    "incognito_mode": False,
                }
            )
            event_id += 1

        cursor = datetime(
            cursor.year, cursor.month, cursor.day, tzinfo=timezone.utc
        ) + timedelta(days=1, hours=rng.randint(8, 14))

    return records


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = generate_records()
    OUT_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} sample listens -> {OUT_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
