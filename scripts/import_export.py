"""Import Spotify Extended Streaming History files into SQLite.

Usage:
    python scripts/import_export.py ../my_spotify_data
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import db
from src.export_parser import import_export_folder


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Spotify export data")
    parser.add_argument(
        "export_path",
        type=Path,
        help="Path to the extracted Spotify data folder.",
    )
    args = parser.parse_args()

    db.init_db()
    with db.connect() as connection:
        stats = import_export_folder(args.export_path, connection=connection)

    print(
        "Export import complete: "
        f"files={stats['files']} records={stats['records']} "
        f"inserted={stats['inserted']} duplicates={stats['duplicates']} "
        f"skipped={stats['skipped']}"
    )


if __name__ == "__main__":
    main()
