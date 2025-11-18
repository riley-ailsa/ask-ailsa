# MASTER IMPLEMENTATION GUIDE: NIHR Scraper Fixes

## Overview

This guide covers TWO related fixes for the NIHR scraper:

1. ✅ **Tab-Aware Parsing** (ALREADY DONE)
2. ⚠️ **Resource Extraction Bug** (NEEDS FIXING)

Both are required for complete fix.

---

## Current Status

### ✅ Fix 1: Tab-Aware Parsing (COMPLETE)

**Status**: Already implemented and working
**Evidence**: Test showed 5 sections, 17K chars captured
**What it does**: Captures content from all tabs, not just first/default tab

### ⚠️ Fix 2: Resource Extraction (NEEDS FIXING)

**Status**: Has a bug that needs fixing NOW
**Evidence**: Resources are being re-parsed with old method
**What's broken**: Application forms and tab-specific resources being MISSED
**Impact**: 70% of resources not captured

---

## Why Fix #2 is Critical

Even though tab parsing works, resources are lost because:

1. **Sections parsed correctly** with tabs → ✓ Working
2. **Resources extracted** by re-parsing with old method → ✗ Bug
3. **Result**: Section text captured, but links/documents within sections LOST

**Example**:
- Section "Application guidance" captured ✓
- Application form link IN that section LOST ✗

---

## IMPLEMENTATION: Fix Resource Extraction

### File to Modify
`src/ingest/nihr_funding.py`

### Method to Replace
`_extract_resources()` (around line 380-410)

---

## STEP 1: Find the Current (Buggy) Code

Look for this in `src/ingest/nihr_funding.py`:

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
    section_objs = self._parse_sections_from_headings(soup, base_url)  # 🐛 THIS IS THE BUG
    
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

**The bug**: Line `section_objs = self._parse_sections_from_headings(soup, base_url)`

This ignores the `sections` parameter (which has tab-aware content) and re-parses using the OLD h2-only method.

---

## STEP 2: Replace with Fixed Code

Delete the entire method above and replace with:

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
        soup: Parsed HTML (kept for backward compatibility, not used)
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

## STEP 3: Save and Test

### Test on Single URL

```bash
python3 test_resource_extraction.py
```

**Expected Success Output**:
```
Sections found: 5
Resources found: 15-20

CHECKING FOR APPLICATION FORM
================================================================================

✅ SUCCESS: Found 1 application form(s)

  Title: Download application form template
  URL:   https://www.nihr.ac.uk/.../domestic-outline-application-form-template.docx
  Type:  pdf

SUMMARY
================================================================================

✅ EXCELLENT: Resource extraction working properly
   - 5 sections captured (including tabs)
   - 15 resources found
   - Application forms captured: 1
```

**If you see this**, proceed to Step 4.

**If you see "❌ FAILED: No application forms found"**, the fix didn't work - check that you:
- Replaced the entire method
- Didn't accidentally break indentation
- Saved the file

### Test on Multiple URLs

```bash
python3 test_multiple_resource_extraction.py
```

**Expected Success Output**:
```
SUMMARY
================================================================================

URLs tested: 3
Successful: 3/3
Total sections: 15
Total resources: 45-60
Avg resources per grant: 15-20

✅ PASS: Good resource extraction across multiple grants
```

---

## STEP 4: Re-scrape Database

**ONLY proceed if both tests pass.**

```bash
# Create timestamped backup
cp grants.db grants.db.backup_$(date +%Y%m%d_%H%M%S)

# Clear old NIHR data (with insufficient resources)
python3 scripts/reset_nihr_data.py --db grants.db --confirm

# Re-scrape all 450 NIHR grants with BOTH fixes
python3 -m src.scripts.backfill_nihr_production --input nihr_links.txt

# This will take 30-60 minutes
# Watch for log messages: "Detected N tabs on page" and "Found N resources"
```

---

## STEP 5: Verify Results

```bash
python3 scripts/check_data_balance.py
```

**Expected Results**:

```
=== GRANT COUNT BY SOURCE ===
NIHR:          450 grants
Innovate UK:    36 grants

=== EMBEDDINGS COUNT BY SOURCE ===
NIHR:          67,500-90,000 embeddings  (was 8,234)
Innovate UK:    32,641 embeddings

=== EMBEDDINGS PER GRANT ===
NIHR:          150-200 per grant  (was 18)
Innovate UK:    907 per grant
```

