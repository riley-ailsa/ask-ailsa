from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class EligibilityFilter:
    """Pre-filters grants based on user profile and eligibility criteria."""

    def __init__(self, grant_store):
        """
        Initialize eligibility filter.

        Args:
            grant_store: PostgresGrantStore instance for querying grant data
        """
        self.grant_store = grant_store

    def filter_grants(self, grant_ids: List[str], user_profile: Dict) -> List[str]:
        """
        Filter grants by eligibility based on user profile.

        user_profile should contain:
        - organization_type: "SME", "university", "large_company", etc.
        - sector: ["biomedical", "digital_health", etc.]
        - funding_range: {"min": 50000, "max": 1000000}
        - has_partnerships: True/False
        - project_stage: "early", "development", "commercialization"
        """

        if not user_profile or not grant_ids:
            logger.info(f"No filtering needed: profile={bool(user_profile)}, grants={len(grant_ids) if grant_ids else 0}")
            return grant_ids

        logger.info(f"=== ELIGIBILITY FILTERING ===")
        logger.info(f"Input: {len(grant_ids)} grants")
        logger.info(f"User profile: org={user_profile.get('organization_type')}, sectors={user_profile.get('sector')}, funding_range={user_profile.get('funding_range')}")

        filtered_ids = []

        # Fetch grants from Postgres
        grants = self.grant_store.get_grants_by_ids(grant_ids)

        for grant in grants:
            grant_data = {
                'grant_id': grant.id,
                'budget_max': grant.total_fund_gbp,
                'description': grant.description,
                'organization_types': getattr(grant, 'organization_types', []),
                'eligible_countries': getattr(grant, 'eligible_countries', [])
            }

            if self._check_eligibility(grant_data, user_profile):
                filtered_ids.append(grant.id)
            else:
                logger.debug(f"Grant {grant.id} filtered out by eligibility check")

        logger.info(f"Output: {len(filtered_ids)} grants passed eligibility filter")
        logger.info(f"=== END ELIGIBILITY FILTERING ===")

        return filtered_ids

    def _check_eligibility(self, grant: Dict, profile: Dict) -> bool:
        """Check if grant matches user profile."""
        grant_id = grant.get('grant_id')
        funding_amount = grant.get('budget_max')
        description = grant.get('description', '')
        org_types = grant.get('organization_types', [])

        # Convert to lowercase for matching
        description_lower = (description or "").lower()
        org_types_lower = [str(ot).lower() for ot in (org_types or [])]
        full_text = f"{description_lower} {' '.join(org_types_lower)}"

        # 1. Check organization type
        org_type = profile.get("organization_type", "").lower()
        if org_type:
            if org_type == "sme":
                # SME-specific checks
                if "large companies only" in full_text or "corporate only" in full_text:
                    return False
            elif org_type == "university":
                if "industry only" in full_text or "commercial only" in full_text:
                    return False

        # 2. Check funding range
        funding_range = profile.get("funding_range", {})
        if funding_range and funding_amount:
            try:
                amount = float(funding_amount)
                min_funding = funding_range.get("min", 0)
                max_funding = funding_range.get("max", float('inf'))

                # Grant amount should be within reasonable range
                # If user can handle max £1M, don't show £25M grants
                if amount > max_funding * 2:  # Allow 2x flexibility
                    return False

            except (ValueError, TypeError):
                pass

        # 3. Check sector match
        # NOTE: This filter is DISABLED - too aggressive, filtering out valid grants
        # Sector matching should be used for RANKING, not filtering
        # sectors = profile.get("sector", [])
        # if sectors:
        #     sector_matched = False
        #     for sector in sectors:
        #         if sector.lower() in full_text:
        #             sector_matched = True
        #             break
        #
        #     # If we specified sectors but none match, it's probably not relevant
        #     # UNLESS this is a general/multi-sector grant
        #     if not sector_matched:
        #         multi_sector_keywords = [
        #             "any sector", "all sectors", "cross-sector",
        #             "multi-disciplinary", "any field"
        #         ]
        #         if not any(kw in full_text for kw in multi_sector_keywords):
        #             return False

        # 4. Check project stage requirements
        stage = profile.get("project_stage", "").lower()
        if stage:
            if stage == "early":
                # Early stage can't do "commercialization" grants
                if "commercial readiness" in full_text or "market launch" in full_text:
                    if "early stage" not in full_text and "proof of concept" not in full_text:
                        return False

        return True

    def rank_by_fit(self, grant_ids: List[str], user_profile: Dict) -> List[tuple]:
        """
        Rank grants by how well they fit user profile.
        Returns: [(grant_id, fit_score), ...]
        """

        if not user_profile or not grant_ids:
            return [(gid, 1.0) for gid in grant_ids]

        scored_grants = []

        # Fetch grants from Postgres
        grants = self.grant_store.get_grants_by_ids(grant_ids)

        for grant in grants:
            grant_data = {
                'grant_id': grant.id,
                'budget_max': grant.total_fund_gbp,
                'description': grant.description,
                'organization_types': getattr(grant, 'organization_types', []),
                'eligible_countries': getattr(grant, 'eligible_countries', [])
            }
            score = self._calculate_fit_score(grant_data, user_profile)
            scored_grants.append((grant.id, score))

        # Sort by score descending
        scored_grants.sort(key=lambda x: x[1], reverse=True)
        return scored_grants

    def _calculate_fit_score(self, grant: Dict, profile: Dict) -> float:
        """Calculate 0-1 fit score for grant given user profile."""
        grant_id = grant.get('grant_id')
        funding_amount = grant.get('budget_max')
        description = grant.get('description', '')
        org_types = grant.get('organization_types', [])

        score = 0.5  # Base score
        org_types_lower = [str(ot).lower() for ot in (org_types or [])]
        full_text = f"{description or ''} {' '.join(org_types_lower)}".lower()

        # Sector match: +0.3
        sectors = profile.get("sector", [])
        if sectors and any(s.lower() in full_text for s in sectors):
            score += 0.3

        # Organization type match: +0.2
        org_type = profile.get("organization_type", "").lower()
        if org_type and org_type in full_text:
            score += 0.2

        # Funding range match: +0.2
        funding_range = profile.get("funding_range", {})
        if funding_range and funding_amount:
            try:
                amount = float(funding_amount)
                min_f = funding_range.get("min", 0)
                max_f = funding_range.get("max", float('inf'))

                if min_f <= amount <= max_f:
                    score += 0.2
                elif amount < max_f * 2:  # Within 2x range
                    score += 0.1
            except (ValueError, TypeError):
                pass

        # Partnership requirements match
        if profile.get("has_partnerships") and "partnership" in full_text:
            score += 0.1

        return min(score, 1.0)
