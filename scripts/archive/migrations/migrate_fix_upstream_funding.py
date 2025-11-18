#!/usr/bin/env python3
"""
Migration script: auto-detect and fix truncated or incomplete funding amounts.

Features:
- Applies verified manual corrections (3 known cases)
- Auto-detects suspiciously small funding (< £100k)
- Infers missing magnitudes (e.g., "£4" → "£4 million")
- Logs all changes in an audit table
- Can be run manually OR automatically at the end of ingestion

Usage:
    # Manual execution
    python3 scripts/migrate_fix_upstream_funding.py --db grants.db

    # View audit log
    python3 scripts/migrate_fix_upstream_funding.py --db grants.db --show-log

    # Automatic (called from backfill script)
    from scripts.migrate_fix_upstream_funding import run_funding_normalization
    run_funding_normalization("grants.db")
"""

import sqlite3
import argparse
from datetime import datetime
import re


# ✅ Verified manual corrections (confirmed from Innovate UK page body text)
VERIFIED_CORRECTIONS = {
    "innovate_uk_2293": {
        "display": "up to £1.1 million",
        "value": 1_100_000,
        "title": "Resource efficiency for resilience and sustainability FS"
    },
    "innovate_uk_2006": {
        "display": "up to £4.8 million",
        "value": 4_800_000,
        "title": "Farming Innovation Programme: Feasibility Round 4"
    },
    "innovate_uk_2010": {
        "display": "up to £7.8 million",
        "value": 7_800_000,
        "title": "Farming Innovation Programme: Small R&D Partnership Projects Rd 4"
    },
}

# 🔎 Threshold for suspicious funding amounts
MIN_REASONABLE_GBP = 100_000


def create_audit_table(cur):
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