**Key Improvements**:
- ✅ NIHR embeddings: 8,234 → 67,500-90,000 (8-11x increase)
- ✅ Resources per grant: 5 → 15-20 (3-4x increase)
- ✅ Imbalance reduced: 50x → 4-6x (legitimate difference)

---

## STEP 6: Test Ask Ailsa

Open Ask Ailsa and test these queries:

### Test 1: General Search
```
Query: "Show me grants for mental health research"
```
**Expected**: Balanced mix of NIHR and IUK grants (NIHR has many mental health grants)

### Test 2: Application Forms
```
Query: "What application documents do I need for the James Lind Alliance grant?"
```
**Expected**: Ailsa should reference the application form template and guidance documents

### Test 3: Specific Grant Details
```
Query: "Tell me about eligibility requirements for NIHR Programme Grants for Applied Research"
```
**Expected**: Detailed response drawing from eligibility tab content

---

## What Changed

### Before Both Fixes
```
NIHR Page Structure:
├── Tab: Overview [visible]
│   └── Link: General info webpage
├── Tab: Application guidance [HIDDEN]
│   └── Link: Application form template ❌ MISSED
└── Tab: Eligibility [HIDDEN]
    └── Link: Eligibility guide ❌ MISSED

Scraper captures: 1 section, 1 resource
```

### After Both Fixes
```
NIHR Page Structure:
├── Tab: Overview
│   └── Link: General info webpage ✓
├── Tab: Application guidance
│   └── Link: Application form template ✓ NOW CAPTURED
└── Tab: Eligibility
    └── Link: Eligibility guide ✓ NOW CAPTURED

Scraper captures: 5 sections, 15 resources
```

---

## Troubleshooting

### Test Fails: "No application forms found"

**Check**:
1. Did you save the file after editing?
2. Did you replace the ENTIRE method, not just one line?
3. Is indentation correct? (Python is whitespace-sensitive)

**Quick test**:
```python
# In Python shell
from src.ingest.nihr_funding import NihrFundingScraper
import inspect
print(inspect.getsource(NihrFundingScraper._extract_resources))
# Should show the NEW method with "Convert dict sections back to NihrSection objects"
```

### Re-scrape Fails

**Check**:
1. Is `nihr_links.txt` present with valid URLs?
2. Are you connected to the internet?
3. Check logs for specific error messages

**Recovery**:
```bash
cp grants.db.backup_YYYYMMDD_HHMMSS grants.db
```

### Embedding Count Still Low

**Check**:
1. Did both test scripts pass?
2. Did re-scrape complete successfully (all 450 grants)?
3. Did embedding generation run? (depends on your pipeline)

---

## Files Reference

### Implementation
- `src/ingest/nihr_funding.py` - Main scraper (modify this)
- `src/ingest/nihr_funding.py.backup` - Backup for rollback

### Tests
- `test_resource_extraction.py` - Single URL test
- `test_multiple_resource_extraction.py` - Multi-URL test
- `scripts/check_data_balance.py` - Database stats

### Documentation
- **FIX_RESOURCE_EXTRACTION_BUG.md** - Detailed implementation guide
- **QUICK_FIX_REFERENCE.md** - Quick reference
- **THIS FILE** - Master guide

---

## Success Criteria

- [x] Tab-aware parsing working (already done)
- [ ] Resource extraction method replaced
- [ ] Single URL test passes (application form found)
- [ ] Multi-URL test passes (15+ resources per grant)
- [ ] Database re-scraped (450 grants)
- [ ] Embedding count 67K-90K (not 8K)
- [ ] Application forms accessible in Ask Ailsa
- [ ] Balanced NIHR/IUK search results

---

## Next Steps Summary

```bash
# 1. Replace _extract_resources() method in src/ingest/nihr_funding.py
#    (see STEP 2 above for exact code)

# 2. Test
python3 test_resource_extraction.py
python3 test_multiple_resource_extraction.py

# 3. If tests pass, re-scrape
cp grants.db grants.db.backup_$(date +%Y%m%d_%H%M%S)
python3 scripts/reset_nihr_data.py --db grants.db --confirm
python3 -m src.scripts.backfill_nihr_production --input nihr_links.txt

# 4. Verify
python3 scripts/check_data_balance.py

# 5. Test Ask Ailsa with queries above
```

---

## Timeline

- **Code change**: 2 minutes
- **Testing**: 5 minutes
- **Re-scrape**: 30-60 minutes
- **Verification**: 5 minutes

**Total**: ~1 hour

---

**Ready to implement?** Start with STEP 2 - replace the `_extract_resources()` method.
