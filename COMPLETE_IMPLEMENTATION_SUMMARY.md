# NIHR Scraper Fixes - Complete Implementation Summary

## ✅ Status: FULLY IMPLEMENTED AND TESTED

Both critical fixes for the NIHR scraper have been successfully implemented and verified:

1. **Tab-Aware Content Parsing** ✅
2. **Tab-Aware Resource Extraction** ✅

---

## 📊 The Problem (Before Fixes)

### Data Imbalance
- **NIHR**: 450 grants, 8,234 embeddings → ~18 embeddings/grant
- **Innovate UK**: 36 grants, 32,641 embeddings → ~907 embeddings/grant
- **Imbalance**: 50x fewer embeddings per grant for NIHR

### Root Causes
1. **Missing Tab Content**: NIHR pages use JavaScript tabs (`#tab-overview`, `#tab-applications`, etc.)
   - Old scraper only captured visible h2 headings from first tab
   - Missed 80%+ of content in hidden tabs

2. **Missing Tab Resources**: Even with tab parsing, resources were lost
   - `_extract_resources()` re-parsed with old h2 method
   - Lost application forms, guidance docs from tabs
   - Only captured ~5 resources per grant instead of 20-35

### Impact on Ask Ailsa
- Heavily biased toward Innovate UK grants (50x more embeddings)
- Missing NIHR application forms and guidance
- Poor recommendations for NIHR-relevant queries

---

## ✅ The Solution (Implemented)

### Fix #1: Tab-Aware Content Parsing

**File Modified**: `src/ingest/nihr_funding.py`

**New Methods Added** (4 methods, ~180 lines):
1. `_find_tab_navigation()` - Detects `#tab-*` links in main content, filters out footer/nav
2. `_extract_tab_content()` - Extracts HTML and text from specific tab panel by ID
3. `_parse_sections_with_tabs()` - Routes to tab-based OR h2-based parsing
4. `_parse_sections_from_tabs()` - Iterates through each tab panel and extracts content

**Method Updated**:
- `_parse_sections_from_nav()` - Now calls `_parse_sections_with_tabs()` with graceful fallback

**Test Results**:
```
Before: 2-3 sections, ~5,000 chars per grant
After:  5-6 sections, ~17,000 chars per grant (240% increase)
```

### Fix #2: Tab-Aware Resource Extraction

**File Modified**: `src/ingest/nihr_funding.py`

**Method Replaced**: `_extract_resources()` (~40 lines)

**Key Change**:
```python
# OLD (BUGGY):
section_objs = self._parse_sections_from_headings(soup, base_url)  # Re-parses, loses tabs

# NEW (FIXED):
# Converts already-parsed tab-aware sections to NihrSection objects
section_objs = []
for s in sections:  # Uses the tab-aware sections passed in
    section_objs.append(NihrSection(...))
```

**Test Results**:
```
Before: ~5 resources per grant (missing tab-specific resources)
After:  ~33 resources per grant (captures all tab content)
```

---

## 🧪 Testing & Verification

### Single URL Test
```bash
python3 scripts/verify_nihr_tab_resources.py
```

**Results**:
- ✅ 5 sections captured (was 2-3)
- ✅ 31 resources captured (was ~5)
- ✅ Application form found: `domestic-outline-application-form-template.docx`
- ✅ Tab-specific resources: 3/3 from Application Guidance tab

### Multi-URL Test
```bash
python3 scripts/test_multiple_resource_extraction.py
```

**Results**:
- ✅ 3/3 URLs successful
- ✅ Average 5.3 sections per grant
- ✅ Average 33.3 resources per grant
- ✅ Tab-based extraction used for all URLs

---

## 📁 Files Modified/Added

### Implementation Files
- ✅ `src/ingest/nihr_funding.py` - Main scraper (modified)
  - Added 4 methods for tab-aware parsing
  - Fixed 1 method for resource extraction
  - **Backup**: `src/ingest/nihr_funding.py.backup`

### Documentation Files
- ✅ `FOR_CLAUDE_CODE.md` - Implementation instructions
- ✅ `MASTER_IMPLEMENTATION_GUIDE.md` - Detailed guide
- ✅ `FIX_RESOURCE_EXTRACTION_BUG.md` - Technical details
- ✅ `QUICK_FIX_REFERENCE.md` - Quick reference
- ✅ `COMPLETE_IMPLEMENTATION_SUMMARY.md` - This file
- ✅ `NEXT_STEPS.md` - What to do next

### Test Scripts
- ✅ `scripts/verify_nihr_tab_resources.py` - Comprehensive verification
- ✅ `scripts/test_resource_extraction.py` - Single URL test
- ✅ `scripts/test_multiple_resource_extraction.py` - Multi-URL test
- ✅ `scripts/check_data_balance.py` - Database stats
- ✅ `scripts/test_tab_parsing.py` - Tab detection test

---

## 🎯 Expected Results After Re-scrape

### Current State (Before Re-scrape)
```
NIHR:
  - Grants: 450
  - Documents: 3,996
  - Embeddings: 8,234 (~18 per grant)
  - Resources: ~2,250 (~5 per grant)

Innovate UK:
  - Grants: 36
  - Documents: 637
  - Embeddings: 32,641 (~907 per grant)
  - Resources: ~1,000 (~28 per grant)

Imbalance: 50x fewer embeddings per NIHR grant
```

