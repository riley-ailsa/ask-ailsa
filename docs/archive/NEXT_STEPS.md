# Next Steps: NIHR Tab-Aware Parsing

## ✅ What's Been Completed

1. **Tab-aware parsing implemented** in [src/ingest/nihr_funding.py](src/ingest/nihr_funding.py)
2. **Tested on sample URL** - working correctly (5 sections, 17K chars)
3. **Backup created** at `src/ingest/nihr_funding.py.backup`
4. **Test scripts added** to verify functionality

## 🎯 What You Need to Do Now

### Recommended: Full Re-scrape (1-2 hours)

This will apply the fix to all 450 NIHR grants in your database:

```bash
# Step 1: Backup your database
cp grants.db grants.db.backup_$(date +%Y%m%d)

# Step 2: Check if you have a reset script for NIHR data
ls scripts/*reset* scripts/*nihr*

# Step 3: If you have a reset script, use it to clear old NIHR data
# Otherwise, you'll need to create one or manually delete NIHR records

# Step 4: Re-scrape all NIHR grants
# (Replace with your actual backfill command)
python3 -m src.scripts.backfill_nihr_production --input nihr_links.txt

# Step 5: Verify the fix worked
python3 scripts/check_data_balance.py
```

**Expected Results After Re-scrape**:
- NIHR embeddings: **8,234 → 60,000-90,000** (7-10x increase)
- Embeddings per grant: **18 → 150-200**
- Better NIHR coverage in Ask Ailsa searches

### Alternative: Incremental Test (Safer)

If you want to be more cautious:

```bash
# Test on 5-10 grants first
head -10 nihr_links.txt > test_nihr_urls.txt
python3 -m src.scripts.backfill_nihr_production --input test_nihr_urls.txt

# Check the results
python3 scripts/check_data_balance.py

# If good, proceed with full re-scrape
```

### Quick Verification (No Changes)

The new scraper will automatically be used for any new NIHR grants you add. You can:

1. Just wait and see if new grants get better coverage
2. Test with a query in Ask Ailsa to see current behavior
3. Decide later if you want to re-scrape historical data

## 📊 Current State

From `scripts/check_data_balance.py`:

```
NIHR:          450 grants  →  8,234 embeddings  (18 per grant)
Innovate UK:    36 grants  → 32,641 embeddings (907 per grant)

Ratio: Innovate UK has 50x more embeddings per grant
```

This imbalance means Ask Ailsa will over-recommend Innovate UK grants because they dominate the vector search results.

## 🔍 How to Know It's Working

After re-scraping, you should see:

1. **In logs**: Messages like "Detected 5 tabs on page" and "Using tab-based section extraction"
2. **In database**: NIHR embedding count increases to 60K-90K
3. **In Ask Ailsa**: More balanced NIHR recommendations for relevant queries

Test queries that should show NIHR grants:
- "mental health clinical trial funding"
- "healthcare research grants UK"
- "NHS research funding opportunities"

## 📁 Files Reference

**Implementation**:
- [src/ingest/nihr_funding.py](src/ingest/nihr_funding.py) - Main scraper (modified)
- [src/ingest/nihr_funding.py.backup](src/ingest/nihr_funding.py.backup) - Backup (restore if needed)

**Documentation**:
- [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md) - Full implementation summary
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Step-by-step integration guide
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Code snippets
- [scripts/data_balance_report.md](scripts/data_balance_report.md) - Initial analysis

**Test Scripts**:
- [scripts/check_data_balance.py](scripts/check_data_balance.py) - Check database stats
- [scripts/test_tab_parsing.py](scripts/test_tab_parsing.py) - Test tab detection
- [scripts/test_multiple_urls.py](scripts/test_multiple_urls.py) - Test multiple URLs

## ❓ Questions?

### "Do I need to re-scrape?"

**Yes, if** you want to fix the imbalance for existing grants in your database.

**No, if** you're okay with the fix only applying to new grants going forward.

### "Will this break anything?"

No. The implementation:
- ✅ Falls back to h2-based parsing if no tabs detected
- ✅ Returns same data structure as before
- ✅ Has been tested on sample URLs
- ✅ Has backup file for easy rollback

### "What if re-scraping fails?"

```bash
# Restore backup
cp grants.db.backup grants.db
cp src/ingest/nihr_funding.py.backup src/ingest/nihr_funding.py
```

### "How long will re-scraping take?"

- **450 grants** × ~2-3 seconds per grant = **15-25 minutes for scraping**
- **Embedding generation**: Additional time depending on your setup
- **Total estimate**: 1-2 hours

## 🚀 Ready to Proceed?

1. Backup your database: `cp grants.db grants.db.backup`
2. Choose your approach (full re-scrape or incremental)
3. Run the commands above
4. Check results with `python3 scripts/check_data_balance.py`
5. Test Ask Ailsa with NIHR-relevant queries

---

**Need Help?** Check the documentation files listed above or review the implementation in [src/ingest/nihr_funding.py](src/ingest/nihr_funding.py).
