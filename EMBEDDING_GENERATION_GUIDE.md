# NIHR Embedding Generation Guide

## 🎯 Current Situation

You successfully scraped 450 NIHR grants with the new tab-aware scraper, but **embeddings were not generated**.

### Stats
- ✅ 450 NIHR grants scraped
- ✅ 2,483 NIHR documents created
- ⚠️ 832 documents have embeddings (33%)
- ❌ **1,651 documents need embeddings** (67%)

## 🚀 Solution: Generate Embeddings

I've created [scripts/generate_nihr_embeddings.py](scripts/generate_nihr_embeddings.py) which will:
1. Find all NIHR documents without embeddings
2. Generate embeddings in batches of 50
3. Show progress with ETA
4. Verify completion

### Run It Now

```bash
# Generate embeddings for all 1,651 NIHR documents
python3 scripts/generate_nihr_embeddings.py
```

**Estimated Time**: ~13-14 minutes
**Estimated Cost**: ~$0.17 (at text-embedding-3-small rates)
**Batch Size**: 50 documents per batch

### What Will Happen

The script will:
1. ✅ Load OPENAI_API_KEY from .env file
2. ✅ Find 1,651 NIHR documents without embeddings
3. ✅ Process in batches of 50
4. ✅ Show progress: `Batch 1/34 (50 documents)...`
5. ✅ Display ETA and rate: `Rate: 2.3 docs/sec, ETA: 11.2 min`
6. ✅ Verify final count at the end

### Expected Results

After completion:
```
Total NIHR embeddings: 60,000-90,000 (was ~8,000)
Embeddings per grant: 150-200 (was 18)
```

## 📊 Verify After Completion

```bash
# Check embedding counts
python3 scripts/check_data_balance.py
```

**Expected Output**:
```
NIHR embeddings: 60,000-90,000
Innovate UK embeddings: 32,641
Ratio: 4-6x (legitimate content difference, not 50x bug)
```

## 🔍 Why This Happened

The backfill script ([src/scripts/backfill_nihr_production.py](src/scripts/backfill_nihr_production.py)) DOES have embedding generation code (lines 259-264):

```python
# Generate embeddings (if vector index available)
if vector_index:
    try:
        vector_index.index_documents(documents)
    except Exception as e:
        logger.warning(f"Failed to generate embeddings: {e}")
```

However, it looks like:
1. Some documents (832) did get embeddings
2. Most (1,651) failed - possibly due to:
   - Rate limiting errors (not caught)
   - API timeouts
   - Individual document failures that didn't stop the scraper

The new script is more robust:
- Processes in smaller batches (50 vs all at once)
- Shows progress and ETA
- Continues on batch failures
- Verifies completion

## 🎉 What This Fixes

**Before** (current state):
- NIHR: 8,234 embeddings (~18 per grant)
- Ask Ailsa: Heavy bias toward Innovate UK

**After** (once embeddings generated):
- NIHR: 60,000-90,000 embeddings (~150-200 per grant)
- Ask Ailsa: Balanced recommendations
- Application forms and guidance docs searchable
- Better NIHR grant discovery

## 📁 Files Reference

**Embedding Script**:
- [scripts/generate_nihr_embeddings.py](scripts/generate_nihr_embeddings.py) - Run this!

**Check Results**:
- [scripts/check_data_balance.py](scripts/check_data_balance.py) - Verify counts

**Documentation**:
- [COMPLETE_IMPLEMENTATION_SUMMARY.md](COMPLETE_IMPLEMENTATION_SUMMARY.md) - Full implementation details
- [README_NIHR_FIXES.md](README_NIHR_FIXES.md) - Quick start guide

## ⏱️ Timeline

1. **Run embedding generation**: ~14 minutes
2. **Verify results**: `python3 scripts/check_data_balance.py` (instant)
3. **Test Ask Ailsa**: Search for "mental health research" (should show NIHR grants)

## 🆘 Troubleshooting

### "OPENAI_API_KEY not set"
The script now loads from .env automatically. If you still see this:
```bash
# Check .env exists and has the key
cat .env | grep OPENAI_API_KEY
```

### Slow Generation
Normal rate is 2-3 docs/sec. If slower:
- Check internet connection
- OpenAI API might have rate limits
- Script will retry automatically

### Batch Failures
The script continues on batch failures and reports at the end. Check logs for specific errors.

---

**Ready?** Run: `python3 scripts/generate_nihr_embeddings.py`

**Date**: November 18, 2025
**Status**: Ready to run
**Next Step**: Generate embeddings (~14 min)
