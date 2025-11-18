# How to Fix the "Stuck Grant" Issue

## Problem Summary
Your system keeps recommending only the "Agentic AI Pioneers Prize" because:
1. **High score threshold** (0.65) filters out most grants
2. **No diversity mechanism** - system optimizes for relevance only
3. **Semantic boosting** amplifies already-high-scoring grants
4. **Company URL parsing** extracts generic keywords like "AI" that match one grant perfectly

## Solution: Add Diversity + Lower Threshold

### Step 1: Run Diagnostic Script

```bash
cd /Users/rileycoleman/grant-analyst-v2
python3 /home/claude/debug_stuck_grant.py
```

This will show you:
- Which grants are being filtered out
- What the actual scores are
- How semantic boosting affects results
- Source distribution of matches

**Expected output**: You'll probably see 1-2 "strong" matches (≥0.65) and many "weak" matches (0.45-0.65) that are actually relevant but filtered out.

### Step 2: Apply the Fix

Open `src/api/server.py` and find the `group_results_by_grant()` function (around line 220-280).

**Option A: Simple Fix (Recommended)**

Replace the function with `improved_group_results_by_grant()` from `/home/claude/fix_diversity.py`.

Key changes:
```python
# OLD CODE
MIN_SCORE_STRONG = 0.65  # Too high!

# NEW CODE
MIN_SCORE_THRESHOLD = 0.40  # More inclusive

# Plus: Add diversity
open_grants = add_diversity_to_grants(
    open_grants, 
    max_grants=max_grants, 
    diversity_weight=0.15
)
```

**Option B: Adaptive Fix (More sophisticated)**

Use `adaptive_threshold_group_results()` which automatically lowers the threshold if too few results are found.

### Step 3: Add the Diversity Function

Add this new function to `server.py` (anywhere before `group_results_by_grant`):

```python
def add_diversity_to_grants(
    grant_scores: list[dict],
    max_grants: int = 5,
    diversity_weight: float = 0.15,
) -> list[dict]:
    """
    Select diverse grants using a diversity penalty.
    
    Prevents the same grant or very similar grants from dominating.
    """
    if not grant_scores or max_grants <= 0:
        return []
    
    selected = []
    remaining = grant_scores.copy()
    
    while len(selected) < max_grants and remaining:
        if not selected:
            # First grant: take highest score
            best = remaining.pop(0)
            selected.append(best)
            continue
        
        # Apply diversity penalty for subsequent grants
        best_idx = 0
        best_adjusted_score = -1
        
        for i, candidate in enumerate(remaining):
            base_score = candidate['boosted_score']
            
            # Penalty for same source
            penalty = 0
            for already_selected in selected:
                if candidate['source'] == already_selected['source']:
                    penalty += diversity_weight * 0.5
                
                # Penalty for similar titles
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

### Step 4: Test the Fix

Restart your API:
```bash
./start_api.sh
```

Test with the same query:
```python
# In your Streamlit UI or via API
query = "what would be a good grant for my company to apply for: https://mildtech.co.uk/"
```

**Expected improvement**:
- You should now see 3-5 different grants
- Mix of Innovate UK and NIHR grants
- Diversity across different funding types (R&D, innovation, clinical, etc.)

### Step 5: Tune Parameters (Optional)

If you're still getting too few results or too many low-quality results:

**Lower threshold more**:
```python
MIN_SCORE_THRESHOLD = 0.35  # Even more inclusive
```

**Increase diversity weight**:
```python
diversity_weight = 0.25  # Stronger diversity preference
```

**Adjust max grants shown**:
```python
max_grants = 7  # Show more options
```

## Testing Examples

### Test 1: Company URL Query
```
Query: "what would be a good grant for my company to apply for: https://mildtech.co.uk/"

BEFORE: 1 grant (Agentic AI Pioneers Prize)
AFTER:  5 grants (Agentic AI, SBRI Healthcare, KTN Innovation, etc.)
```

### Test 2: Generic AI Query
```
Query: "AI funding for startups"

BEFORE: 1-2 grants (mostly Agentic AI)
AFTER:  4-5 grants (Agentic AI, Smart Grant, Innovation Vouchers, etc.)
```

### Test 3: Healthcare Query
```
Query: "healthcare innovation grants"

BEFORE: Maybe 1-2 healthcare grants
AFTER:  5+ grants (NIHR i4i, HIC, Themed Call, etc.)
```

## How Diversity Works

The diversity algorithm:

1. **First grant**: Takes the highest-scoring grant (pure relevance)

2. **Subsequent grants**: For each candidate:
   - Start with its relevance score
   - Apply penalties for:
     * Being from the same source (Innovate UK vs NIHR)
     * Having similar title words to already-selected grants
   - Select the grant with highest adjusted score

3. **Result**: You get diverse recommendations that are still relevant but cover different funding types, sources, and opportunities

## Visual Example

```
WITHOUT DIVERSITY:
1. Agentic AI Pioneers Prize      (score: 0.72, source: innovate_uk)
2. Agentic AI Pioneers Prize Copy (score: 0.71, source: innovate_uk)
3. [filtered out, score too low]

WITH DIVERSITY (0.15 weight):
1. Agentic AI Pioneers Prize      (score: 0.72, adjusted: 0.72)
2. NIHR i4i Programme             (score: 0.58, adjusted: 0.58 - no penalty)
3. Smart Grant                     (score: 0.56, adjusted: 0.51 - small penalty for Innovate UK)
4. HIC Early-Stage Programme      (score: 0.54, adjusted: 0.54 - no penalty)
5. KTN Innovation Network          (score: 0.52, adjusted: 0.52 - no penalty)
```

## Monitoring

After deploying, check your logs for:

```
INFO: Only 1 open grants with threshold 0.50, lowering to 0.35
INFO: Built context from 5 unique grants (deduped from 20 hits)
INFO: Selected 5 diverse grants from 12 candidates
```

These log lines indicate the adaptive threshold and diversity mechanisms are working.

## Rollback Plan

If the fix causes issues, simply:

1. Keep the original `group_results_by_grant()` function
2. Just change `MIN_SCORE_STRONG = 0.40` (lower threshold only)
3. This will increase variety without the diversity algorithm

The diversity algorithm is the sophisticated approach, but lowering the threshold alone will help significantly.
