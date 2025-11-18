#!/usr/bin/env python3
"""
Automated evaluation script for search quality.

Runs a test suite of queries and validates expected content appears in results.

Usage:
    python3 scripts/run_eval.py
    python3 scripts/run_eval.py --eval-file custom_queries.json
"""

import json
import requests
import argparse
from datetime import datetime

API_URL = "http://localhost:8000"


def evaluate(eval_file="evaluation_queries.json", output_file=None):
    """
    Run evaluation suite and report results.

    Args:
        eval_file: Path to evaluation queries JSON
        output_file: Optional path to save detailed results
    """
    print("=" * 80)
    print("🔍 Search Quality Evaluation")
    print("=" * 80)
    print(f"Evaluation set: {eval_file}")
    print(f"API endpoint:   {API_URL}")
    print(f"Timestamp:      {datetime.now().isoformat()}")
    print("=" * 80)
    print()

    try:
        with open(eval_file) as f:
            eval_set = json.load(f)
    except FileNotFoundError:
        print(f"❌ Evaluation file not found: {eval_file}")
        return

    results = []

    for idx, item in enumerate(eval_set, 1):
        query = item["query"]
        expected = item["expected_contains"]
        notes = item.get("notes", "")

        print(f"\n[{idx}/{len(eval_set)}] Evaluating: {query}")
        if notes:
            print(f"    Notes: {notes}")

        try:
            resp = requests.get(
                f"{API_URL}/search",
                params={"query": query, "top_k": 10, "active_only": False},
                timeout=30
            )
            resp.raise_for_status()
            hits = resp.json()["results"]
        except requests.exceptions.RequestException as e:
            print(f"    ❌ API Error: {e}")
            results.append({
                "query": query,
                "expected": expected,
                "score": 0,
                "passed": False,
                "error": str(e)
            })
            continue

        # Check if expected terms appear in results
        hit_text = json.dumps(hits).lower()
        matches = [e for e in expected if e.lower() in hit_text]
        score = len(matches)

        result = {
            "query": query,
            "expected": expected,
            "matches": matches,
            "score": score,
            "total_expected": len(expected),
            "passed": score == len(expected),
            "total_hits": len(hits),
            "notes": notes
        }
        results.append(result)

        # Print result
        status = "✅ PASS" if result["passed"] else "⚠️  PARTIAL" if score > 0 else "❌ FAIL"
        print(f"    {status} Score: {score}/{len(expected)}")
        if matches:
            print(f"    Matched: {', '.join(matches)}")
        if score < len(expected):
            missing = [e for e in expected if e not in matches]
            print(f"    Missing: {', '.join(missing)}")

    # Summary
    print("\n" + "=" * 80)
    print("📊 EVALUATION SUMMARY")
    print("=" * 80)

    passed = sum(1 for r in results if r.get("passed", False))
    partial = sum(1 for r in results if r.get("score", 0) > 0 and not r.get("passed", False))
    failed = len(results) - passed - partial

    print(f"Total queries:  {len(results)}")
    print(f"✅ Passed:      {passed} ({100*passed/len(results):.1f}%)")
    print(f"⚠️  Partial:     {partial} ({100*partial/len(results):.1f}%)")
    print(f"❌ Failed:      {failed} ({100*failed/len(results):.1f}%)")
    print()

    # Save detailed results if requested
    if output_file:
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "eval_file": eval_file,
                "summary": {
                    "total": len(results),
                    "passed": passed,
                    "partial": partial,
                    "failed": failed
                },
                "results": results
            }, f, indent=2)
        print(f"📄 Detailed results saved to: {output_file}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run search quality evaluation"
    )
    parser.add_argument(
        "--eval-file",
        default="evaluation_queries.json",
        help="Path to evaluation queries JSON"
    )
    parser.add_argument(
        "--output",
        help="Path to save detailed results JSON"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API base URL"
    )

    args = parser.parse_args()
    API_URL = args.api_url

    evaluate(args.eval_file, args.output)
