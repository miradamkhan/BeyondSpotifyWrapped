"""Prepare Milestone 3 narrative inputs without calling an LLM."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import db
from src.narrative_pipeline import prepare_narrative_jobs
from src.significant_moments import (
    detect_significant_moments,
    save_moments_with_neighbors,
)

OUTPUT_PATH = REPO_ROOT / "data" / "narrative_jobs.jsonl"


def main() -> None:
    db.init_db()
    with db.connect() as connection:
        moments = detect_significant_moments(connection)
        neighbors = save_moments_with_neighbors(connection, moments)
        counts = prepare_narrative_jobs(connection)

        jobs = connection.execute(
            """
            SELECT id, job_type, source_key, input_json, prompt,
                   output_schema_json, status
            FROM narrative_jobs
            ORDER BY job_type, source_key
            """
        ).fetchall()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        for job in jobs:
            file.write(json.dumps(dict(job)) + "\n")

    print(f"Prepared {len(moments)} significant moments.")
    print(f"Attached {sum(len(items) for items in neighbors.values())} cross-era neighbors.")
    print(
        "Narrative jobs: "
        + ", ".join(f"{job_type}={count}" for job_type, count in counts.items())
    )
    print(f"Exported {len(jobs)} jobs to {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
