# Fix: NIHR Resource Extraction Bug

## Problem Statement

The NIHR scraper has a critical bug in resource extraction:

1. **Tab-aware parsing captures all sections** from tabs (✓ Working)
2. **Resource extraction RE-PARSES with old h2 method** (✗ Bug)
3. **Result**: Resources in tab-only content are MISSED

This means application forms, guidance documents, and other important resources that only appear in tabs (like "Application guidance" tab) are not being captured.

## Impact

**Missing Resources**:
- Application form templates (e.g., "domestic-outline-application-form-template.docx")
- Tab-specific guidance documents
- Supplemental PDFs that only appear in certain tabs

**Use Cases Affected**:
- Cannot provide application forms to users
- Cannot help clients understand application requirements
- Vector search missing critical guidance content

## Solution

Fix the `_extract_resources()` method to use the already-parsed tab-aware sections instead of re-parsing with the old h2 method.

---

## Implementation

### File to Modify
`src/ingest/nihr_funding.py`

### Method to Replace
`_extract_resources()` (around line 380-400)

---

## STEP 1: Locate the Buggy Code

Find this method in `src/ingest/nihr_funding.py`:

```python
def _extract_resources(
    self,
    base_url: str,
    soup: BeautifulSoup,
    sections: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extract all resources from sections.
    Calls new _extract_resources_from_sections and converts to dict format.
    """
    # Get section objects (re-parse if needed)
    section_objs = self._parse_sections_from_headings(soup, base_url)  # 🐛 BUG HERE
    
    # Call new resource extractor
    resources = self._extract_resources_from_sections(section_objs, base_url)
    
    # Convert NihrResource objects to dicts for backward compatibility
    return [
        {
            "title": r.title,
            "url": r.url,
            "type": r.kind,
            "scope": r.scope,
            "text": ""  # To be filled by document processor
        }
        for r in resources
    ]
```

**The Bug**: Line with `self._parse_sections_from_headings(soup, base_url)`

This re-parses sections using the OLD h2-based method, ignoring the tab-aware sections that were already parsed and passed in as `sections` parameter.

---

## STEP 2: Replace with Fixed Code

Replace the entire `_extract_resources()` method with this:

```python
def _extract_resources(
    self,
    base_url: str,
    soup: BeautifulSoup,
    sections: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extract all resources from sections.
    
    FIXED: Uses the sections that were already parsed (preserving tab content)
    instead of re-parsing with old h2 method.
    
    Args:
        base_url: Page URL
        soup: Parsed HTML (unused now, kept for compatibility)
        sections: Already-parsed sections (from tab-aware parser)
    
    Returns:
        List of resource dicts
    """
    # Convert dict sections back to NihrSection objects
    # These sections already contain tab content from tab-aware parsing
    section_objs = []
    for s in sections:
        section_objs.append(
            NihrSection(
                name=s["title"],
                slug=s.get("slug", _slugify(s["title"])),
                html=s["html"],
                text=s["text"],
                source_url=s["url"]
            )
        )
    
    # Extract resources from these sections (preserving tab content)
    resources = self._extract_resources_from_sections(section_objs, base_url)
    
    # Convert NihrResource objects to dicts for backward compatibility
    return [
        {
            "title": r.title,
            "url": r.url,
            "type": r.kind,
            "scope": r.scope,
            "text": ""  # To be filled by document processor
        }
        for r in resources
    ]
```

---

## STEP 3: Create Test Script

Create `test_resource_extraction.py` in your project root:

```python
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
```

---

## STEP 4: Test the Fix

```bash
# Run test script
python3 test_resource_extraction.py
```

**Expected Output (AFTER fix)**:
```
TESTING RESOURCE EXTRACTION
================================================================================

URL: https://www.nihr.ac.uk/...

Scraping...
✓ Scraped successfully

Sections found: 5
  - Overview
  - Application guidance
  - Eligibility
  - Key dates
  - Contact

Resources found: 15-20

All resources:
   1. Download application form template                            | pdf
   2. Guidance document                                             | pdf
   3. NIHR website                                                  | webpage
   ...

================================================================================
CHECKING FOR APPLICATION FORM
================================================================================

✅ SUCCESS: Found 1 application form(s)

  Title: Download application form template
  URL:   https://www.nihr.ac.uk/.../domestic-outline-application-form-template.docx
  Type:  pdf

📚 Guidance documents found: 3
  - Guidance document
  - Application guidance notes
  ...

================================================================================
SUMMARY
================================================================================

✅ EXCELLENT: Resource extraction working properly
   - 5 sections captured (including tabs)
   - 15 resources found
   - Application forms captured: 1
```

