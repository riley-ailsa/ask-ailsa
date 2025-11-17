#!/usr/bin/env python3
"""
Refine funding amounts to include decimals by reading competition text already
stored in the `documents` table (no network requests).

Process:
- Scans competition-scope documents for patterns like:
    "up to £1.5 million", "£3.425 million", "£15.5 million"
- If a decimal million is found, updates grants.total_fund + total_fund_gbp
- Logs all changes into manual_corrections (correction_type='auto_decimal_from_docs')
- Supports optional explicit overrides for any grant IDs

Usage:
    # Refine specific grants by ID
    python3 scripts/migrate_refine_funding_decimals.py --db grants.db \
        --ids innovate_uk_2327,innovate_uk_2335,innovate_uk_2307,innovate_uk_2328

    # Auto-detect candidates (whole millions without decimals)
    python3 scripts/migrate_refine_funding_decimals.py --db grants.db

    # View audit log
    python3 scripts/migrate_refine_funding_decimals.py --db grants.db --show-log
"""

import re
import sqlite3
import argparse
from datetime import datetime


# Optional explicit overrides if you already know precise decimals
# Use this if regex extraction fails or for known edge cases
# Format: {"grant_id": ("display_string", numeric_value)}
EXPLICIT_DECIMALS = {
    # Example (uncomment and fill if needed):
    # "innovate_uk_2327": ("up to £15.5 million", 15_500_000),
    # "innovate_uk_2335": ("up to £3.425 million", 3_425_000),
    # "innovate_uk_2307": ("up to £1.5 million", 1_500_000),
    # "innovate_uk_2328": ("up to £15.5 million", 15_500_000),
}

# Regex finds decimal million figures with optional "up to" prefix
# Examples matched:
#   - "up to £1.5 million"
#   - "£3.425 million"
#   - "£15.5 million"
#   - "up to £ 2.75 million" (with space after £)
DECIMAL_MILLION_RE = re.compile(
    r"(?:up to\s*)?£\s*(\d+(?:\.\d+)?)\s*million",
    flags=re.IGNORECASE
)


def ensure_audit_table(cur):
    """Create or ensure audit table exists for logging corrections."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS manual_corrections (
            id TEXT,
            old_total_fund TEXT,
            old_total_fund_gbp REAL,
            new_total_fund TEXT,
            new_total_fund_gbp REAL,
            reason TEXT,
            applied_at TEXT,
            correction_type TEXT
        )
    """)


