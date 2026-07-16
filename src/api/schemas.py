"""Pydantic response models for the FastAPI surface."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TimelineGenrePoint(BaseModel):
    genre: str
    percentage: float
    listen_ms: int
    listen_events: int


class TimelineMonth(BaseModel):
    month: str
    genres: list[TimelineGenrePoint]


class TimelineResponse(BaseModel):
    months: list[TimelineMonth]
    top_genres: list[str]


class ClusterLabel(BaseModel):
    cluster_id: int
    label: str | None = None
    description: str | None = None
    representative_tracks: list[str] = Field(default_factory=list)
    representative_artists: list[str] = Field(default_factory=list)


class ClusterPoint(BaseModel):
    track_id: str
    name: str
    artists: str
    cluster_id: int
    x: float
    y: float


class ClustersResponse(BaseModel):
    clusters: list[ClusterLabel]
    points: list[ClusterPoint]


class NeighborTrack(BaseModel):
    track_id: str
    name: str
    artists: str
    similarity: float
    rank: int


class MomentItem(BaseModel):
    id: int
    month: str
    track_id: str
    track_name: str
    artists: str
    play_count: int
    total_ms: int
    listening_hours: float
    reason: str
    narrative: dict[str, Any] | None = None
    sounds_like: list[NeighborTrack]


class MomentsResponse(BaseModel):
    moments: list[MomentItem]


class NarrativeItem(BaseModel):
    source_key: str
    month: str | None = None
    model: str | None = None
    generated_at: str | None = None
    content: dict[str, Any]


class NarrativesResponse(BaseModel):
    narratives: list[NarrativeItem]


class TasteDnaResponse(BaseModel):
    model: str | None = None
    generated_at: str | None = None
    content: dict[str, Any]


class SyncResponse(BaseModel):
    fetched: int
    inserted: int
    duplicates: int
