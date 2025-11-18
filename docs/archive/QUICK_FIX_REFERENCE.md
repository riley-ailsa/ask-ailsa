# QUICK REFERENCE: Fix Resource Extraction Bug

## TL;DR

**Bug**: `_extract_resources()` re-parses with old h2 method, losing tab-specific resources like application forms.

**Fix**: Use the already-parsed tab-aware sections instead of re-parsing.

**Impact**: 3x more resources captured per grant, including critical application forms.

---

## Files You Have

All in `/home/claude/`:

1. **FIX_RESOURCE_EXTRACTION_BUG.md** ← Full implementation guide
2. **test_resource_extraction.py** ← Test script (single URL)
3. **test_multiple_resource_extraction.py** ← Test script (multiple URLs)
4. **THIS FILE** ← Quick reference

---

## The One Method to Change

**File**: `src/ingest/nihr_funding.py`
**Method**: `_extract_resources()` (around line 380-400)

**Find this**:
```python
def _extract_resources(...):
    section_objs = self._parse_sections_from_headings(soup, base_url)  # BUG
```

**Replace with**:
```python
def _extract_resources(...):
    section_objs = []
    for s in sections:  # Use passed-in sections, not re-parsed
        section_objs.append(NihrSection(...))
```

**Full replacement code** is in FIX_RESOURCE_EXTRACTION_BUG.md

---

## Test Workflow

```bash
# 1. Make the code change (see FIX_RESOURCE_EXTRACTION_BUG.md Step 2)

# 2. Test single URL
python3 test_resource_extraction.py

# Expected: "✅ SUCCESS: Found 1 application form(s)"

# 3. Test multiple URLs
python3 test_multiple_resource_extraction.py

# Expected: "✅ PASS: Good resource extraction across multiple grants"

# 4. If both pass, re-scrape database
python3 scripts/reset_nihr_data.py --db grants.db --confirm
python3 -m src.scripts.backfill_nihr_production --input nihr_links.txt
```

---

## Expected Results

### Before Fix
- **Resources/grant**: ~5
- **Application forms**: NOT captured ❌
- **Total resources**: ~2,250 (450 grants × 5)

### After Fix
- **Resources/grant**: ~15-20
- **Application forms**: Captured ✅
- **Total resources**: ~6,750 (450 grants × 15)

---

## Why This Matters

**Without fix**: Application forms and tab-specific guidance missing
- User asks: "What's the application form?" → Ailsa: "I don't have that"
- Incomplete guidance for applicants

**With fix**: All resources captured
- User asks: "What's the application form?" → Ailsa: "Here's the form: [link]"
- Complete application guidance

---

## Verification

After re-scrape, test in Ask Ailsa:

```
Query: "What application documents do I need for the James Lind Alliance grant?"
```

**Expected response**: Should reference application form template and guidance docs.

---

## Quick Rollback

```bash
cp src/ingest/nihr_funding.py.backup src/ingest/nihr_funding.py
cp grants.db.backup grants.db
```

---

## Status

- [ ] Code changed in `nihr_funding.py`
- [ ] Single URL test passes
- [ ] Multi-URL test passes  
- [ ] Database re-scraped
- [ ] Resources count increased
- [ ] Application forms accessible in Ailsa

---

**Read FIX_RESOURCE_EXTRACTION_BUG.md for complete step-by-step instructions.**
