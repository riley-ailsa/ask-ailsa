#!/usr/bin/env python3
"""
Migrate existing grants to use correct London timezone-based status.

This script:
1. Reads all grants from the database
2. Recalculates status using London local time
3. Updates each grant's is_active field
4. Shows before/after statistics
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.time_utils import infer_status


def migrate_timezone_fix(db_path: str):
    """
    Fix timezone-based status for all grants in database.

    Args:
        db_path: Path to SQLite database file
    """
    print(f"🔧 Migrating grant statuses in: {db_path}")
    print()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get current statistics
    print("📊 BEFORE MIGRATION:")
    cursor.execute("""
        SELECT
            CASE WHEN is_active = 1 THEN 'active' ELSE 'inactive' END as status,
            COUNT(*) as count
        FROM grants
        GROUP BY is_active
    """)
    for row in cursor.fetchall():
        print(f"  {row['status']}: {row['count']}")
    print()

    # Check for anomalies
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM grants
        WHERE is_active = 1
          AND closes_at IS NOT NULL
          AND datetime(closes_at) < datetime('now')
    """)
    past_active = cursor.fetchone()['count']
    if past_active > 0:
        print(f"⚠️  Found {past_active} 'active' grants with past deadlines (will be fixed)")
        print()

    # Fetch all grants
    cursor.execute("""
        SELECT id, opens_at, closes_at, is_active
        FROM grants
    """)
    rows = cursor.fetchall()

    print(f"🔄 Processing {len(rows)} grants...")

    changes = {
        'updated': 0,
        'unchanged': 0,
        'status_changes': {}
    }

    for row in rows:
        grant_id = row['id']
        opens_at_str = row['opens_at']
        closes_at_str = row['closes_at']
        old_is_active = bool(row['is_active'])

        # Parse datetimes
        opens_at = datetime.fromisoformat(opens_at_str) if opens_at_str else None
        closes_at = datetime.fromisoformat(closes_at_str) if closes_at_str else None

        # Calculate new status using London time
        new_status = infer_status(opens_at, closes_at)
        new_is_active = (new_status == "active")

        # Track changes
        if old_is_active != new_is_active:
            changes['updated'] += 1
            old_status_str = "active" if old_is_active else "inactive"
            new_status_str = "active" if new_is_active else "inactive"
            transition = f"{old_status_str} → {new_status_str}"
            changes['status_changes'][transition] = changes['status_changes'].get(transition, 0) + 1
        else:
            changes['unchanged'] += 1

        # Update database
        cursor.execute("""
            UPDATE grants
            SET is_active = ?
            WHERE id = ?
        """, (1 if new_is_active else 0, grant_id))

    conn.commit()

    # Show results
    print()
    print("✅ MIGRATION COMPLETE")
    print(f"  Updated: {changes['updated']} grants")
    print(f"  Unchanged: {changes['unchanged']} grants")

    if changes['status_changes']:
        print()
        print("📈 Status Changes:")
        for transition, count in sorted(changes['status_changes'].items()):
            print(f"  {transition}: {count}")

    print()
    print("📊 AFTER MIGRATION:")
    cursor.execute("""
        SELECT
            CASE WHEN is_active = 1 THEN 'active' ELSE 'inactive' END as status,
            COUNT(*) as count
        FROM grants
        GROUP BY is_active
    """)
    for row in cursor.fetchall():
        print(f"  {row['status']}: {row['count']}")

    # Verify no anomalies remain
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM grants
        WHERE is_active = 1
          AND closes_at IS NOT NULL
          AND datetime(closes_at) < datetime('now')
    """)
    remaining_anomalies = cursor.fetchone()['count']

    print()
    if remaining_anomalies == 0:
        print("✅ No active grants with past deadlines")
    else:
        print(f"⚠️  Warning: {remaining_anomalies} active grants still have past deadlines")
        print("   (This may be correct if they are in London time)")

    conn.close()
    print()
    print("✨ Done!")


if __name__ == "__main__":
    db_path = "grants.db"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    migrate_timezone_fix(db_path)
