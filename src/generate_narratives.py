"""Run pending narrative jobs against a local Ollama model."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from src.ollama_client import (
    DEFAULT_MODEL,
    generate_json,
    validate_against_schema,
)


def pending_jobs(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT id, job_type, source_key, prompt, output_schema_json, status
        FROM narrative_jobs
        WHERE status = 'pending'
        ORDER BY
            CASE job_type
                WHEN 'taste_dna' THEN 1
                WHEN 'change_point' THEN 2
                WHEN 'cluster_label' THEN 3
                ELSE 4
            END,
            source_key
        """
    ).fetchall()


def generate_pending_narratives(
    connection: sqlite3.Connection,
    *,
    model: str = DEFAULT_MODEL,
    limit: int | None = None,
) -> dict[str, int]:
    """Generate structured narratives for pending jobs and store them."""
    jobs = pending_jobs(connection)
    if limit is not None:
        jobs = jobs[:limit]

    stats = {"attempted": 0, "completed": 0, "failed": 0}
    total = len(jobs)
    for index, job in enumerate(jobs, start=1):
        stats["attempted"] += 1
        schema = json.loads(job["output_schema_json"])
        try:
            response = generate_json(job["prompt"], schema, model=model)
            validate_against_schema(response, schema)
            connection.execute(
                """
                UPDATE narrative_jobs
                SET status = 'completed',
                    model = ?,
                    response_json = ?,
                    error = NULL,
                    generated_at = ?
                WHERE id = ?
                """,
                (
                    model,
                    json.dumps(response),
                    datetime.now(timezone.utc).isoformat(),
                    job["id"],
                ),
            )
            connection.commit()
            stats["completed"] += 1
            preview = _preview(response)
            print(
                f"[{index}/{total}] completed {job['job_type']} "
                f"{job['source_key']}: {preview}",
                flush=True,
            )
        except Exception as error:  # noqa: BLE001 - store any generation failure
            connection.execute(
                """
                UPDATE narrative_jobs
                SET status = 'failed',
                    model = ?,
                    error = ?,
                    generated_at = ?
                WHERE id = ?
                """,
                (
                    model,
                    str(error),
                    datetime.now(timezone.utc).isoformat(),
                    job["id"],
                ),
            )
            connection.commit()
            stats["failed"] += 1
            print(
                f"[{index}/{total}] FAILED {job['job_type']} "
                f"{job['source_key']}: {error}",
                flush=True,
            )

    return stats


def _preview(response: dict) -> str:
    for key in ("title", "label", "headline", "note"):
        if key in response and isinstance(response[key], str):
            text = response[key].strip()
            return text if len(text) <= 80 else text[:77] + "..."
    return "ok"