def log_change(cur, grant_id, old_display, old_value, new_display, new_value, reason, ctype):
    """
    Record correction in audit table.

    Args:
        cur: Database cursor
        grant_id: Grant identifier
        old_display: Original funding display string
        old_value: Original numeric value
        new_display: Corrected display string
        new_value: Corrected numeric value
        reason: Explanation of correction
        ctype: Correction type ('auto_decimal_from_docs' or 'manual_decimal_override')
    """
    cur.execute("""
        INSERT INTO manual_corrections (
            id, old_total_fund, old_total_fund_gbp,
            new_total_fund, new_total_fund_gbp,
            reason, applied_at, correction_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        grant_id, old_display, old_value,
        new_display, new_value,
        reason, datetime.utcnow().isoformat(), ctype
    ))


def refine_from_documents(cur, grant_id):
    """
    Extract decimal funding from stored documents for a specific grant.

    Priority:
    1. Explicit override (if defined in EXPLICIT_DECIMALS)
    2. Regex extraction from competition-scope documents

    Args:
        cur: Database cursor
        grant_id: Grant identifier to refine

    Returns:
        str: Status message describing what happened
    """
    # Priority 1: Explicit override wins
    if grant_id in EXPLICIT_DECIMALS:
        new_display, new_value = EXPLICIT_DECIMALS[grant_id]
        cur.execute(
            "SELECT total_fund, total_fund_gbp FROM grants WHERE id=?",
            (grant_id,)
        )
        row = cur.fetchone()
        if not row:
            return f"⚠️  {grant_id}: not found in database"

        old_display, old_value = row

        # Apply correction
        cur.execute(
            "UPDATE grants SET total_fund=?, total_fund_gbp=? WHERE id=?",
            (new_display, new_value, grant_id)
        )

        # Log change
        log_change(
            cur, grant_id, old_display, old_value, new_display, new_value,
            "Explicit decimal override (manually specified)",
            "manual_decimal_override"
        )

        return f"✅ {grant_id}: {old_display} → {new_display} (£{new_value:,}) [manual override]"

    # Priority 2: Extract from stored documents
    cur.execute("""
        SELECT text FROM documents
        WHERE grant_id=? AND scope='competition'
        ORDER BY id
    """, (grant_id,))

    texts = [text for (text,) in cur.fetchall() if text]

    if not texts:
        return f"⚠️  {grant_id}: no competition-scope documents found"

    # Search for decimal million pattern in document text
    for blob in texts:
        match = DECIMAL_MILLION_RE.search(blob)
        if match:
            # Extract decimal number (e.g., "15.5" from "up to £15.5 million")
            number = float(match.group(1))
            new_value = int(round(number * 1_000_000))

            # Format display string: use :g to avoid trailing zeros
            # "15.5" stays "15.5", but "15.0" becomes "15"
            new_display = f"up to £{number:g} million"

            # Get current values
            cur.execute(
                "SELECT total_fund, total_fund_gbp FROM grants WHERE id=?",
                (grant_id,)
            )
            row = cur.fetchone()
            if not row:
                return f"⚠️  {grant_id}: disappeared from database?"

            old_display, old_value = row

            # Only update if genuinely different
            # Compare both numeric value and display string
            old_value = old_value or 0
            old_display = (old_display or "").lower()

            if old_value != new_value or old_display != new_display.lower():
                # Apply correction
                cur.execute(
                    "UPDATE grants SET total_fund=?, total_fund_gbp=? WHERE id=?",
                    (new_display, new_value, grant_id)
                )

                # Log change
                log_change(
                    cur, grant_id, old_display, old_value, new_display, new_value,
                    "Decimal million extracted from stored competition documents",
                    "auto_decimal_from_docs"
                )

                return f"✅ {grant_id}: {old_display} → {new_display} (£{new_value:,})"
            else:
                return f"ℹ️  {grant_id}: already correct ({new_display})"

    # No decimal pattern found in any document
    return f"⚠️  {grant_id}: decimal million not found in documents (no change)"


def auto_detect_candidates(cur):
    """
    Auto-detect grants that likely need decimal refinement.

    Criteria:
    - Has funding amount with "million" keyword
    - No decimal point in display string
    - Has NOT already been refined (no 'auto_decimal_from_docs' correction logged)

    Returns:
        list: Grant IDs that are candidates for refinement
    """
    cur.execute("""
        SELECT g.id
        FROM grants g
        LEFT JOIN manual_corrections m
          ON m.id = g.id AND m.correction_type = 'auto_decimal_from_docs'
        WHERE g.total_fund_gbp IS NOT NULL
          AND (g.total_fund LIKE 'up to £% million' OR g.total_fund LIKE '£% million')
          AND INSTR(g.total_fund, '.') = 0
          AND m.id IS NULL
        ORDER BY g.id
    """)

    return [row[0] for row in cur.fetchall()]


def show_audit_log(db_path):
    """Display audit log of decimal refinements."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                id, old_total_fund, new_total_fund,
                reason, correction_type, applied_at
            FROM manual_corrections
            WHERE correction_type IN ('auto_decimal_from_docs', 'manual_decimal_override')
            ORDER BY applied_at DESC
            LIMIT 20
        """)

        rows = cur.fetchall()

        if not rows:
            print("📋 No decimal refinements found in audit log\n")
            return

        print(f"📋 Decimal Refinement Audit Log (showing last {len(rows)} entries):\n")
        print("=" * 80)

        for row in rows:
            grant_id, old_val, new_val, reason, corr_type, timestamp = row
            print(f"\n🔍 {grant_id} [{corr_type}]")
            print(f"   Before: {old_val}")
            print(f"   After:  {new_val}")
            print(f"   Reason: {reason}")
            print(f"   When:   {timestamp}")

        print("\n" + "=" * 80 + "\n")

    except sqlite3.OperationalError:
        print("📋 No audit log table found\n")

    finally:
        conn.close()


def run_decimal_refinement(db_path="grants.db", grant_ids=None):
    """
    Main function for decimal refinement - can be called from other scripts.

    Args:
        db_path: Path to SQLite database
        grant_ids: List of specific grant IDs to refine, or None to auto-detect

    Returns:
        dict: Statistics about refinements applied
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Ensure audit table exists
    ensure_audit_table(cur)

    # Determine which grants to process
    if grant_ids is None:
        grant_ids = auto_detect_candidates(cur)
        if not grant_ids:
            print("✅ No decimal refinement candidates found (all grants already precise)\n")
            conn.close()
            return {"updated": 0, "skipped": 0, "total": 0}

    # Process each grant
    print(f"🔎 Refining decimal funding amounts for {len(grant_ids)} grant(s)...\n")

    updated = 0
    skipped = 0

    for gid in grant_ids:
        msg = refine_from_documents(cur, gid)
        print(msg)

        if msg.startswith("✅"):
            updated += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()

    print()
    return {
        "updated": updated,
        "skipped": skipped,
        "total": len(grant_ids)
    }


def main():
    parser = argparse.ArgumentParser(
        description="Refine funding amounts to include decimal precision from stored documents"
    )
    parser.add_argument(
        "--db",
        default="grants.db",
        help="Path to SQLite database (default: grants.db)"
    )
    parser.add_argument(
        "--ids",
        help="Comma-separated grant IDs to refine (optional). If omitted, auto-detects candidates."
    )
    parser.add_argument(
        "--show-log",
        action="store_true",
        help="Display audit log of decimal refinements instead of applying corrections"
    )

    args = parser.parse_args()

    if args.show_log:
        show_audit_log(args.db)
    else:
        # Parse grant IDs if provided
        grant_ids = None
        if args.ids:
            grant_ids = [s.strip() for s in args.ids.split(",") if s.strip()]

        # Run refinement
        print("=" * 80)
        print("🔧 Decimal Funding Refinement")
        print("=" * 80)
        print(f"Database: {args.db}")
        if grant_ids:
            print(f"Target grants: {len(grant_ids)} specified")
        else:
            print("Target grants: auto-detect candidates")
        print("=" * 80)
        print()

        stats = run_decimal_refinement(args.db, grant_ids)

        print("=" * 80)
        print("✅ Decimal Refinement Complete")
        print("=" * 80)
        print(f"Updated:  {stats['updated']} grant(s)")
        print(f"Skipped:  {stats['skipped']} grant(s)")
        print(f"Total:    {stats['total']} grant(s) processed")
        print("=" * 80)
        print()


if __name__ == "__main__":
    main()
