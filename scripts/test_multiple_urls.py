#!/usr/bin/env python3
"""
Test the tab-aware NIHR scraper on multiple URLs to verify robustness.
"""

import sys
sys.path.insert(0, '/Users/rileycoleman/grant-analyst-v2')

from src.ingest.nihr_funding import NihrFundingScraper

# Test URLs - a mix of different NIHR page types
TEST_URLS = [
    "https://www.nihr.ac.uk/funding/nihr-james-lind-alliance-priority-setting-partnerships-rolling-funding-opportunity-hsdr-programme/2025331",
    # Add more URLs here if you have them
]

def test_url(scraper, url):
    """Test a single URL and return results."""
    try:
        opp = scraper.scrape(url)

        sections_count = len(opp.sections)
        total_chars = sum(len(s['text']) for s in opp.sections)
        has_tabs = any('#tab-' in s['url'] for s in opp.sections)

        return {
            'success': True,
            'sections': sections_count,
            'chars': total_chars,
            'has_tabs': has_tabs,
            'title': opp.title[:60] + '...' if len(opp.title or '') > 60 else opp.title
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def main():
    print("=" * 80)
    print("TESTING TAB-AWARE NIHR SCRAPER ON MULTIPLE URLs")
    print("=" * 80)
    print()

    scraper = NihrFundingScraper()

    results = []
    for i, url in enumerate(TEST_URLS, 1):
        print(f"[{i}/{len(TEST_URLS)}] Testing: {url}")
        result = test_url(scraper, url)
        results.append((url, result))

        if result['success']:
            print(f"  ✅ Success: {result['sections']} sections, {result['chars']:,} chars")
            print(f"     Tab-based: {'Yes' if result['has_tabs'] else 'No (h2 fallback)'}")
            print(f"     Title: {result['title']}")
        else:
            print(f"  ❌ Failed: {result['error']}")
        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    successful = sum(1 for _, r in results if r['success'])
    with_tabs = sum(1 for _, r in results if r['success'] and r['has_tabs'])

    print(f"Total URLs tested: {len(TEST_URLS)}")
    print(f"Successful: {successful}/{len(TEST_URLS)}")
    print(f"Tab-based extraction: {with_tabs}/{successful}")

    if successful > 0:
        avg_sections = sum(r['sections'] for _, r in results if r['success']) / successful
        avg_chars = sum(r['chars'] for _, r in results if r['success']) / successful
        print(f"Average sections per grant: {avg_sections:.1f}")
        print(f"Average content per grant: {avg_chars:,.0f} chars")

    print()

    if successful == len(TEST_URLS):
        print("✅ All tests passed!")
        return 0
    else:
        print(f"⚠️  {len(TEST_URLS) - successful} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
