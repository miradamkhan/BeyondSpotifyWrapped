"""Build track metadata embeddings, clusters, and 2D coordinates."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import db
from src.track_embeddings import run_embedding_pipeline


def main() -> None:
    db.init_db()
    with db.connect() as connection:
        stats = run_embedding_pipeline(connection)
        print(
            f"Embedded {stats['tracks']} tracks into {stats['dimensions']} dims "
            f"and {stats['clusters']} clusters."
        )
        print(f"Saved vectors to {stats['embeddings_path']}.")
        print("Cluster previews:")
        for row in connection.execute(
            """
            SELECT
                ta.cluster_id,
                COUNT(*) AS tracks,
                GROUP_CONCAT(t.name, ' | ') AS example_tracks
            FROM track_analysis ta
            JOIN tracks t ON t.id = ta.track_id
            GROUP BY ta.cluster_id
            ORDER BY tracks DESC
            """
        ):
            examples = " | ".join((row["example_tracks"] or "").split(" | ")[:4])
            print(f"  cluster {row['cluster_id']}: {row['tracks']} tracks - {examples}")


if __name__ == "__main__":
    main()
