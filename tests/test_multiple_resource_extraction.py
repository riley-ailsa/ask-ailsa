#!/usr/bin/env python3
"""Test resource extraction on multiple NIHR grants."""

from src.ingest.nihr_funding import NihrFundingScraper

TEST_URLS = [
    "https://www.nihr.ac.uk/funding/nihr-james-lind-alliance-priority-setting-partnerships-rolling-funding-opportunity-hsdr-programme/2025331",
    "https://www.nihr.ac.uk/funding/research-patient-benefit-march-2025/2025222-2025223-2025224",
    "https://www.nihr.ac.uk/funding/programme-grants-applied-research-february-2025/2025218-2025219-2025220",
]

scraper = NihrFundingScraper()

print("=" * 80)
print("MULTI-URL RESOURCE EXTRACTION TEST")
print("=" * 80)

results = []

for i, url in enumerate(TEST_URLS, 1):
    print(f"\n[{i}/{len(TEST_URLS)}] Testing: {url}")
    
    try:
        opp = scraper.scrape(url)
        sections = len(opp.sections)
        resources = len(opp.resources)
        
        print(f"  ✓ Sections: {sections}, Resources: {resources}")
        
        results.append({
            "url": url,
            "sections": sections,
            "resources": resources,
            "success": True
        })
    except Exception as e:
        print(f"  ✗ Error: {e}")
        results.append({
            "url": url,
            "sections": 0,
            "resources": 0,
            "success": False
        })

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

total_sections = sum(r["sections"] for r in results)
total_resources = sum(r["resources"] for r in results)
successes = sum(1 for r in results if r["success"])

print(f"\nURLs tested: {len(TEST_URLS)}")
print(f"Successful: {successes}/{len(TEST_URLS)}")
print(f"Total sections: {total_sections}")
print(f"Total resources: {total_resources}")
print(f"Avg resources per grant: {total_resources / len(TEST_URLS):.1f}")

if total_resources >= 30:  # ~10 per grant minimum
    print("\n✅ PASS: Good resource extraction across multiple grants")
else:
    print("\n⚠️  WARNING: Low resource count - may indicate issues")

# Detailed breakdown
print("\n" + "=" * 80)
print("DETAILED RESULTS")
print("=" * 80)

for i, result in enumerate(results, 1):
    status = "✓" if result["success"] else "✗"
    print(f"\n[{i}] {status} {result['url']}")
    print(f"    Sections: {result['sections']}, Resources: {result['resources']}")
