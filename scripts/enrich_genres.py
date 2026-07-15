"""Fill artist genres from MusicBrainz.

Usage:
    python scripts/enrich_genres.py             # process all pending artists
    python scripts/enrich_genres.py --limit 10  # small test run
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import db
from src.genre_enrichment import enrich_genres


def main() -> None:
    parser = argparse.ArgumentParser(description="MusicBrainz genre enrichment")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process this many artists (for testing).",
    )
    args = parser.parse_args()

    connection = db.connect()
    try:
        stats = enrich_genres(connection, limit=args.limit)
    finally:
        connection.close()

    print(
        "Genre enrichment complete: "
        f"attempted={stats['attempted']} with_genres={stats['with_genres']} "
        f"no_match={stats['no_match']} errors={stats['errors']}"
    )


if __name__ == "__main__":
    main()
