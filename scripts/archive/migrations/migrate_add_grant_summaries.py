#!/usr/bin/env python3
"""
Create grant_summaries table for cached GPT summaries.

Usage:
    python3 scripts/migrate_add_grant_summaries.py --db grants.db
"""

import argparse
import sqlite3
from pathlib import Path


def migrate(db_path: str) -> None:
    """
    Add grant_summaries table to database.

    Schema:
        grant_id: Primary key, links to grants.id
        summary: Generated GPT summary (2-3 sentences)
        model: Model used for generation (e.g., "gpt-4o-mini")
        created_at: Timestamp of generation
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise SystemExit(f"❌ Database not found: {db_file}")

    print(f"Running migration on: {db_file}")

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    # Create grant_summaries table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS grant_summaries (
            grant_id    TEXT PRIMARY KEY,
            summary     TEXT NOT NULL,
            model       TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (grant_id) REFERENCES grants(id)
        )
        """
    )

    # Index on model for analytics
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_grant_summaries_model
        ON grant_summaries (model)
        """
    )

    # Index on created_at for tracking generation
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_grant_summaries_created
        ON grant_summaries (created_at)
        """
    )

    conn.commit()
    conn.close()

    print("✅ Migration complete: grant_summaries table created")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add grant_summaries table to database"
    )
    parser.add_argument(
        "--db",
        default="grants.db",
        help="Path to SQLite database"
    )

    args = parser.parse_args()
    migrate(args.db)


if __name__ == "__main__":
    main()
