#!/usr/bin/env python3
"""
Generate GPT summaries for all grants and cache in database.

Usage:
    export OPENAI_API_KEY="sk-..."

    # Test with 10 grants
    python3 scripts/generate_grant_summaries.py --db grants.db --max-grants 10

    # Generate for all grants
    python3 scripts/generate_grant_summaries.py --db grants.db
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import sqlite3
from typing import List, Optional
from datetime import datetime

from src.storage.grant_store import GrantStore
from src.storage.document_store import DocumentStore
from src.llm.client import LLMClient


DB_PATH_DEFAULT = "grants.db"
SUMMARY_MODEL = "gpt-4o-mini"  # Fast and cost-effective for summaries


def _get_existing_ids(conn: sqlite3.Connection) -> set:
    """Get grant IDs that already have summaries."""
    cur = conn.cursor()
    cur.execute("SELECT grant_id FROM grant_summaries")
    return {row[0] for row in cur.fetchall()}


def _choose_docs_for_grant(docs) -> List[str]:
    """
    Select most relevant documents for summarization.

    Priority:
    1. Overview/summary sections
    2. Research specification/application guidance
    3. Eligibility criteria
    4. Fallback: first 2-4 documents

    Returns:
        List of document text strings
    """
    if not docs:
        return []

    def _score_doc(doc) -> int:
        """Score document relevance for summarization."""
        dt = (doc.doc_type or "").lower()

        # Highest priority: overview/summary
        if "overview" in dt or "summary" in dt:
            return 10

        # High priority: specifications and guidance
        if any(keyword in dt for keyword in [
            "research-specification",
            "research-plan",
            "application-guidance",
            "eligibility"
        ]):
            return 5

        # Medium priority: scope and themes
        if any(keyword in dt for keyword in [
            "scope",
            "strategic-themes",
            "objectives"
        ]):
            return 3

        # Lower priority: other sections
        return 1

    # Sort by relevance and take top 4
    sorted_docs = sorted(docs, key=_score_doc, reverse=True)

    texts: List[str] = []
    for doc in sorted_docs[:4]:
        if doc.text and doc.text.strip():
            texts.append(doc.text.strip())

    return texts


def _build_context(grant, docs) -> str:
    """
    Build context string from grant and documents for summarization.

    Args:
        grant: Grant object
        docs: List of documents

    Returns:
        Context string (truncated to ~6000 chars to fit token limits)
    """
    pieces = _choose_docs_for_grant(docs)

    if not pieces:
        return ""

    # Join documents with separators
    joined = "\n\n---\n\n".join(pieces)

    # Truncate to reasonable length (leaves room for prompts)
    return joined[:6000]


def generate_summaries(
    db_path: str,
    max_grants: Optional[int] = None,
    force_regenerate: bool = False
) -> None:
    """
    Generate GPT summaries for grants.

    Args:
        db_path: Path to database
        max_grants: Optional limit on number to generate (for testing)
        force_regenerate: If True, regenerate existing summaries
    """
    print("=" * 80)
    print("📝 Grant Summary Generation")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Model:    {SUMMARY_MODEL}")
    if max_grants:
        print(f"Limit:    {max_grants} grants")
    print("=" * 80)
    print()

    conn = sqlite3.connect(db_path)
    existing_ids = _get_existing_ids(conn)

    print(f"Found {len(existing_ids)} existing summaries")
    if not force_regenerate:
        print("Skipping grants with existing summaries")
    print()

    grant_store = GrantStore(db_path)
    doc_store = DocumentStore(db_path)
    llm = LLMClient(model=SUMMARY_MODEL)

    processed = 0
    created = 0
    skipped = 0
    failed = 0

    cur = conn.cursor()

    # Fetch all grants
    grants = grant_store.list_grants(limit=10000, offset=0, active_only=False)

    print(f"Processing {len(grants)} grants...")
    print()

    for idx, grant in enumerate(grants, 1):
        if max_grants is not None and processed >= max_grants:
            print(f"Reached limit of {max_grants} grants")
            break

        processed += 1

        # Skip if already summarized (unless force_regenerate)
        if grant.id in existing_ids and not force_regenerate:
            skipped += 1
            continue

        # Get documents for grant
        docs = doc_store.get_documents_for_grant(grant.id)
        context = _build_context(grant, docs)

        if not context:
            print(f"[{idx}/{len(grants)}] ⚠️  {grant.id}: No context available")
            failed += 1
            continue

        # Build prompts
        system_prompt = (
            "You write concise, factual summaries of research and innovation "
            "funding opportunities.\n\n"
            "Requirements:\n"
            "- Write exactly 2-3 sentences\n"
            "- State what the funding is for, who can apply, and key themes\n"
            "- Only mention amounts/dates if explicitly stated in context\n"
            "- Use neutral, professional language (no marketing speak)\n"
            "- Be specific about domain/sector when mentioned\n"
        )

        user_prompt = (
            f"Grant Title: {grant.title}\n"
            f"Source: {grant.source}\n\n"
            f"Context from grant documents:\n{context}\n\n"
            "Generate a 2-3 sentence summary of this funding opportunity."
        )

        # Generate summary
        try:
            summary = llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
        except Exception as e:
            print(f"[{idx}/{len(grants)}] ❌ {grant.id}: LLM error - {e}")
            failed += 1
            continue

        summary = (summary or "").strip()

        if not summary:
            print(f"[{idx}/{len(grants)}] ❌ {grant.id}: Empty summary")
            failed += 1
            continue

        # Store in database
        try:
            cur.execute(
                """
                INSERT OR REPLACE INTO grant_summaries (grant_id, summary, model)
                VALUES (?, ?, ?)
                """,
                (grant.id, summary, SUMMARY_MODEL),
            )
            conn.commit()
            created += 1

            # Show preview
            preview = summary[:100] + "..." if len(summary) > 100 else summary
            print(f"[{idx}/{len(grants)}] ✅ {grant.id}: {preview}")

        except Exception as e:
            print(f"[{idx}/{len(grants)}] ❌ {grant.id}: Database error - {e}")
            failed += 1
            continue

    conn.close()

    # Final statistics
    print()
    print("=" * 80)
    print("📊 Summary Generation Complete")
    print("=" * 80)
    print(f"Processed:        {processed}")
    print(f"Created:          {created}")
    print(f"Skipped:          {skipped}")
    print(f"Failed:           {failed}")
    print("=" * 80)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate GPT summaries for grants"
    )
    parser.add_argument(
        "--db",
        default=DB_PATH_DEFAULT,
        help="Path to SQLite database"
    )
    parser.add_argument(
        "--max-grants",
        type=int,
        default=None,
        help="Maximum number of grants to process (for testing)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate existing summaries"
    )

    args = parser.parse_args()
    generate_summaries(args.db, args.max_grants, args.force)


if __name__ == "__main__":
    main()
