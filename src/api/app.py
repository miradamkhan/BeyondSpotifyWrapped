"""FastAPI application exposing Beyond Spotify Wrapped analytics."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from src import db
from src.api.auth import ApiKeyDep
from src.api.schemas import (
    ClusterLabel,
    ClusterPoint,
    ClustersResponse,
    MomentItem,
    MomentsResponse,
    NarrativeItem,
    NarrativesResponse,
    NeighborTrack,
    SyncResponse,
    TasteDnaResponse,
    TimelineGenrePoint,
    TimelineMonth,
    TimelineResponse,
)
from src.sync import run_once

app = FastAPI(
    title="Beyond Spotify Wrapped API",
    version="0.1.0",
    description="Personal listening analytics: timeline, clusters, moments, narratives.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = db.connect()
    try:
        yield connection
    finally:
        connection.close()


@app.get("/health")
def health() -> dict[str, str]:
    """Unauthenticated liveness check."""
    return {"status": "ok"}


@app.get("/timeline", response_model=TimelineResponse)
def get_timeline(
    _: ApiKeyDep,
    top_n: int = Query(12, ge=3, le=40, description="Top genres kept for charting"),
) -> TimelineResponse:
    """Monthly genre-mix percentages for the stacked timeline chart."""
    with get_connection() as connection:
        top_genres = [
            row["genre"]
            for row in connection.execute(
                """
                SELECT genre, SUM(percentage) AS weight
                FROM monthly_genre_mix
                WHERE genre != 'unknown'
                GROUP BY genre
                ORDER BY weight DESC
                LIMIT ?
                """,
                (top_n,),
            )
        ]
        if not top_genres:
            return TimelineResponse(months=[], top_genres=[])

        placeholders = ",".join("?" for _ in top_genres)
        rows = connection.execute(
            f"""
            SELECT month, genre, percentage, listen_ms, listen_events
            FROM monthly_genre_mix
            WHERE genre IN ({placeholders})
            ORDER BY month, percentage DESC
            """,
            top_genres,
        ).fetchall()

    by_month: dict[str, list[TimelineGenrePoint]] = {}
    for row in rows:
        by_month.setdefault(row["month"], []).append(
            TimelineGenrePoint(
                genre=row["genre"],
                percentage=row["percentage"],
                listen_ms=row["listen_ms"],
                listen_events=row["listen_events"],
            )
        )

    return TimelineResponse(
        top_genres=top_genres,
        months=[
            TimelineMonth(month=month, genres=genres)
            for month, genres in sorted(by_month.items())
        ],
    )


@app.get("/clusters", response_model=ClustersResponse)
def get_clusters(_: ApiKeyDep) -> ClustersResponse:
    """Cluster labels plus 2D coordinates for the scatter plot."""
    with get_connection() as connection:
        label_rows = connection.execute(
            """
            SELECT source_key, response_json
            FROM narrative_jobs
            WHERE job_type = 'cluster_label' AND status = 'completed'
            """
        ).fetchall()
        labels_by_id: dict[int, ClusterLabel] = {}
        for row in label_rows:
            cluster_id = int(row["source_key"])
            content = json.loads(row["response_json"] or "{}")
            labels_by_id[cluster_id] = ClusterLabel(
                cluster_id=cluster_id,
                label=content.get("label"),
                description=content.get("description"),
                representative_tracks=content.get("representative_tracks") or [],
                representative_artists=content.get("representative_artists") or [],
            )

        point_rows = connection.execute(
            """
            SELECT
                ta.track_id,
                t.name,
                GROUP_CONCAT(DISTINCT art.artist_name) AS artists,
                ta.cluster_id,
                ta.x,
                ta.y
            FROM track_analysis ta
            JOIN tracks t ON t.id = ta.track_id
            LEFT JOIN track_artists art ON art.track_id = t.id
            WHERE ta.cluster_id IS NOT NULL
              AND ta.x IS NOT NULL
              AND ta.y IS NOT NULL
            GROUP BY ta.track_id, t.name, ta.cluster_id, ta.x, ta.y
            """
        ).fetchall()

        cluster_ids = sorted({row["cluster_id"] for row in point_rows})
        clusters = [
            labels_by_id.get(cluster_id, ClusterLabel(cluster_id=cluster_id))
            for cluster_id in cluster_ids
        ]
        points = [
            ClusterPoint(
                track_id=row["track_id"],
                name=row["name"],
                artists=row["artists"] or "",
                cluster_id=row["cluster_id"],
                x=row["x"],
                y=row["y"],
            )
            for row in point_rows
        ]

    return ClustersResponse(clusters=clusters, points=points)


@app.get("/moments", response_model=MomentsResponse)
def get_moments(_: ApiKeyDep) -> MomentsResponse:
    """Significant replay moments with cross-era 'sounds like' neighbors."""
    with get_connection() as connection:
        moment_rows = connection.execute(
            """
            SELECT
                sm.id,
                sm.month,
                sm.track_id,
                t.name AS track_name,
                GROUP_CONCAT(DISTINCT art.artist_name) AS artists,
                sm.play_count,
                sm.total_ms,
                sm.reason
            FROM significant_moments sm
            JOIN tracks t ON t.id = sm.track_id
            LEFT JOIN track_artists art ON art.track_id = sm.track_id
            GROUP BY
                sm.id, sm.month, sm.track_id, t.name, sm.play_count, sm.total_ms, sm.reason
            ORDER BY sm.play_count DESC
            """
        ).fetchall()

        narrative_rows = connection.execute(
            """
            SELECT source_key, response_json
            FROM narrative_jobs
            WHERE job_type = 'significant_moment' AND status = 'completed'
            """
        ).fetchall()
        narratives = {
            row["source_key"]: json.loads(row["response_json"] or "{}")
            for row in narrative_rows
        }

        neighbor_rows = connection.execute(
            """
            SELECT
                mn.moment_id,
                mn.neighbor_track_id,
                mn.rank,
                mn.similarity,
                t.name,
                GROUP_CONCAT(DISTINCT art.artist_name) AS artists
            FROM moment_neighbors mn
            JOIN tracks t ON t.id = mn.neighbor_track_id
            LEFT JOIN track_artists art ON art.track_id = t.id
            GROUP BY
                mn.moment_id, mn.neighbor_track_id, mn.rank, mn.similarity, t.name
            ORDER BY mn.moment_id, mn.rank
            """
        ).fetchall()

    neighbors_by_moment: dict[int, list[NeighborTrack]] = {}
    for row in neighbor_rows:
        neighbors_by_moment.setdefault(row["moment_id"], []).append(
            NeighborTrack(
                track_id=row["neighbor_track_id"],
                name=row["name"],
                artists=row["artists"] or "",
                similarity=row["similarity"],
                rank=row["rank"],
            )
        )

    moments = [
        MomentItem(
            id=row["id"],
            month=row["month"],
            track_id=row["track_id"],
            track_name=row["track_name"],
            artists=row["artists"] or "",
            play_count=row["play_count"],
            total_ms=row["total_ms"],
            listening_hours=round(row["total_ms"] / 3_600_000, 1),
            reason=row["reason"],
            narrative=narratives.get(f"{row['month']}:{row['track_id']}"),
            sounds_like=neighbors_by_moment.get(row["id"], []),
        )
        for row in moment_rows
    ]
    return MomentsResponse(moments=moments)


@app.get("/narratives", response_model=NarrativesResponse)
def get_narratives(_: ApiKeyDep) -> NarrativesResponse:
    """Latest LLM-generated change-point narratives."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT source_key, model, generated_at, response_json
            FROM narrative_jobs
            WHERE job_type = 'change_point' AND status = 'completed'
            ORDER BY source_key
            """
        ).fetchall()

    narratives = [
        NarrativeItem(
            source_key=row["source_key"],
            month=row["source_key"],
            model=row["model"],
            generated_at=row["generated_at"],
            content=json.loads(row["response_json"] or "{}"),
        )
        for row in rows
    ]
    return NarrativesResponse(narratives=narratives)


@app.get("/taste-dna", response_model=TasteDnaResponse)
def get_taste_dna(_: ApiKeyDep) -> TasteDnaResponse:
    """Living Taste DNA profile generated from historical listening facts."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT model, generated_at, response_json, status
            FROM narrative_jobs
            WHERE job_type = 'taste_dna' AND source_key = 'current'
            """
        ).fetchone()

    if not row or row["status"] != "completed" or not row["response_json"]:
        return TasteDnaResponse(content={})

    return TasteDnaResponse(
        model=row["model"],
        generated_at=row["generated_at"],
        content=json.loads(row["response_json"]),
    )


@app.post("/sync", response_model=SyncResponse)
def trigger_sync(_: ApiKeyDep) -> SyncResponse:
    """Manually trigger a recently-played Spotify sync."""
    stats = run_once()
    return SyncResponse(
        fetched=stats["fetched"],
        inserted=stats["inserted"],
        duplicates=stats["duplicates"],
    )
