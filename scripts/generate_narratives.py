"""Generate pending narrative jobs with a local Ollama model.

Usage:
    python scripts/generate_narratives.py
    python scripts/generate_narratives.py --limit 2
    python scripts/generate_narratives.py --model qwen3:8b
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src import db
from src.generate_narratives import generate_pending_narratives
from src.ollama_client import DEFAULT_MODEL


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate narratives via Ollama")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only generate this many pending jobs (for testing).",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Reset failed jobs to pending before generating.",
    )
    args = parser.parse_args()

    connection = db.connect()
    try:
        if args.retry_failed:
            connection.execute(
                """
                UPDATE narrative_jobs
                SET status = 'pending', error = NULL
                WHERE status = 'failed'
                """
            )
            connection.commit()

        pending = connection.execute(
            "SELECT COUNT(*) FROM narrative_jobs WHERE status = 'pending'"
        ).fetchone()[0]
        print(f"Pending jobs: {pending} (model={args.model})")
        stats = generate_pending_narratives(
            connection,
            model=args.model,
            limit=args.limit,
        )
    finally:
        connection.close()

    print(
        "Generation complete: "
        f"attempted={stats['attempted']} completed={stats['completed']} "
        f"failed={stats['failed']}"
    )


if __name__ == "__main__":
    main()
