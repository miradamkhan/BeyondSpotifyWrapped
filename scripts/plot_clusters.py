"""Save a quick matplotlib scatter plot of clustered tracks."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import matplotlib.pyplot as plt

from src import db

PLOT_PATH = REPO_ROOT / "data" / "plots" / "track_clusters.png"


def main() -> None:
    with db.connect() as connection:
        rows = connection.execute(
            """
            SELECT cluster_id, x, y
            FROM track_analysis
            WHERE cluster_id IS NOT NULL AND x IS NOT NULL AND y IS NOT NULL
            """
        ).fetchall()

    if not rows:
        raise ValueError("No cluster coordinates found; run build_track_embeddings.py first")

    PLOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    xs = [row["x"] for row in rows]
    ys = [row["y"] for row in rows]
    clusters = [row["cluster_id"] for row in rows]

    plt.figure(figsize=(11, 8))
    scatter = plt.scatter(xs, ys, c=clusters, cmap="tab10", s=8, alpha=0.65)
    plt.title("Track Metadata Clusters")
    plt.xlabel("PCA 1")
    plt.ylabel("PCA 2")
    plt.colorbar(scatter, label="Cluster")
    plt.tight_layout()
    plt.savefig(PLOT_PATH, dpi=180)
    print(f"Saved cluster plot to {PLOT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
