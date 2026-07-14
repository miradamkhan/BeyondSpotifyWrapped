"""Shared Spotify client factory.

Centralizes OAuth setup so the sync job, enrichment scripts, and one-off
tools all authenticate the same way and share one token cache.
"""

from __future__ import annotations

from pathlib import Path

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / ".cache-spotify"

# Only the read scope is needed for the data foundation.
SCOPE = "user-read-recently-played"


def get_client(*, open_browser: bool = False) -> spotipy.Spotify:
    """Build an authenticated Spotify client.

    Uses the cached refresh token when present; only opens a browser for the
    first-time consent flow when explicitly allowed.
    """
    load_dotenv(REPO_ROOT / ".env")
    auth_manager = SpotifyOAuth(
        scope=SCOPE,
        cache_path=str(CACHE_PATH),
        open_browser=open_browser,
    )
    return spotipy.Spotify(auth_manager=auth_manager, requests_timeout=15, retries=3)
