"""Change-point detection on monthly genre-mix vectors."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_WINDOW_MONTHS = 3
DEFAULT_TOP_N = 6


@dataclass(frozen=True)
class ChangePoint:
    month: str
    score: float
    before_summary: dict[str, float]
    after_summary: dict[str, float]


def load_monthly_genre_matrix(
    connection: sqlite3.Connection,
    *,
    top_genres: int = 40,
) -> pd.DataFrame:
    """Load monthly genre percentages as a dense month x genre matrix."""
    rows = connection.execute(
        """
        SELECT month, genre, percentage
        FROM monthly_genre_mix
        """
    ).fetchall()
    if not rows:
        raise ValueError("monthly_genre_mix is empty; run build_genre_mix.py first")

    frame = pd.DataFrame([dict(row) for row in rows])
    genre_totals = (
        frame.groupby("genre")["percentage"]
        .sum()
        .sort_values(ascending=False)
        .head(top_genres)
        .index
    )
    frame = frame[frame["genre"].isin(genre_totals)]
    matrix = (
        frame.pivot_table(
            index="month",
            columns="genre",
            values="percentage",
            aggfunc="sum",
            fill_value=0.0,
        )
        .sort_index()
        .astype(float)
    )
    return matrix


def detect_change_points(
    matrix: pd.DataFrame,
    *,
    max_points: int = 6,
    min_window: int = MIN_WINDOW_MONTHS,
) -> list[ChangePoint]:
    """Find months where the genre distribution changes sharply.

    This is a small dependency-free substitute for the planned ruptures/PELT
    pass. It scores each possible boundary by the L2 distance between the
    average genre vector before and after that boundary, then keeps the
    strongest non-overlapping boundaries.
    """
    if len(matrix) < min_window * 2 + 1:
        return []

    values = matrix.to_numpy(dtype=float)
    months = list(matrix.index)
    candidates: list[tuple[int, float]] = []

    for boundary in range(min_window, len(matrix) - min_window):
        before = values[max(0, boundary - 6) : boundary]
        after = values[boundary : min(len(matrix), boundary + 6)]
        if len(before) < min_window or len(after) < min_window:
            continue
        score = float(np.linalg.norm(after.mean(axis=0) - before.mean(axis=0)))
        candidates.append((boundary, score))

    if not candidates:
        return []

    # Keep strong local maxima, spaced apart so one broad shift does not emit
    # a stack of adjacent months.
    min_spacing = 3
    selected: list[tuple[int, float]] = []
    for boundary, score in sorted(candidates, key=lambda item: item[1], reverse=True):
        if any(abs(boundary - chosen) < min_spacing for chosen, _ in selected):
            continue
        selected.append((boundary, score))
        if len(selected) >= max_points:
            break

    selected.sort()
    return [
        ChangePoint(
            month=months[boundary],
            score=score,
            before_summary=_top_summary(matrix.iloc[max(0, boundary - 6) : boundary]),
            after_summary=_top_summary(matrix.iloc[boundary : min(len(matrix), boundary + 6)]),
        )
        for boundary, score in selected
    ]


def save_change_points(
    connection: sqlite3.Connection,
    change_points: list[ChangePoint],
) -> None:
    """Replace persisted change-point rows."""
    connection.execute("DELETE FROM change_points")
    connection.executemany(
        """
        INSERT INTO change_points (
            month, score, before_summary_json, after_summary_json
        ) VALUES (?, ?, ?, ?)
        """,
        [
            (
                point.month,
                point.score,
                json.dumps(point.before_summary),
                json.dumps(point.after_summary),
            )
            for point in change_points
        ],
    )
    connection.commit()


def _top_summary(frame: pd.DataFrame, *, top_n: int = DEFAULT_TOP_N) -> dict[str, float]:
    means = frame.mean(axis=0).sort_values(ascending=False).head(top_n)
    return {genre: round(float(value), 4) for genre, value in means.items()}
