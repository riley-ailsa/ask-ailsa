#!/usr/bin/env python3
"""
Test script for tab-aware NIHR section parsing.

This tests the new tab detection logic on a real NIHR page
without modifying the actual scraper yet.

Usage:
    python3 test_tab_parsing.py
"""

import sys
from pathlib import Path
from bs4 import BeautifulSoup
import requests

# Test URL - known to have tabs
TEST_URL = "https://www.nihr.ac.uk/funding/nihr-james-lind-alliance-priority-setting-partnerships-rolling-funding-opportunity-hsdr-programme/2025331"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

def test_tab_detection():
    """Test if we can detect tabs on NIHR pages."""
    print("=" * 80)
    print("TAB DETECTION TEST")
    print("=" * 80)
    print(f"\nFetching: {TEST_URL}\n")

    # Fetch page
    response = requests.get(TEST_URL, headers=DEFAULT_HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    
    print("✓ Page fetched successfully")
    print(f"  HTML size: {len(response.text):,} chars\n")
    
    # Look for tab navigation
    print("Looking for tab navigation...")
    
    # Strategy 1: Find <ul> with tab-related classes
    tab_containers = soup.find_all("ul", class_=lambda x: x and ("tab" in str(x).lower() or "nav" in str(x).lower()))
    print(f"  Found {len(tab_containers)} potential tab containers")
    
    # Strategy 2: Find links with #tab- pattern
    tab_links = soup.find_all("a", href=lambda x: x and x.startswith("#tab-"))
    print(f"  Found {len(tab_links)} links with #tab- pattern")
    
    if tab_links:
        print("\n📑 Tabs detected:")
        for link in tab_links[:10]:  # Show first 10
            href = link.get("href")
            text = link.get_text(strip=True)
            print(f"    - {text:30s} → {href}")
    else:
        print("\n❌ No tabs found")
    
    # Look for tab panels
    print("\nLooking for tab panels...")
    tab_panels = soup.find_all("div", id=lambda x: x and x.startswith("tab-"))
    print(f"  Found {len(tab_panels)} tab panels")
    
    if tab_panels:
        print("\n📄 Tab panels:")
        for panel in tab_panels:
            panel_id = panel.get("id")
            # Count content inside
            text_length = len(" ".join(panel.stripped_strings))
            print(f"    - #{panel_id:30s} → {text_length:6,} chars")
    
    # Current h2-based approach (what we're currently getting)
    print("\n" + "=" * 80)
    print("CURRENT H2-BASED EXTRACTION (what we get now)")
    print("=" * 80)
    
    main = soup.find("main") or soup
    h2s = main.find_all("h2")
    print(f"\nFound {len(h2s)} h2 headings")
    
    total_h2_content = 0
    for h2 in h2s[:10]:  # Show first 10
        title = h2.get_text(strip=True)
        # Count content until next h2
        content_chars = 0
        for sib in h2.next_siblings:
            if isinstance(sib, type(h2)) and sib.name == "h2":
                break
            if hasattr(sib, 'stripped_strings'):
                content_chars += len(" ".join(sib.stripped_strings))
        
        total_h2_content += content_chars
        print(f"  - {title:40s} → {content_chars:6,} chars")
    
    print(f"\n📊 Total content from h2 approach: {total_h2_content:,} chars")
    
    # Tab-based approach (what we'll get)
    if tab_panels:
        print("\n" + "=" * 80)
        print("NEW TAB-BASED EXTRACTION (what we'll get)")
        print("=" * 80)
        
        total_tab_content = 0
        for panel in tab_panels:
            panel_id = panel.get("id")
            text_length = len(" ".join(panel.stripped_strings))
            total_tab_content += text_length
        
        print(f"\n📊 Total content from tab approach: {total_tab_content:,} chars")
        
        improvement = ((total_tab_content - total_h2_content) / total_h2_content * 100) if total_h2_content > 0 else 0
        print(f"📈 Improvement: {improvement:.1f}% more content")
        
        if improvement > 200:
            print("\n🎉 EXCELLENT! Tab-based extraction captures significantly more content!")
        elif improvement > 50:
            print("\n✅ GOOD! Tab-based extraction captures notably more content")
        else:
            print("\n⚠️  Minor improvement - this page might not be tab-heavy")


def test_specific_tab_extraction():
    """Test extracting content from a specific tab."""
    print("\n\n" + "=" * 80)
    print("SPECIFIC TAB CONTENT TEST")
    print("=" * 80)

    response = requests.get(TEST_URL, headers=DEFAULT_HEADERS, timeout=30)
    soup = BeautifulSoup(response.text, "lxml")
    
    # Try to find the "overview" tab
    overview_panel = soup.find("div", id="tab-overview")
    
    if overview_panel:
        print("\n✓ Found 'tab-overview' panel")
        
        # Extract text
        text = " ".join(overview_panel.stripped_strings)
        
        print(f"  Length: {len(text):,} chars")
        print(f"  Preview: {text[:200]}...")
    else:
        print("\n❌ Could not find 'tab-overview' panel")
        
        # Show all divs with IDs for debugging
        divs_with_ids = soup.find_all("div", id=True)
        print(f"\nFound {len(divs_with_ids)} divs with IDs:")
        for div in divs_with_ids[:20]:
            div_id = div.get("id")
            if "tab" in div_id.lower():
                print(f"  - {div_id}")


if __name__ == "__main__":
    try:
        test_tab_detection()
        test_specific_tab_extraction()
        
        print("\n\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print("""
If tabs were detected and show significantly more content:
→ Tab-aware parsing will solve your embedding imbalance!
→ Proceed with integration into nihr_funding.py

If no tabs found:
→ This specific page might not use tabs
→ Try testing with a different NIHR URL
→ The fallback to h2-based parsing will still work
        """)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
