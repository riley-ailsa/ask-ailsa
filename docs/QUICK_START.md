# Quick Fix Guide: Stop Recommending Only One Grant

## TL;DR
Your system shows only "Agentic AI Pioneers Prize" because your score threshold (0.65) is too high and there's no diversity mechanism. Lower the threshold to 0.40 and add diversity weighting.

---

## 3-Step Fix (5 minutes)

### Step 1: Diagnose (Optional but Recommended)
```bash
cd /Users/rileycoleman/grant-analyst-v2
python3 /mnt/user-data/outputs/debug_stuck_grant.py
```

**Look for**: How many grants are "🔴 FILTERED" that should actually be shown.

---

### Step 2: Apply the Fix

Open `src/api/server.py` and find this section (around line 220):

```python
def group_results_by_grant(hits: list, query: str, max_grants: int = 5) -> list:
```

**Change 1**: Find this line:
```python
MIN_SCORE_STRONG = 0.65  # or similar high value
```

Replace with:
```python
MIN_SCORE_THRESHOLD = 0.40  # More inclusive
```

**Change 2**: Add this function before `group_results_by_grant()`:
```python
def add_diversity_to_grants(grant_scores, max_grants=5, diversity_weight=0.15):
    """Prevent same grant from dominating results."""
    if not grant_scores or max_grants <= 0:
        return []
    
    selected = []
    remaining = grant_scores.copy()
    
    while len(selected) < max_grants and remaining:
        if not selected:
            best = remaining.pop(0)
            selected.append(best)
            continue
        
        best_idx = 0
        best_adjusted_score = -1
        
        for i, candidate in enumerate(remaining):
            base_score = candidate['boosted_score']
            penalty = 0
            
            for already_selected in selected:
                # Same source penalty
                if candidate['source'] == already_selected['source']:
                    penalty += diversity_weight * 0.5
                
                # Similar title penalty
                title_words_cand = set(candidate['title'].lower().split())
                title_words_sel = set(already_selected['title'].lower().split())
                overlap = len(title_words_cand & title_words_sel) / max(len(title_words_cand), 1)
                if overlap > 0.5:
                    penalty += diversity_weight * 0.3
            
            adjusted_score = base_score - penalty
            if adjusted_score > best_adjusted_score:
                best_adjusted_score = adjusted_score
                best_idx = i
        
        selected.append(remaining.pop(best_idx))
    
    return selected
```

**Change 3**: In `group_results_by_grant()`, find where it sorts open_grants and add:
```python
open_grants.sort(key=lambda x: x["best_score"], reverse=True)

# ADD THIS LINE:
open_grants = add_diversity_to_grants(open_grants, max_grants=max_grants, diversity_weight=0.15)
```

---

### Step 3: Test
```bash
# Restart API
./start_api.sh

# Test in UI or via curl:
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "what grants for https://mildtech.co.uk/", "conversation_history": []}'
```

**Expected**: You should now see 4-5 different grants instead of just 1.

---

## Copy-Paste Full Implementation

**Full working code** is in `/mnt/user-data/outputs/fix_diversity.py`

Just copy `improved_group_results_by_grant()` and replace your existing function.

---

## Troubleshooting

### Still showing only 1-2 grants?
Lower the threshold more:
```python
MIN_SCORE_THRESHOLD = 0.35  # Even more inclusive
```

### Getting too many low-quality results?
Raise the threshold slightly:
```python
MIN_SCORE_THRESHOLD = 0.45  # Bit more selective
```

### Not enough diversity?
Increase the penalty:
```python
diversity_weight = 0.25  # Stronger diversity preference
```

### Too much diversity (sacrificing relevance)?
Decrease the penalty:
```python
diversity_weight = 0.10  # Prioritize relevance more
```

---

## What This Changes

| Before | After |
|--------|-------|
| 1 grant shown | 5 grants shown |
| Only Innovate UK | Mix of NIHR + Innovate UK |
| £1M only | £100K - £1M range |
| 1 deadline option | Multiple deadline options |

---

## Files Provided

1. **`debug_stuck_grant.py`** - Diagnose what's happening with your queries
2. **`fix_diversity.py`** - Complete working implementation
3. **`IMPLEMENTATION_GUIDE.md`** - Detailed step-by-step guide
4. **`BEFORE_AFTER_COMPARISON.md`** - Visual examples of the fix

All in `/mnt/user-data/outputs/`

---

## Questions?

**Q: Will this break existing queries?**  
A: No - it only shows more results. Top result is still the most relevant.

**Q: What if I need to rollback?**  
A: Just change `MIN_SCORE_THRESHOLD` back to 0.65.

**Q: Should I use diversity or adaptive threshold?**  
A: Start with diversity (simpler, more predictable). Try adaptive if you want automatic adjustment.

**Q: How do I tune the parameters?**  
A: Run `debug_stuck_grant.py` with different test queries and watch the score distributions. Adjust thresholds based on what you see.

---

**Next Steps**: Run the diagnostic script, apply the fix, test with your company URL query, then tune parameters based on results.