**Expected Output (BEFORE fix / if still broken)**:
```
Resources found: 3-5

❌ FAILED: No application forms found

This means the bug is still present - resources from tabs
are not being captured properly.

❌ PROBLEM: Very few resources captured
   - Only 3 resources found
   - Bug may still be present
```

---

## STEP 5: Verify on Multiple URLs

Create `test_multiple_resource_extraction.py`:

```python
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
```

Run with:
```bash
python3 test_multiple_resource_extraction.py
```

---

## STEP 6: Re-scrape Database (if tests pass)

Only proceed if Step 4 and Step 5 tests pass successfully.

```bash
# Backup database
cp grants.db grants.db.backup_resource_fix_$(date +%Y%m%d_%H%M%S)

# Reset NIHR data
python3 scripts/reset_nihr_data.py --db grants.db --confirm

# Re-scrape with fixed resource extraction
python3 -m src.scripts.backfill_nihr_production --input nihr_links.txt

# Verify
python3 scripts/check_data_balance.py
```

---

## Expected Results

### Before Fix
```
NIHR Resources: ~5 per grant
- Mostly just top-level links
- Missing application forms
- Missing tab-specific guidance
```

### After Fix
```
NIHR Resources: ~15-20 per grant
- Application form templates ✓
- Tab-specific guidance documents ✓
- All downloadable resources ✓
```

### Database Impact
```
BEFORE:
- 450 grants × 5 resources = ~2,250 resources
- 450 grants × 18 embeddings = 8,234 embeddings

AFTER:
- 450 grants × 15 resources = ~6,750 resources
- 450 grants × 150-200 embeddings = 67,500-90,000 embeddings
```

---

## Rollback Plan

If something goes wrong:

```bash
# Restore code
cd src/ingest
git checkout nihr_funding.py
# OR
cp nihr_funding.py.backup nihr_funding.py

# Restore database
cp grants.db.backup_resource_fix_YYYYMMDD_HHMMSS grants.db
```

---

## Verification Checklist

After implementation:

- [ ] Code modified in `src/ingest/nihr_funding.py`
- [ ] Test script created: `test_resource_extraction.py`
- [ ] Single URL test passes (application form found)
- [ ] Multi-URL test passes (avg 10+ resources per grant)
- [ ] Database backup created
- [ ] Full re-scrape completed
- [ ] Embedding count increased significantly
- [ ] Resources accessible in Ask Ailsa queries

---

## Why This Matters

With this fix, Ask Ailsa can:

1. **Provide application forms directly**: "Here's the application form for this grant"
2. **Answer application questions**: "What documents do I need to apply?"
3. **Guide users through process**: Reference specific guidance documents
4. **Better search results**: More content = better semantic matching

---

## Questions?

**Q: Why wasn't this caught earlier?**
A: The tab-aware parsing was working, but resource extraction was inadvertently using the old method. The sections were captured correctly, but resources within those sections were lost during re-parsing.

**Q: Will this slow down scraping?**
A: No - actually slightly faster since we avoid re-parsing sections.

**Q: Does this affect non-tabbed pages?**
A: No - the sections passed in are already parsed correctly whether they came from tabs or h2 headings.

**Q: Can I test without re-scraping everything?**
A: Yes - run the test scripts first. They test on live URLs without touching your database.

---

## Next Steps

1. **Implement the fix** (replace `_extract_resources()` method)
2. **Run `test_resource_extraction.py`** to verify
3. **If test passes**, run `test_multiple_resource_extraction.py`
4. **If both pass**, proceed with full re-scrape
5. **Verify** improved resource counts in database

---

**Ready to proceed?** Start with Step 1 - locate and replace the buggy method.
