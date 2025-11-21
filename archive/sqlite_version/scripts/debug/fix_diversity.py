"""
Fix for stuck grant issue - adds diversity to recommendations.

Add this to your server.py file.
"""

def add_diversity_to_grants(
    grant_scores: list[dict],
    max_grants: int = 5,
    diversity_weight: float = 0.15,
) -> list[dict]:
    """
    Select diverse grants using a diversity penalty.
    
    This prevents the same grant (or very similar grants from the same source/type)
    from dominating recommendations.
    
    Args:
        grant_scores: List of grant dicts with 'boosted_score', 'source', 'title'
        max_grants: Maximum number of grants to return
        diversity_weight: How much to penalize similarity (0.0-1.0)
    
    Returns:
        Diversified list of grants
    """
    if not grant_scores or max_grants <= 0:
        return []
    
    selected = []
    remaining = grant_scores.copy()
    
    while len(selected) < max_grants and remaining:
        if not selected:
            # First grant: just take the highest score
            best = remaining.pop(0)
            selected.append(best)
            continue
        
        # For subsequent grants, apply diversity penalty
        best_idx = 0
        best_adjusted_score = -1
        
        for i, candidate in enumerate(remaining):
            base_score = candidate['boosted_score']
            
            # Calculate diversity penalty
            penalty = 0
            for already_selected in selected:
                # Same source penalty
                if candidate['source'] == already_selected['source']:
                    penalty += diversity_weight * 0.5
                
                # Same category/type penalty (if titles are very similar)
                title_words_cand = set(candidate['title'].lower().split())
                title_words_sel = set(already_selected['title'].lower().split())
                overlap = len(title_words_cand & title_words_sel) / max(len(title_words_cand), 1)
                
                if overlap > 0.5:  # More than 50% word overlap
                    penalty += diversity_weight * 0.3
            
            adjusted_score = base_score - penalty
            
            if adjusted_score > best_adjusted_score:
                best_adjusted_score = adjusted_score
                best_idx = i
        
        selected.append(remaining.pop(best_idx))
    
    return selected


