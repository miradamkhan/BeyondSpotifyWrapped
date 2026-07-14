"""Run the recently-played sync: once, or on a nightly schedule.

Usage:
    python scripts/run_sync.py            # run one sync pass and exit
    python scripts/run_sync.py --schedule # run nightly (blocks, Ctrl+C to stop)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from apscheduler.schedulers.blocking import BlockingScheduler

from src.sync import run_once


def _run_and_report() -> None:
    stats = run_once()
    stamp = datetime.now().isoformat(timespec="seconds")
    print(
        f"[{stamp}] sync complete: fetched={stats['fetched']} "
        f"inserted={stats['inserted']} duplicates={stats['duplicates']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Spotify recently-played sync")
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run nightly on a schedule instead of a single pass.",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=3,
        help="Hour of day (0-23) to run the nightly sync (default: 3).",
    )
    args = parser.parse_args()

    if not args.schedule:
        _run_and_report()
        return

    # Run immediately on startup so we don't wait until the first trigger,
    # then hand off to the nightly schedule.
    _run_and_report()

    scheduler = BlockingScheduler()
    scheduler.add_job(_run_and_report, "cron", hour=args.hour, minute=0)
    print(f"Scheduled nightly sync at {args.hour:02d}:00. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")


if __name__ == "__main__":
    main()
