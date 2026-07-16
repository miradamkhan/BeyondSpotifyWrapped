"""Detect major listening-history change points from monthly genre mix."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import db
from src.change_detection import (
    detect_change_points,
    load_monthly_genre_matrix,
    save_change_points,
)


def main() -> None:
    with db.connect() as connection:
        matrix = load_monthly_genre_matrix(connection)
        points = detect_change_points(matrix)
        save_change_points(connection, points)

    print(f"Detected {len(points)} change points.")
    for point in points:
        before = ", ".join(_format_summary(point.before_summary))
        after = ", ".join(_format_summary(point.after_summary))
        print(f"  {point.month} score={point.score:.3f}")
        print(f"    before: {before}")
        print(f"    after:  {after}")


def _format_summary(summary: dict[str, float]) -> list[str]:
    return [f"{genre} {value * 100:.1f}%" for genre, value in summary.items()]


if __name__ == "__main__":
    main()
