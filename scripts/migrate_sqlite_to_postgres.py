"""
Migrate grants from SQLite to PostgreSQL.

This script reads grants from the SQLite database (grants.db) and inserts them
into the PostgreSQL database, handling schema differences between the two.
"""

import os
import sqlite3
from datetime import datetime
from typing import Optional
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def map_sqlite_to_postgres(sqlite_row: dict) -> dict:
    """
    Map SQLite grant row to PostgreSQL schema.

    SQLite schema (old):
    - id (INTEGER) -> grant_id (TEXT)
    - grant_id (TEXT) -> grant_id (TEXT)
    - source, title, url, status
    - opens_at, closes_at -> open_date, close_date
    - description -> description_summary
    - tags (TEXT, JSON) -> tags (ARRAY)
    - total_fund_gbp -> budget_max

    PostgreSQL schema (new):
    - grant_id, source, title, url, status
    - open_date, close_date
    - description_summary
    - budget_min, budget_max
    - tags (ARRAY)
    - updated_at, scraped_at
    """
    # Handle tags - convert from JSON string to list
    tags = sqlite_row.get('tags')
    if tags:
        import json
        try:
            tags = json.loads(tags) if isinstance(tags, str) else tags
        except:
            tags = []
    else:
        tags = []

    # Handle dates
    opens_at = sqlite_row.get('opens_at')
    closes_at = sqlite_row.get('closes_at')

    # Convert ISO strings to dates if needed
    if opens_at and isinstance(opens_at, str):
        try:
            opens_at = datetime.fromisoformat(opens_at.replace('Z', '+00:00')).date()
        except:
            opens_at = None

    if closes_at and isinstance(closes_at, str):
        try:
            closes_at = datetime.fromisoformat(closes_at.replace('Z', '+00:00')).date()
        except:
            closes_at = None

    # Determine status based on dates and is_active flag
    status = sqlite_row.get('status', 'Closed')
    if not status:
        is_active = sqlite_row.get('is_active', 0)
        if is_active:
            if closes_at and closes_at < datetime.now().date():
                status = 'Closed'
            elif opens_at and opens_at > datetime.now().date():
                status = 'Forthcoming'
            else:
                status = 'Open'
        else:
            status = 'Closed'

    return {
        'grant_id': sqlite_row['grant_id'],
        'source': sqlite_row['source'],
        'title': sqlite_row['title'],
        'url': sqlite_row.get('url', ''),
        'status': status,
        'open_date': opens_at,
        'close_date': closes_at,
        'description_summary': sqlite_row.get('description', ''),
        'budget_max': sqlite_row.get('total_fund_gbp'),
        'tags': tags,
        'updated_at': datetime.utcnow(),
        'scraped_at': datetime.utcnow(),
    }


def migrate_grants(
    sqlite_db_path: str = "grants.db",
    source_filter: Optional[str] = None,
    dry_run: bool = False
):
    """
    Migrate grants from SQLite to PostgreSQL.

    Args:
        sqlite_db_path: Path to SQLite database file
        source_filter: Only migrate grants from this source (e.g., "nihr")
        dry_run: If True, only print what would be migrated without actually migrating
    """
    # Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_db_path)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # Get grants from SQLite
    query = "SELECT * FROM grants"
    params = []

    if source_filter:
        query += " WHERE source = ?"
        params.append(source_filter)

    sqlite_cursor.execute(query, params)
    sqlite_rows = sqlite_cursor.fetchall()

    print(f"Found {len(sqlite_rows)} grants in SQLite (source: {source_filter or 'all'})")

    if len(sqlite_rows) == 0:
        print("No grants to migrate!")
        sqlite_conn.close()
        return

    # Convert to dict and map to PostgreSQL schema
    postgres_rows = []
    for row in sqlite_rows:
        row_dict = dict(row)
        try:
            pg_row = map_sqlite_to_postgres(row_dict)
            postgres_rows.append(pg_row)
        except Exception as e:
            print(f"Error mapping row {row_dict.get('grant_id')}: {e}")
            continue

    print(f"Successfully mapped {len(postgres_rows)} grants to PostgreSQL schema")

    if dry_run:
        print("\nDRY RUN - Would migrate these grants:")
        for i, row in enumerate(postgres_rows[:5]):
            print(f"\n{i+1}. {row['grant_id']}")
            print(f"   Title: {row['title'][:60]}...")
            print(f"   Source: {row['source']}")
            print(f"   Status: {row['status']}")
        if len(postgres_rows) > 5:
            print(f"\n... and {len(postgres_rows) - 5} more")
        sqlite_conn.close()
        return

    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    pg_cursor = pg_conn.cursor()

    # Prepare INSERT query with ON CONFLICT to handle duplicates
    insert_query = """
        INSERT INTO grants (
            grant_id, source, title, url, status,
            open_date, close_date, description_summary,
            budget_max, tags, updated_at, scraped_at
        ) VALUES %s
        ON CONFLICT (grant_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            url = EXCLUDED.url,
            status = EXCLUDED.status,
            open_date = EXCLUDED.open_date,
            close_date = EXCLUDED.close_date,
            description_summary = EXCLUDED.description_summary,
            budget_max = EXCLUDED.budget_max,
            tags = EXCLUDED.tags,
            updated_at = EXCLUDED.updated_at
    """

    # Prepare values
    values = [
        (
            row['grant_id'],
            row['source'],
            row['title'],
            row['url'],
            row['status'],
            row['open_date'],
            row['close_date'],
            row['description_summary'],
            row['budget_max'],
            row['tags'],
            row['updated_at'],
            row['scraped_at']
        )
        for row in postgres_rows
    ]

    try:
        # Batch insert
        execute_values(pg_cursor, insert_query, values)
        pg_conn.commit()
        print(f"\n✅ Successfully migrated {len(values)} grants to PostgreSQL!")

        # Verify
        pg_cursor.execute(
            "SELECT COUNT(*) FROM grants WHERE source = %s",
            (source_filter,) if source_filter else None
        )
        if source_filter:
            count = pg_cursor.fetchone()[0]
            print(f"PostgreSQL now has {count} grants from {source_filter}")

    except Exception as e:
        pg_conn.rollback()
        print(f"\n❌ Error migrating grants: {e}")
        raise
    finally:
        pg_cursor.close()
        pg_conn.close()
        sqlite_conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate grants from SQLite to PostgreSQL")
    parser.add_argument(
        "--source",
        type=str,
        help="Only migrate grants from this source (e.g., 'nihr', 'innovate_uk')"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be migrated without actually migrating"
    )
    parser.add_argument(
        "--sqlite-db",
        type=str,
        default="grants.db",
        help="Path to SQLite database file (default: grants.db)"
    )

    args = parser.parse_args()

    print("=" * 80)
    print("SQLite to PostgreSQL Migration")
    print("=" * 80)

    migrate_grants(
        sqlite_db_path=args.sqlite_db,
        source_filter=args.source,
        dry_run=args.dry_run
    )

    print("\n" + "=" * 80)
    print("Migration complete!")
    print("=" * 80)
