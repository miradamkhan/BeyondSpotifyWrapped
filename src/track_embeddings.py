"""Track metadata embeddings and clustering."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from src.db import REPO_ROOT
from src.genre_mix import _clean_genres

EMBEDDINGS_DIR = REPO_ROOT / "data" / "embeddings"
EMBEDDINGS_PATH = EMBEDDINGS_DIR / "track_embeddings.npz"
N_COMPONENTS = 128
N_CLUSTERS = 8


@dataclass(frozen=True)
class TrackDocument:
    track_id: str
    text: str


def load_track_documents(connection: sqlite3.Connection) -> list[TrackDocument]:
    """Build one metadata text document per track."""
    rows = connection.execute(
        """
        SELECT
            t.id,
            t.name,
            t.album_name,
            t.album_release_date,
            GROUP_CONCAT(ta.artist_name, ', ') AS artists,
            GROUP_CONCAT(a.genres_json, '|||') AS genre_jsons
        FROM tracks t
        LEFT JOIN track_artists ta ON ta.track_id = t.id
        LEFT JOIN artists a ON a.id = ta.artist_id
        GROUP BY t.id
        ORDER BY t.id
        """
    ).fetchall()

    documents: list[TrackDocument] = []
    for row in rows:
        genres = _genres_from_jsons(row["genre_jsons"], artist_name=row["artists"] or "")
        year = (row["album_release_date"] or "")[:4]
        parts = [
            row["name"] or "",
            f"by {row['artists']}" if row["artists"] else "",
            f"from {row['album_name']}" if row["album_name"] else "",
            f"released {year}" if year else "",
            f"genres: {', '.join(genres)}" if genres else "",
        ]
        documents.append(
            TrackDocument(
                track_id=row["id"],
                text=" ".join(part for part in parts if part).strip(),
            )
        )
    return documents


def build_embeddings(
    documents: list[TrackDocument],
    *,
    n_components: int = N_COMPONENTS,
) -> tuple[np.ndarray, TfidfVectorizer, TruncatedSVD]:
    """Create dense metadata embeddings using TF-IDF followed by SVD."""
    texts = [doc.text for doc in documents]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.8,
        sublinear_tf=True,
    )
    sparse = vectorizer.fit_transform(texts)
    components = min(n_components, sparse.shape[1] - 1, sparse.shape[0] - 1)
    if components < 2:
        raise ValueError("Not enough tracks/vocabulary to build embeddings")

    reducer = TruncatedSVD(n_components=components, random_state=42)
    embeddings = reducer.fit_transform(sparse)
    return normalize(embeddings), vectorizer, reducer


def cluster_and_project(
    embeddings: np.ndarray,
    *,
    n_clusters: int = N_CLUSTERS,
) -> tuple[np.ndarray, np.ndarray]:
    """Cluster embeddings and produce 2D plot coordinates."""
    clusters = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto").fit_predict(
        embeddings
    )
    coordinates = PCA(n_components=2, random_state=42).fit_transform(embeddings)
    return clusters, coordinates


def save_embedding_outputs(
    connection: sqlite3.Connection,
    documents: list[TrackDocument],
    embeddings: np.ndarray,
    clusters: np.ndarray,
    coordinates: np.ndarray,
) -> None:
    """Persist cluster/plot metadata in SQLite and vectors as a compressed NPZ."""
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    track_ids = np.array([doc.track_id for doc in documents])
    np.savez_compressed(
        EMBEDDINGS_PATH,
        track_ids=track_ids,
        embeddings=embeddings.astype(np.float32),
    )

    connection.execute("DELETE FROM track_analysis")
    connection.executemany(
        """
        INSERT INTO track_analysis (
            track_id, text_representation, cluster_id, x, y, updated_at
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            (
                doc.track_id,
                doc.text,
                int(clusters[index]),
                float(coordinates[index, 0]),
                float(coordinates[index, 1]),
            )
            for index, doc in enumerate(documents)
        ],
    )
    connection.commit()


def run_embedding_pipeline(
    connection: sqlite3.Connection,
    *,
    n_clusters: int = N_CLUSTERS,
) -> dict[str, int | str]:
    """Build embeddings, clusters, and projection coordinates for all tracks."""
    documents = load_track_documents(connection)
    embeddings, _, _ = build_embeddings(documents)
    clusters, coordinates = cluster_and_project(embeddings, n_clusters=n_clusters)
    save_embedding_outputs(connection, documents, embeddings, clusters, coordinates)
    return {
        "tracks": len(documents),
        "dimensions": embeddings.shape[1],
        "clusters": n_clusters,
        "embeddings_path": str(EMBEDDINGS_PATH.relative_to(REPO_ROOT)),
    }


def _genres_from_jsons(genre_jsons: str | None, *, artist_name: str) -> list[str]:
    if not genre_jsons:
        return []

    genres: list[str] = []
    for payload in genre_jsons.split("|||"):
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError:
            continue
        cleaned = _clean_genres(json.dumps(raw), artist_name=artist_name)
        for genre in cleaned:
            if genre not in genres:
                genres.append(genre)
    return genres[:8]
