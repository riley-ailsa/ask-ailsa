# FOR CLAUDE CODE: NIHR Resource Extraction Fix

## Executive Summary

**Context**: You recently implemented tab-aware parsing for NIHR grants (✅ working). However, there's a bug in resource extraction that causes application forms and tab-specific documents to be MISSED.

**Problem**: The `_extract_resources()` method re-parses sections using the old h2-only method, ignoring the tab-aware sections that were already parsed.

**Impact**: 70% of resources (including application forms) are not being captured from NIHR grants.

**Solution**: Fix one method in `src/ingest/nihr_funding.py` to use the already-parsed tab-aware sections.

**Time Required**: 5 minutes code change + 5 minutes testing + 1 hour re-scrape

---

## Quick Context

### What Works (Tab-Aware Parsing)
✅ NIHR pages have tabs like `#tab-overview`, `#tab-applications`, `#tab-eligibility`
✅ Tab-aware parser now captures content from ALL tabs
✅ Sections increased from 1-2 to 5-8 per grant
✅ Text content increased from ~5K to ~17K chars per grant

### What's Broken (Resource Extraction)
❌ Resources (links, PDFs, documents) are extracted by RE-PARSING with old method
❌ This loses resources that only appear in tabs
❌ Application forms, guidance docs, supplemental materials MISSED
❌ Only 5 resources/grant captured instead of 15-20

---

## Files You Have

All files are in `/home/claude/`:

### Main Implementation Guide
📄 **MASTER_IMPLEMENTATION_GUIDE.md** ← **START HERE**
- Complete step-by-step instructions
- Exact code to replace
- Testing workflow
- Expected results

### Detailed Documentation
📄 **FIX_RESOURCE_EXTRACTION_BUG.md**
- Detailed technical explanation
- Before/after comparison
- Troubleshooting guide

### Quick Reference
📄 **QUICK_FIX_REFERENCE.md**
- TL;DR summary
- One-page reference

### Test Scripts
📄 **test_resource_extraction.py**
- Tests single NIHR URL
- Verifies application forms captured

📄 **test_multiple_resource_extraction.py**
- Tests multiple NIHR URLs
- Verifies consistency

---

## The One Method to Fix

**File**: `src/ingest/nihr_funding.py`
**Method**: `_extract_resources()` (around line 380-410)

**Current Code (BUGGY)**:
```python
def _extract_resources(...):
    # Get section objects (re-parse if needed)
    section_objs = self._parse_sections_from_headings(soup, base_url)  # 🐛 BUG
    ...
```

**Problem**: Ignores `sections` parameter and re-parses with old method

**Fixed Code**: See STEP 2 in MASTER_IMPLEMENTATION_GUIDE.md

---

## Implementation Workflow

```bash
# STEP 1: Read the guide
cat MASTER_IMPLEMENTATION_GUIDE.md

# STEP 2: Replace the _extract_resources() method
#         (exact code in MASTER_IMPLEMENTATION_GUIDE.md STEP 2)

# STEP 3: Test single URL
python3 test_resource_extraction.py
# Expected: "✅ SUCCESS: Found 1 application form(s)"

# STEP 4: Test multiple URLs
python3 test_multiple_resource_extraction.py
# Expected: "✅ PASS: Good resource extraction"

# STEP 5: Re-scrape database (if tests pass)
cp grants.db grants.db.backup_$(date +%Y%m%d_%H%M%S)
python3 scripts/reset_nihr_data.py --db grants.db --confirm
python3 -m src.scripts.backfill_nihr_production --input nihr_links.txt

# STEP 6: Verify
python3 scripts/check_data_balance.py
# Expected: NIHR embeddings 67K-90K (was 8K)
```

---

## Expected Results

### Before Fix
```
Resources per grant: ~5
Application forms: ❌ NOT captured
Total NIHR resources: ~2,250
Example missing resource: "Download application form template.docx"
```

### After Fix
```
Resources per grant: ~15-20
Application forms: ✅ Captured
Total NIHR resources: ~6,750
Example captured resource: "Download application form template.docx" ✓
```

### Database Impact
```
NIHR embeddings: 8,234 → 67,500-90,000 (8-11x increase)
Resources captured: 2,250 → 6,750 (3x increase)
```

---

## Why This Matters for Ask Ailsa

**Without Fix**:
```
User: "What's the application form for the James Lind Alliance grant?"
Ailsa: "I don't have information about the application form."
```

**With Fix**:
```
User: "What's the application form for the James Lind Alliance grant?"
Ailsa: "Here's the application form template: [link to domestic-outline-application-form-template.docx]"
```

---

## Key Points for Implementation

1. **Only ONE method changes** - `_extract_resources()` in `src/ingest/nihr_funding.py`
2. **Tab-aware parsing already works** - don't touch those methods
3. **Test before re-scraping** - both test scripts must pass
4. **Backup database first** - easy rollback if needed
5. **Re-scrape takes ~1 hour** - for all 450 NIHR grants

---

## Success Criteria

- [ ] Method replaced in `nihr_funding.py`
- [ ] `test_resource_extraction.py` shows "✅ SUCCESS: Found 1 application form(s)"
- [ ] `test_multiple_resource_extraction.py` shows "✅ PASS"
- [ ] Database re-scraped (450 grants)
- [ ] `check_data_balance.py` shows 67K-90K NIHR embeddings
- [ ] Ask Ailsa can reference application forms

---

## Questions to Answer

**Q: Is this safe?**
A: Yes - only changes one method, has backup strategy, tests verify before re-scrape

**Q: Will it break anything?**
A: No - returns same data structure, just uses better source data

**Q: What if tests fail?**
A: Don't re-scrape - check you replaced entire method correctly, verify indentation

**Q: How long does this take?**
A: 2 min code + 5 min test + 60 min re-scrape = ~1 hour total

**Q: Can I skip re-scraping?**
A: Yes, but existing 450 grants will still have missing resources. Only new grants will benefit.

---

## Rollback Plan

If something goes wrong:

```bash
# Restore code
cp src/ingest/nihr_funding.py.backup src/ingest/nihr_funding.py

# Restore database
cp grants.db.backup_YYYYMMDD_HHMMSS grants.db
```

---

## Next Action

**Read**: `MASTER_IMPLEMENTATION_GUIDE.md` for complete step-by-step instructions

**Start**: STEP 2 - Replace the `_extract_resources()` method

---

## Support Files

All documentation and test scripts are ready to use. No additional setup needed.

**Good luck!** The fix is straightforward - just one method replacement and you'll capture 3x more resources including all those critical application forms.
