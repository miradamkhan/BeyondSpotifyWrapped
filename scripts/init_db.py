"""Initialize the local SQLite database."""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.db import DEFAULT_DB_PATH, init_db


def main() -> None:
    db_path = init_db(DEFAULT_DB_PATH)
    print(f"Initialized database at {Path(db_path).relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
