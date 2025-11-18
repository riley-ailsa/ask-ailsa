# Data Balance Analysis Report

## Summary

This report shows the data distribution across sources (NIHR vs Innovate UK) in the grant database.

## 1. Grant Count by Source

```
nihr                                  450
innovate_uk                            36
```

**Ratio**: NIHR has ~12.5x more grants than Innovate UK (450 vs 36)

## 2. Document Count by Source

```
nihr                                3,996
innovate_uk                           637
```

**Ratio**: NIHR has ~6.3x more documents than Innovate UK (3,996 vs 637)

## 3. Embeddings Count by Source

```
innovate_uk                        32,641
nihr                                8,234
```

**Ratio**: Innovate UK has ~4x MORE embeddings than NIHR (32,641 vs 8,234)

## Key Findings

### The Imbalance Problem

Despite having:
- **12.5x more grants** (450 vs 36)
- **6.3x more documents** (3,996 vs 637)

NIHR only has **0.25x the embeddings** of Innovate UK (8,234 vs 32,641)

This means:
- **NIHR**: ~18 embeddings per grant (8,234 / 450)
- **Innovate UK**: ~907 embeddings per grant (32,641 / 36)

### Why This Matters

The vector search is based on embeddings. With Innovate UK having 50x more embeddings per grant, it will naturally dominate search results even for NIHR-relevant queries.

### Test Query Results

Query: "mental health clinical trial funding"

**Results**: 10/10 results were from NIHR

This is a clearly NIHR-specific query (mental health clinical trials), and the system correctly returned only NIHR results. This suggests the semantic search is working well when the query is specific enough.

## Recommendations

1. **Check NIHR document processing**: Why are NIHR grants generating fewer embeddings?
   - Are NIHR documents shorter?
   - Are NIHR documents not being chunked properly?
   - Is there an issue with NIHR document extraction?

2. **Investigate embedding generation**:
   - Check if NIHR documents are being skipped during embedding generation
   - Verify chunk size settings are appropriate for both sources

3. **Test with broader queries**: The "mental health clinical trial" query is very NIHR-specific. Test with more general queries to see if Innovate UK dominates.

4. **Consider source-aware filtering**: Implement smart filtering based on query analysis to determine which sources are most relevant.