def log_correction(cur, grant_id, old_display, old_value, new_display, new_value, reason, correction_type):
    """
    Record every manual or automatic correction in audit table.

    Args:
        cur: Database cursor
        grant_id: Grant identifier
        old_display: Original funding display string
        old_value: Original numeric value
        new_display: Corrected display string
        new_value: Corrected numeric value
        reason: Explanation of correction
        correction_type: "manual" or "automatic"
    """
    cur.execute("""
        INSERT INTO manual_corrections (
            id, old_total_fund, old_total_fund_gbp,
            new_total_fund, new_total_fund_gbp,
            reason, applied_at, correction_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        grant_id,
        old_display,
        old_value,
        new_display,
        new_value,
        reason,
        datetime.utcnow().isoformat(),
        correction_type
    ))


def apply_verified_corrections(cur):
    """
    Apply verified manual corrections from known upstream issues.

    These corrections have been manually confirmed by inspecting the full
    Innovate UK page text where headers show abbreviated values.

    Returns:
        int: Number of corrections applied
    """
    print("📘 Applying verified funding corrections...\n")

    applied = 0

    for grant_id, correction in VERIFIED_CORRECTIONS.items():
        cur.execute(
            "SELECT total_fund, total_fund_gbp FROM grants WHERE id = ?",
            (grant_id,)
        )
        row = cur.fetchone()

        if not row:
            print(f"⚠️  Skipped {grant_id}: not found in database")
            continue

        old_display, old_value = row
        new_display = correction["display"]
        new_value = correction["value"]

        # Skip if already correct
        if old_value == new_value:
            print(f"ℹ️  {grant_id}: already correct (£{new_value:,})")
            continue

        # Apply correction
        cur.execute("""
            UPDATE grants
            SET total_fund = ?, total_fund_gbp = ?
            WHERE id = ?
        """, (new_display, new_value, grant_id))

        # Log correction
        log_correction(
            cur,
            grant_id,
            old_display,
            old_value,
            new_display,
            new_value,
            reason="Verified manual correction (decimal confirmed from source page body text)",
            correction_type="manual"
        )

        print(f"✅ {grant_id}: {old_display} → {new_display} (£{new_value:,})")
        applied += 1

    print()
    return applied


def auto_detect_and_fix_suspicious(cur):
    """
    Detect suspiciously small funding amounts and infer missing magnitudes.

    Uses heuristic: if funding < £100k and string contains "£X" without
    magnitude indicator ("million"/"thousand"), assume "million".

    Returns:
        int: Number of automatic corrections applied
    """
    print(f"🤖 Scanning for suspiciously small funding amounts (<£{MIN_REASONABLE_GBP:,})...\n")

    cur.execute("""
        SELECT id, total_fund, total_fund_gbp
        FROM grants
        WHERE total_fund_gbp IS NOT NULL
        AND total_fund_gbp < ?
    """, (MIN_REASONABLE_GBP,))

    rows = cur.fetchall()

    if not rows:
        print("✅ No suspiciously small values detected.\n")
        return 0

    applied = 0

    for grant_id, display, value in rows:
        # Skip if already in verified corrections
        if grant_id in VERIFIED_CORRECTIONS:
            continue

        if not display:
            print(f"⚠️  Skipped {grant_id}: no display string")
            continue

        # Heuristic: if contains "£" but not "million"/"thousand", assume "million"
        if "£" in display and "million" not in display.lower() and "thousand" not in display.lower():
            try:
                # Extract numeric value from string
                number_match = re.search(r'£?\s*(\d+\.?\d*)', display)
                if not number_match:
                    print(f"⚠️  Skipped {grant_id}: couldn't extract number from '{display}'")
                    continue

                number = float(number_match.group(1))
                inferred_gbp = int(number * 1_000_000)

                # Construct new display string
                new_display = display.strip()
                if "million" not in new_display.lower():
                    # Insert "million" after the number
                    new_display = re.sub(
                        r'(£?\s*\d+\.?\d*)',
                        r'\1 million',
                        new_display,
                        count=1
                    )

                # Apply correction
                cur.execute("""
                    UPDATE grants
                    SET total_fund = ?, total_fund_gbp = ?
                    WHERE id = ?
                """, (new_display, inferred_gbp, grant_id))

                # Log correction
                log_correction(
                    cur,
                    grant_id,
                    display,
                    value,
                    new_display,
                    inferred_gbp,
                    reason="Auto-inferred missing 'million' magnitude (heuristic for values <£100k)",
                    correction_type="automatic"
                )

                print(f"🧠 {grant_id}: {display} → {new_display} (£{inferred_gbp:,})")
                applied += 1

            except Exception as e:
                print(f"⚠️  Skipped {grant_id}: failed to infer ({e})")

    print()
    return applied


def run_funding_normalization(db_path="grants.db"):
    """
    Main function for funding normalization - can be called from other scripts.

    Args:
        db_path: Path to SQLite database

    Returns:
        dict: Statistics about corrections applied
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Ensure audit table exists
    create_audit_table(cur)

    # Apply corrections
    manual_count = apply_verified_corrections(cur)
    auto_count = auto_detect_and_fix_suspicious(cur)

    conn.commit()
    conn.close()

    return {
        "manual_corrections": manual_count,
        "automatic_corrections": auto_count,
        "total_corrections": manual_count + auto_count
    }


def show_audit_log(db_path):
    """Display audit log of all corrections."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                id, old_total_fund, new_total_fund,
                reason, correction_type, applied_at
            FROM manual_corrections
            ORDER BY applied_at DESC
            LIMIT 20
        """)

        rows = cur.fetchall()

        if not rows:
            print("📋 No corrections found in audit log\n")
            return

        print(f"📋 Funding Corrections Audit Log (showing last {len(rows)} entries):\n")
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
        print("📋 No audit log table found (no corrections applied yet)\n")

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Fix and normalize small or incorrect funding values"
    )
    parser.add_argument(
        "--db",
        default="grants.db",
        help="Path to SQLite database (default: grants.db)"
    )
    parser.add_argument(
        "--show-log",
        action="store_true",
        help="Display audit log instead of applying corrections"
    )

    args = parser.parse_args()

    if args.show_log:
        show_audit_log(args.db)
    else:
        print("=" * 80)
        print("🔧 Funding Normalization Migration Started")
        print("=" * 80)
        print(f"Database: {args.db}")
        print(f"Started:  {datetime.utcnow().isoformat()}")
        print("=" * 80)
        print()

        stats = run_funding_normalization(args.db)

        print("=" * 80)
        print("✅ Funding Normalization Complete")
        print("=" * 80)
        print(f"Manual corrections:    {stats['manual_corrections']}")
        print(f"Automatic corrections: {stats['automatic_corrections']}")
        print(f"Total corrections:     {stats['total_corrections']}")
        print("=" * 80)
        print()


if __name__ == "__main__":
    main()
