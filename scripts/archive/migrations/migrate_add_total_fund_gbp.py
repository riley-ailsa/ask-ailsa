#!/usr/bin/env python3
"""
Add total_fund_gbp column to existing database and populate it.

Usage:
    python scripts/migrate_add_total_fund_gbp.py
"""

import sqlite3
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.money import parse_gbp_amount


def migrate():
    """Add total_fund_gbp column and populate it."""
    db_path = "grants.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 80)
    print("MIGRATION: Add total_fund_gbp Column")
    print("=" * 80)
    print()

    # Add column
    print("Adding total_fund_gbp column...")

    try:
        cursor.execute("ALTER TABLE grants ADD COLUMN total_fund_gbp INTEGER")
        print("✓ Column added")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("✓ Column already exists")
        else:
            raise

    # Populate column by parsing existing total_fund values
    print("\nParsing existing funding amounts...")

    cursor.execute("SELECT id, total_fund FROM grants WHERE total_fund IS NOT NULL")
    rows = cursor.fetchall()

    updated = 0
    failed = 0
    failed_grants = []

    for row in rows:
        grant_id = row["id"]
        total_fund = row["total_fund"]

        _, amount_gbp = parse_gbp_amount(total_fund)

        if amount_gbp is not None:
            cursor.execute(
                "UPDATE grants SET total_fund_gbp = ? WHERE id = ?",
                (amount_gbp, grant_id)
            )
            updated += 1
        else:
            failed += 1
            failed_grants.append((grant_id, total_fund))

    conn.commit()

    print(f"\n✓ Updated {updated} grants")

    if failed > 0:
        print(f"\n⚠️  Failed to parse {failed} amounts:")
        for grant_id, total_fund in failed_grants[:10]:  # Show first 10
            print(f"  • {grant_id}: '{total_fund}'")
        if failed > 10:
            print(f"  ... and {failed - 10} more")

    print("\n" + "=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)

    conn.close()


if __name__ == "__main__":
    migrate()
