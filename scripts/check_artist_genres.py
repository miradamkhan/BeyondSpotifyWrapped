"""Check whether Spotify returns genres for several recent artists."""

import json
from pathlib import Path

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

spotify = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        scope="user-read-recently-played",
        cache_path=str(REPO_ROOT / ".cache-spotify"),
        open_browser=False,
    ),
    requests_timeout=10,
    retries=1,
)

sample = json.loads(
    (REPO_ROOT / "data/samples/recently_played.json").read_text(encoding="utf-8")
)
artist_ids = list(
    dict.fromkeys(
        artist["id"]
        for item in sample["items"]
        for artist in item["track"]["artists"]
        if artist.get("id")
    )
)[:8]

for artist_id in artist_ids:
    artist = spotify.artist(artist_id)
    print(f"{artist['name']} -> {artist.get('genres', '<missing>')}")
