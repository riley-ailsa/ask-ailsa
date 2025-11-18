#!/usr/bin/env python3
"""
Test that resource extraction captures tab-specific resources.

Specifically tests the James Lind Alliance grant which has an
application form template in the "Application guidance" tab.
"""

from src.ingest.nihr_funding import NihrFundingScraper

def test_resource_extraction():
    """Test that we capture resources from all tabs."""
    scraper = NihrFundingScraper()
    
    # This grant has application form in "Application guidance" tab
    url = "https://www.nihr.ac.uk/funding/nihr-james-lind-alliance-priority-setting-partnerships-rolling-funding-opportunity-hsdr-programme/2025331"
    
    print("=" * 80)
    print("TESTING RESOURCE EXTRACTION")
    print("=" * 80)
    print(f"\nURL: {url}\n")
    
    # Scrape
    print("Scraping...")
    opp = scraper.scrape(url)
    
    print(f"✓ Scraped successfully")
    print(f"\nSections found: {len(opp.sections)}")
    for section in opp.sections:
        print(f"  - {section['title']}")
    
    print(f"\nResources found: {len(opp.resources)}")
    
    # Show all resources
    print("\nAll resources:")
    for i, r in enumerate(opp.resources, 1):
        title = r['title'][:60]
        print(f"  {i:2d}. {title:60s} | {r['type']:8s}")
    
    # Check for application form specifically
    print("\n" + "=" * 80)
    print("CHECKING FOR APPLICATION FORM")
    print("=" * 80)
    
    app_forms = [
        r for r in opp.resources 
        if ('application' in r['title'].lower() and 'form' in r['title'].lower())
        or 'template' in r['title'].lower()
    ]
    
    if app_forms:
        print(f"\n✅ SUCCESS: Found {len(app_forms)} application form(s)")
        for form in app_forms:
            print(f"\n  Title: {form['title']}")
            print(f"  URL:   {form['url']}")
            print(f"  Type:  {form['type']}")
    else:
        print("\n❌ FAILED: No application forms found")
        print("\nThis means the bug is still present - resources from tabs")
        print("are not being captured properly.")
    
    # Check for guidance documents
    guidance_docs = [
        r for r in opp.resources 
        if 'guidance' in r['title'].lower() or 'guide' in r['title'].lower()
    ]
    
    print(f"\n📚 Guidance documents found: {len(guidance_docs)}")
    for doc in guidance_docs[:5]:  # Show first 5
        print(f"  - {doc['title']}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if len(opp.resources) >= 10 and app_forms:
        print("\n✅ EXCELLENT: Resource extraction working properly")
        print(f"   - {len(opp.sections)} sections captured (including tabs)")
        print(f"   - {len(opp.resources)} resources found")
        print(f"   - Application forms captured: {len(app_forms)}")
    elif len(opp.resources) >= 5:
        print("\n⚠️  PARTIAL: Some resources captured, but may be incomplete")
        print(f"   - {len(opp.resources)} resources found")
        print(f"   - Application forms: {len(app_forms)}")
    else:
        print("\n❌ PROBLEM: Very few resources captured")
        print(f"   - Only {len(opp.resources)} resources found")
        print("   - Bug may still be present")
    
    return len(app_forms) > 0


if __name__ == "__main__":
    success = test_resource_extraction()
    exit(0 if success else 1)
