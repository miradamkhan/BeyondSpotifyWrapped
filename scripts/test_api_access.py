"""One-off script to verify what our Spotify access tier can actually do.

Tests the three things Milestone 1+2 depend on:
  1. recently-played (the nightly sync source)
  2. artist lookup - specifically whether `genres` is still populated
  3. single track lookup

Saves raw responses to data/samples/ so we can design the SQLite schema
against real payload shapes.

Usage: copy .env.example to .env, fill in credentials, then run
    python scripts/test_api_access.py
A browser window will open for the OAuth consent flow on first run.
"""

import json
from pathlib import Path

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_ROOT / "data" / "samples"

load_dotenv(REPO_ROOT / ".env")


def save_sample(name: str, payload: dict) -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    path = SAMPLES_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"  saved raw response -> {path.relative_to(REPO_ROOT)}")


def main() -> None:
    sp = spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            scope="user-read-recently-played",
            cache_path=str(REPO_ROOT / ".cache-spotify"),
            open_browser=True,
        )
    )

    print("== 1. GET /me/player/recently-played ==")
    recent = sp.current_user_recently_played(limit=50)
    items = recent.get("items", [])
    print(f"  OK, {len(items)} items returned")
    for item in items[:5]:
        track = item["track"]
        artists = ", ".join(a["name"] for a in track["artists"])
        print(f"    {item['played_at']}  {track['name']} - {artists}")
    save_sample("recently_played", recent)

    if not items:
        print("  No recent listens found - play a few tracks and rerun.")
        return

    first_track = items[0]["track"]
    artist_id = first_track["artists"][0]["id"]
    track_id = first_track["id"]

    print("\n== 2. GET /artists/{id} (checking `genres` field) ==")
    artist = sp.artist(artist_id)
    print(f"  OK, artist: {artist['name']}")
    genres = artist.get("genres")
    if genres:
        print(f"  genres field IS populated: {genres}")
    else:
        print("  WARNING: genres field is empty/missing on this tier - "
              "Milestone 2 will need a fallback genre source")
    save_sample("artist", artist)

    print("\n== 3. GET /tracks/{id} ==")
    track = sp.track(track_id)
    print(f"  OK, track: {track['name']} ({track['duration_ms']} ms)")
    save_sample("track", track)

    print("\nAll checks done. Inspect data/samples/*.json before designing "
          "the schema.")


if __name__ == "__main__":
    main()