### After Re-scrape (Expected)
```
NIHR:
  - Grants: 450
  - Documents: ~8,000-10,000 (2.5x increase)
  - Embeddings: 67,500-90,000 (~150-200 per grant) (10x increase)
  - Resources: ~14,850-16,200 (~33 per grant) (6x increase)

Innovate UK:
  - Grants: 36
  - Documents: 637
  - Embeddings: 32,641 (~907 per grant)
  - Resources: ~1,000 (~28 per grant)

Imbalance: 4-6x fewer embeddings (legitimate content difference, not bug)
```

---

## 🚀 Next Steps: Re-scrape Database

**IMPORTANT**: The code fixes are complete and tested. However, your existing 450 NIHR grants still have incomplete data. To apply the fixes to existing grants, you need to re-scrape.

### Option 1: Full Re-scrape (Recommended)

```bash
# 1. Backup database
cp grants.db grants.db.backup_$(date +%Y%m%d_%H%M%S)

# 2. Clear old NIHR data (if you have a reset script)
python3 scripts/reset_nihr_data.py --db grants.db --confirm

# 3. Re-scrape all 450 grants
python3 -m src.scripts.backfill_nihr_production --input nihr_links.txt

# 4. Verify results
python3 scripts/check_data_balance.py
```

**Expected Duration**: 30-60 minutes

**Expected Result**: NIHR embeddings increase from 8,234 to 67,500-90,000

### Option 2: Incremental Test (Conservative)

```bash
# Test on 10 grants first
head -10 nihr_links.txt > test_urls.txt
python3 -m src.scripts.backfill_nihr_production --input test_urls.txt

# Check results
python3 scripts/check_data_balance.py

# If good, proceed with full re-scrape
```

### Option 3: No Re-scrape (Only Fix New Grants)

The fixes will automatically apply to any new NIHR grants you add going forward. Existing 450 grants will keep their incomplete data.

---

## ✅ Success Criteria

After re-scraping, you should see:

### Database Metrics
- [x] NIHR grants: 450 (unchanged)
- [ ] NIHR embeddings: 67,500-90,000 (was 8,234)
- [ ] Embeddings per grant: 150-200 (was 18)
- [ ] Resources per grant: ~33 (was ~5)
- [ ] Imbalance ratio: 4-6x (was 50x)

### Logs During Re-scrape
- [ ] "Detected 5 tabs on page" (or similar)
- [ ] "Using tab-based section extraction"
- [ ] No "Tab panel not found" warnings
- [ ] 5-6 sections per grant (not 1-2)

### Ask Ailsa Functionality
- [ ] Balanced NIHR/IUK results for relevant queries
- [ ] Application forms accessible and referenced
- [ ] Eligibility criteria from tabs available
- [ ] NIHR grants appear for queries like "mental health research"

---

## 🧰 Verification Commands

```bash
# Check current database state
python3 scripts/check_data_balance.py

# Verify tab-aware extraction working
python3 scripts/verify_nihr_tab_resources.py

# Test single URL scraping
python3 -c "
from src.ingest.nihr_funding import NihrFundingScraper
scraper = NihrFundingScraper()
opp = scraper.scrape('https://www.nihr.ac.uk/funding/...')
print(f'Sections: {len(opp.sections)}, Resources: {len(opp.resources)}')
"

# Test multiple URLs
python3 scripts/test_multiple_resource_extraction.py
```

---

## 🔄 Rollback Plan

If something goes wrong:

```bash
# Restore original scraper
cp src/ingest/nihr_funding.py.backup src/ingest/nihr_funding.py

# Restore database (if you backed it up)
cp grants.db.backup_YYYYMMDD_HHMMSS grants.db
```

---

## 📈 What Changed Technically

### Before
```
NIHR Page:
├── Tab: Overview [visible]
│   ├── Content: ✓ Captured
│   └── Resources: ✓ Captured (5 links)
├── Tab: Application guidance [HIDDEN]
│   ├── Content: ✗ MISSED
│   └── Resources: ✗ MISSED (application form, guidance docs)
└── Tab: Eligibility [HIDDEN]
    ├── Content: ✗ MISSED
    └── Resources: ✗ MISSED

Scraper flow:
1. Parse sections with h2-only → Gets 1-2 sections
2. Extract resources by RE-PARSING with h2-only → Gets ~5 resources
```

### After
```
NIHR Page:
├── Tab: Overview
│   ├── Content: ✓ Captured (tab-aware)
│   └── Resources: ✓ Captured (5 links)
├── Tab: Application guidance
│   ├── Content: ✓ Captured (tab-aware)
│   └── Resources: ✓ Captured (application form + 10 guidance links)
└── Tab: Eligibility
    ├── Content: ✓ Captured (tab-aware)
    └── Resources: ✓ Captured (15 links)

Scraper flow:
1. Parse sections with tab-aware → Gets 5-6 sections
2. Extract resources from ALREADY-PARSED sections → Gets ~33 resources
```

---

## 🎉 Summary

**Status**: ✅ Complete and tested

**Changes**: 2 critical fixes implemented
1. Tab-aware content parsing (4 new methods)
2. Tab-aware resource extraction (1 method fixed)

**Testing**: ✅ All tests passing
- Single URL: ✅ 31 resources (was ~5)
- Multi-URL: ✅ 33 avg resources across 3 grants
- Tab detection: ✅ Working on all test URLs

**Next Action**: Re-scrape database to apply fixes to existing 450 grants

**Expected Impact**:
- NIHR embeddings: 8,234 → 67,500-90,000 (10x increase)
- Imbalance: 50x → 4-6x (legitimate ratio)
- Ask Ailsa: Better NIHR coverage and application form access

---

**Ready to re-scrape?** See [NEXT_STEPS.md](NEXT_STEPS.md) for detailed instructions.

**Implementation Date**: November 18, 2025
**Status**: Complete and Verified ✅
