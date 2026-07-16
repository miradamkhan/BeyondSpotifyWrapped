"""Compute and persist monthly genre-mix percentages."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import db
from src.genre_mix import compute_monthly_genre_mix, save_monthly_genre_mix


def main() -> None:
    db.init_db()
    with db.connect() as connection:
        rows = compute_monthly_genre_mix(connection)
        save_monthly_genre_mix(connection, rows)

        months = connection.execute(
            "SELECT COUNT(DISTINCT month) FROM monthly_genre_mix"
        ).fetchone()[0]
        genres = connection.execute(
            "SELECT COUNT(DISTINCT genre) FROM monthly_genre_mix"
        ).fetchone()[0]

        print(
            f"Saved {len(rows)} monthly genre rows "
            f"across {months} months and {genres} genres."
        )
        print("Recent top genres:")
        for row in connection.execute(
            """
            SELECT month, genre, ROUND(percentage * 100, 1) AS pct
            FROM monthly_genre_mix
            WHERE month >= (
                SELECT MAX(month) FROM monthly_genre_mix
            )
            ORDER BY percentage DESC
            LIMIT 8
            """
        ):
            print(f"  {row['month']}: {row['genre']} {row['pct']}%")


if __name__ == "__main__":
    main()