def improved_group_results_by_grant(hits: list, query: str, max_grants: int = 5) -> list:
    """
    Improved version that adds diversity to prevent stuck-grant issue.
    
    REPLACE the existing group_results_by_grant() function with this one.
    """
    from collections import defaultdict
    from src.storage.grant_store import GrantStore
    import logging
    
    logger = logging.getLogger(__name__)
    grant_store = GrantStore(db_path="grants.db")
    
    by_grant = defaultdict(list)
    
    for h in hits:
        if not h.grant_id:
            continue
        by_grant[h.grant_id].append(h)
    
    items = []
    for gid, group in by_grant.items():
        best = max(group, key=lambda x: x.score)
        
        # Get grant details
        grant = grant_store.get_grant(gid)
        if not grant:
            continue
        
        # Filter out Smart Grants (paused January 2025)
        title_lower = grant.title.lower()
        if "smart grant" in title_lower or "smart grants" in title_lower:
            logger.info(f"Filtered out Smart Grant: {grant.title}")
            continue
        
        # Apply semantic boosting
        from src.api.server import apply_semantic_boost
        boosted_score = apply_semantic_boost(query, grant.title, float(best.score))
        
        items.append({
            "grant_id": gid,
            "title": grant.title,
            "source": grant.source,
            "status": "open" if grant.is_active else "closed",
            "closes_at": grant.closes_at.isoformat() if grant.closes_at else None,
            "total_fund_gbp": getattr(grant, "total_fund_gbp", None) or grant.total_fund,
            "best_score": boosted_score,
            "url": grant.url,
        })
    
    # Separate open and closed grants
    from datetime import datetime, timezone
    
    open_grants = []
    closed_grants = []
    
    # LOWERED THRESHOLD: 0.40 instead of 0.65
    # This is the key fix - many relevant grants were being filtered out
    MIN_SCORE_THRESHOLD = 0.40  # Was too high at ~0.65
    
    for item in items:
        if item["best_score"] < MIN_SCORE_THRESHOLD:
            continue
        
        # Check if grant is truly open based on deadline
        is_open = item["status"] == "open"
        if item["closes_at"]:
            try:
                deadline_dt = datetime.fromisoformat(item["closes_at"].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                is_open = deadline_dt > now
            except:
                pass
        
        if is_open:
            open_grants.append(item)
        else:
            closed_grants.append(item)
    
    # Sort by score
    open_grants.sort(key=lambda x: x["best_score"], reverse=True)
    closed_grants.sort(key=lambda x: x["best_score"], reverse=True)
    
    # **KEY FIX**: Add diversity to prevent same grant dominating
    open_grants = add_diversity_to_grants(open_grants, max_grants=max_grants, diversity_weight=0.15)
    
    # Prioritize open grants, fill remaining slots with closed
    result = open_grants[:max_grants]
    
    if len(result) < max_grants:
        closed_to_add = max_grants - len(result)
        result.extend(closed_grants[:closed_to_add])
    
    return result


# Alternative: Dynamic threshold adjustment
def adaptive_threshold_group_results(hits: list, query: str, max_grants: int = 5) -> list:
    """
    Alternative approach: dynamically lower threshold if too few results.
    
    Use this if you want to keep the original logic but automatically adjust
    when there aren't enough strong matches.
    """
    from collections import defaultdict
    from src.storage.grant_store import GrantStore
    import logging
    
    logger = logging.getLogger(__name__)
    grant_store = GrantStore(db_path="grants.db")
    
    by_grant = defaultdict(list)
    
    for h in hits:
        if not h.grant_id:
            continue
        by_grant[h.grant_id].append(h)
    
    items = []
    for gid, group in by_grant.items():
        best = max(group, key=lambda x: x.score)
        
        grant = grant_store.get_grant(gid)
        if not grant:
            continue
        
        # Filter Smart Grants
        title_lower = grant.title.lower()
        if "smart grant" in title_lower or "smart grants" in title_lower:
            continue
        
        from src.api.server import apply_semantic_boost
        boosted_score = apply_semantic_boost(query, grant.title, float(best.score))
        
        items.append({
            "grant_id": gid,
            "title": grant.title,
            "source": grant.source,
            "status": "open" if grant.is_active else "closed",
            "closes_at": grant.closes_at.isoformat() if grant.closes_at else None,
            "total_fund_gbp": getattr(grant, "total_fund_gbp", None) or grant.total_fund,
            "best_score": boosted_score,
            "url": grant.url,
        })
    
    # Separate open/closed
    from datetime import datetime, timezone
    
    open_grants = []
    closed_grants = []
    
    # Start with conservative threshold
    MIN_SCORE_THRESHOLD = 0.50
    
    # Filter with initial threshold
    for item in items:
        if item["best_score"] < MIN_SCORE_THRESHOLD:
            continue
        
        is_open = item["status"] == "open"
        if item["closes_at"]:
            try:
                deadline_dt = datetime.fromisoformat(item["closes_at"].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                is_open = deadline_dt > now
            except:
                pass
        
        if is_open:
            open_grants.append(item)
        else:
            closed_grants.append(item)
    
    # **ADAPTIVE THRESHOLD**: If too few results, lower threshold
    if len(open_grants) < 2:
        logger.info(f"Only {len(open_grants)} open grants with threshold {MIN_SCORE_THRESHOLD}, lowering to 0.35")
        MIN_SCORE_THRESHOLD = 0.35
        
        # Re-filter with lower threshold
        open_grants = []
        closed_grants = []
        
        for item in items:
            if item["best_score"] < MIN_SCORE_THRESHOLD:
                continue
            
            is_open = item["status"] == "open"
            if item["closes_at"]:
                try:
                    deadline_dt = datetime.fromisoformat(item["closes_at"].replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    is_open = deadline_dt > now
                except:
                    pass
            
            if is_open:
                open_grants.append(item)
            else:
                closed_grants.append(item)
    
    # Sort and apply diversity
    open_grants.sort(key=lambda x: x["best_score"], reverse=True)
    closed_grants.sort(key=lambda x: x["best_score"], reverse=True)
    
    # Add diversity
    open_grants = add_diversity_to_grants(open_grants, max_grants=max_grants)
    
    result = open_grants[:max_grants]
    
    if len(result) < max_grants:
        closed_to_add = max_grants - len(result)
        result.extend(closed_grants[:closed_to_add])
    
    return result
