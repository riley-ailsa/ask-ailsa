from typing import List, Dict, Optional
import numpy as np
from openai import OpenAI
import os
import logging
import re

from backend.conversation_manager import ConversationManager
from backend.intent_classifier import IntentClassifier
from backend.eligibility_filter import EligibilityFilter
from backend.strategic_advisor import StrategicAdvisor
from backend.profile_extractor import ProfileExtractor

logger = logging.getLogger(__name__)


class EnhancedGrantSearch:
    """Context-aware grant search with strategic advisory."""

    def __init__(self, grant_store, vector_index=None):
        """
        Initialize enhanced search.

        Args:
            grant_store: PostgresGrantStore instance for querying grant data
            vector_index: PineconeVectorIndex instance for semantic search
        """
        self.grant_store = grant_store
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.vector_index = vector_index

        # Initialize new components
        self.conv_manager = ConversationManager()
        self.intent_classifier = IntentClassifier()
        self.eligibility_filter = EligibilityFilter(grant_store)
        self.strategic_advisor = StrategicAdvisor()
        self.profile_extractor = ProfileExtractor()

    def _is_likely_followup(self, query: str, context: Dict) -> bool:
        """
        Pattern-based detection for follow-up questions.
        Fallback in case LLM classifier misses it.
        """
        # Only consider if there are recently discussed grants
        has_discussed = bool(context.get("discussed_grants"))
        if not has_discussed:
            logger.debug(f"Pattern detector: No discussed grants, not a follow-up")
            return False

        query_lower = query.lower().strip()
        logger.debug(f"Pattern detector: Checking query '{query_lower}' with {len(context.get('discussed_grants', []))} discussed grants")

        # Common follow-up patterns
        followup_patterns = [
            r"what are the dates\??",
            r"what are the deadlines\??",
            r"what's the deadline",
            r"when does (it|this) close\??",
            r"when do (they|these|those) close\??",
            r"when do these close\??",
            r"when does this close\??",
            r"how much funding",
            r"what's the budget",
            r"who can apply",
            r"what are the requirements",
            r"how do i apply",
            r"tell me more",
            r"tell me more about",
            r"what about",
            r"what are the dates for (this|these|that|those)\??",
            r"what's the funding",
            r"how much can i get",
        ]

        # Check if query matches any pattern
        for pattern in followup_patterns:
            if re.search(pattern, query_lower):
                logger.info(f"Pattern detector: MATCH on pattern '{pattern}' - overriding to followup")
                return True

        # Also check for very short queries (< 10 words) with question words + pronouns
        # after discussing grants
        word_count = len(query.split())
        question_words = ["what", "when", "how", "who", "which", "where"]
        pronoun_indicators = ["this", "that", "these", "those", "it", "they", "them"]

        if word_count <= 10:
            starts_with_question = any(query_lower.startswith(qw) for qw in question_words)
            contains_pronoun = any(pronoun in query_lower.split() for pronoun in pronoun_indicators)

            if starts_with_question and contains_pronoun:
                # Questions with pronouns like "when do these close?" are almost always follow-ups
                recent_msgs = context.get("recent_messages", [])
                if recent_msgs and recent_msgs[-1].get("role") == "assistant":
                    logger.info(f"Pattern detector: Short question with pronoun detected - treating as follow-up")
                    return True

        return False

    def _extract_grants_from_history(self, history: List[Dict]) -> List[str]:
        """
        Extract grant IDs mentioned in recent assistant messages.

        Parses the conversation history to find grants that were discussed,
        so follow-up queries can reference them without re-searching.

        This is a fallback for when ConversationManager doesn't have tracked grants
        (e.g., when using streaming endpoints that bypass tracking).
        """
        grant_ids = []

        # Look through recent assistant messages (last 3)
        assistant_messages = [
            msg for msg in history
            if msg.get('role') == 'assistant' and len(msg.get('content', '')) > 100
        ][-3:]

        for msg in assistant_messages:
            content = msg.get('content', '')
            # Extract grant IDs like "innovate_uk_2332" or "nihr_2025_340"
            id_pattern = r'\b(innovate_uk_\d+|nihr_\d+(?:_\d+)?|horizon_europe[:\w]+)\b'
            found_ids = re.findall(id_pattern, content, re.IGNORECASE)
            grant_ids.extend(found_ids)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(grant_ids))[:10]

    def _extract_grant_name_query(self, query: str) -> Optional[str]:
        """
        Detect if user is asking about a specific grant by name.
        Returns normalized grant name if found, None otherwise.
        """
        query_lower = query.lower()

        # Known grant name keywords to look for
        grant_keywords = [
            'biomedical catalyst', 'biomed catalyst', 'biomedical cat',
            'i4i', 'invention for innovation',
            'horizon europe', 'eureka',
            'digital europe', 'smart grant',
            'sbri', 'small business research',
            'nihr fellowship', 'nihr professorship',
            'erc grant', 'marie curie',
            'innovate uk', 'knowledge transfer',
        ]

        for keyword in grant_keywords:
            if keyword in query_lower:
                logger.info(f"Grant name query detected: '{keyword}'")
                return keyword

        return None

    def _filter_grants_by_name(self, grants: List[Dict], query_name: str, top_k: int = 10) -> List[Dict]:
        """
        Filter and prioritize grants matching the queried name.
        Returns ALL matching grants first, then others up to top_k.
        """
        matching_grants = []
        other_grants = []

        for grant in grants:
            title_lower = grant.get('title', '').lower()
            # Check if grant title contains the queried name
            if query_name in title_lower:
                matching_grants.append(grant)
            else:
                other_grants.append(grant)

        logger.info(f"Grant name filter: '{query_name}' -> {len(matching_grants)} matches, {len(other_grants)} others")

        # Diagnostic: Log matching grants
        if matching_grants:
            logger.info(f"=== MATCHING GRANTS FOR '{query_name}' ===")
            for i, g in enumerate(matching_grants, 1):
                logger.info(f"  {i}. [{g.get('grant_id', 'N/A')}] {g.get('title', 'N/A')[:80]}")
            logger.info(f"=== END MATCHING GRANTS ===")

        # If we found matches, prioritize them
        if matching_grants:
            # Return ALL matching grants (e.g., both Biomedical Catalyst variants)
            # Plus a few others if we have room
            result = matching_grants[:top_k]
            if len(result) < top_k:
                result.extend(other_grants[:top_k - len(result)])
            return result

        # No matches found, return all grants
        return grants[:top_k]

    def search(self, query: str, session_id: str, top_k: int = 10,
               active_only: bool = True, history: Optional[List[Dict]] = None) -> Dict:
        """
        Enhanced search with context awareness and strategic advice.

        Args:
            query: User's search query
            session_id: Conversation session ID
            top_k: Number of grants to return
            active_only: Filter to only active grants
            history: Optional conversation history for extracting grant context
                    (fallback when ConversationManager doesn't have tracked grants)

        Returns:
            {
                "response": "Strategic advice text",
                "grants": [list of matched grants],
                "intent": "query intent type",
                "user_profile": {extracted profile}
            }
        """

        # 1. Get conversation context
        context = self.conv_manager.get_context(session_id)

        # 2. Extract user profile from current message
        updated_profile = self.profile_extractor.extract_from_message(
            query,
            context["user_profile"]
        )
        self.conv_manager.extract_user_profile(session_id, updated_profile)

        # 3. Classify intent
        intent_info = self.intent_classifier.classify(query, context)
        intent = intent_info["intent"]

        logger.info(f"Query intent: {intent}, confidence: {intent_info.get('confidence', 0)}")

        # 3.5. Fallback: Pattern-based follow-up detection
        # If classifier missed it but query looks like a follow-up, override
        if intent != "followup" and self._is_likely_followup(query, context):
            logger.info(f"Pattern-based override: changing intent from '{intent}' to 'followup'")
            intent = "followup"
            intent_info["intent"] = "followup"

        # 3.6. Check for "tell me more" pattern - always a follow-up if grants were discussed
        if "tell me more" in query.lower() and context.get("discussed_grants"):
            if intent != "followup":
                logger.info(f"'Tell me more' detected with discussed grants - overriding intent from '{intent}' to 'followup'")
                intent = "followup"
                intent_info["intent"] = "followup"

        # 4. Get relevant grants based on intent
        if intent == "comparative" and intent_info.get("referenced_grants"):
            # User is comparing specific grants from conversation
            grant_ids = self._get_specific_grants(intent_info["referenced_grants"])
            grants = self._fetch_grants_by_ids(grant_ids, active_only)

        elif intent == "followup":
            # Use last discussed grants - prioritize conversation context
            last_grant_ids = self.conv_manager.get_last_grants(session_id, n=5)
            grants = self._fetch_grants_by_ids(last_grant_ids, active_only)

            logger.info(f"Follow-up query detected, using {len(grants)} grants from ConversationManager")

            # Fallback: Extract from conversation history if ConversationManager has no grants
            # This handles streaming endpoints that bypass grant tracking
            if len(grants) == 0 and history:
                logger.info("ConversationManager has no grants, extracting from conversation history")
                history_grant_ids = self._extract_grants_from_history(history)
                if history_grant_ids:
                    logger.info(f"Extracted {len(history_grant_ids)} grant IDs from history: {history_grant_ids}")
                    grants = self._fetch_grants_by_ids(history_grant_ids, active_only)
                    logger.info(f"Found {len(grants)} grants from history extraction")

            # Only add additional grants if we don't have enough context
            if len(grants) < 3 and self.vector_index:
                logger.info("Not enough context grants, adding semantic search results")
                additional = self._semantic_search(query, top_k=3, active_only=active_only)
                grants.extend(additional)

        else:
            # Do full semantic search
            grants = self._semantic_search(query, top_k=top_k * 2, active_only=active_only)  # Get more for filtering

        # Diagnostic: Log all grants after semantic search (before any filtering)
        logger.info(f"=== GRANTS AFTER SEMANTIC SEARCH (before any filtering) ===")
        logger.info(f"Total grants from semantic search: {len(grants)}")
        for i, g in enumerate(grants[:20], 1):  # Show top 20
            title = g.get('title', 'N/A')
            grant_id = g.get('grant_id', 'N/A')
            score = g.get('pinecone_score', 0)
            logger.info(f"  {i}. [{grant_id}] (score: {score:.3f}) {title[:80]}")
        logger.info(f"=== END SEMANTIC SEARCH RESULTS ===")

        logger.info(f"Grants before name filtering: {len(grants)}")

        # 4.5. Check if user is asking about a specific grant by name
        grant_name_query = self._extract_grant_name_query(query)
        if grant_name_query:
            # Log grants before name filtering for debugging
            logger.info(f"=== GRANTS BEFORE NAME FILTER (searching for '{grant_name_query}') ===")
            for i, g in enumerate(grants[:15], 1):
                title = g.get('title', 'N/A')
                grant_id = g.get('grant_id', 'N/A')
                has_match = grant_name_query in title.lower()
                logger.info(f"  {i}. [{grant_id}] {'✓' if has_match else '✗'} {title[:80]}")
            logger.info(f"=== END GRANTS BEFORE NAME FILTER ===")

            # Filter to prioritize grants matching the queried name
            grants = self._filter_grants_by_name(grants, grant_name_query, top_k=top_k)
            logger.info(f"Grants after name filtering: {len(grants)}")

        logger.info(f"Grants before eligibility filter: {len(grants)}")

        # 5. Filter by eligibility
        grant_ids = [g["grant_id"] for g in grants]
        filtered_ids = self.eligibility_filter.filter_grants(grant_ids, updated_profile)

        # Diagnostic: Log which grants were filtered out
        filtered_out = [g for g in grants if g["grant_id"] not in filtered_ids]
        if filtered_out:
            logger.info(f"=== GRANTS FILTERED OUT BY ELIGIBILITY ({len(filtered_out)} removed) ===")
            for g in filtered_out[:10]:  # Show first 10
                logger.info(f"  Removed: [{g.get('grant_id', 'N/A')}] {g.get('title', 'N/A')[:80]}")
            logger.info(f"=== END FILTERED OUT GRANTS ===")

        grants = [g for g in grants if g["grant_id"] in filtered_ids]

        logger.info(f"Grants after eligibility filter: {len(grants)}")

        # 6. Rank by fit (boost Pinecone scores rather than replace them)
        if grants and updated_profile:
            # Get eligibility fit scores
            ranked = self.eligibility_filter.rank_by_fit(
                [g["grant_id"] for g in grants],
                updated_profile
            )
            id_to_fit_score = dict(ranked)

            # Combine Pinecone semantic score with eligibility boost
            # This preserves semantic ranking while allowing profile matching to influence order
            for grant in grants:
                pinecone_score = grant.get('pinecone_score', 0.5)  # Semantic relevance (0-1)
                fit_score = id_to_fit_score.get(grant["grant_id"], 0.5)  # Eligibility fit (0-1)

                # Combined score: 70% semantic + 30% eligibility
                # This weights semantic relevance higher to preserve Pinecone ranking
                grant['combined_score'] = (pinecone_score * 0.7) + (fit_score * 0.3)

            # Sort by combined score
            grants.sort(key=lambda g: g.get('combined_score', 0), reverse=True)

            logger.info(f"Ranking: Combined semantic ({pinecone_score:.3f} × 0.7) + eligibility ({fit_score:.3f} × 0.3)")
        elif grants:
            # If no profile, just preserve Pinecone ranking
            grants.sort(key=lambda g: g.get('pinecone_score', 0), reverse=True)

        # Determine how many grants to send to LLM
        # If user asked about a specific grant, send more to include all variants
        llm_grant_count = 8 if grant_name_query else 5

        # Log grants being sent to LLM context
        logger.info(f"=== GRANTS IN LLM CONTEXT ===")
        for i, g in enumerate(grants[:llm_grant_count], 1):
            title = g.get('title', 'N/A')
            source = g.get('source', 'N/A')
            grant_id = g.get('grant_id', 'N/A')
            logger.info(f"  {i}. {title[:60]} ({source}) - {grant_id}")
        logger.info(f"=== END LLM CONTEXT (showing top {min(llm_grant_count, len(grants))} of {len(grants)}) ===")

        # 7. Generate strategic advice
        response = self.strategic_advisor.generate_advice(
            query=query,
            grants=grants[:llm_grant_count],  # 8 for specific grant queries, 5 otherwise
            user_profile=updated_profile,
            context=context,
            intent=intent  # Pass intent to help with follow-up handling
        )

        # 8. Update conversation history
        self.conv_manager.add_message(
            session_id=session_id,
            role="user",
            content=query
        )

        self.conv_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=response,
            grants=[g["grant_id"] for g in grants[:5]]
        )

        # Determine how many grant cards to return
        # For follow-up queries, don't show cards (user already saw them)
        # For specific grant queries with matches, show ONLY the matches (no extras)
        # For specific grant queries without matches, show top 4
        # For discovery queries, show up to 10
        if intent == "followup":
            max_grant_cards = 0  # Don't show cards for follow-ups
        elif grant_name_query:
            # Count how many grants actually match the query name
            matching_count = sum(1 for g in grants if grant_name_query in g.get('title', '').lower())
            if matching_count > 0:
                # Show ONLY the matching grants (e.g., just the 2 Biomedical Catalyst grants)
                max_grant_cards = matching_count
                logger.info(f"Specific grant query with {matching_count} matches - showing only matching grants")
            else:
                # No matches found, show top 4 related grants
                max_grant_cards = 4
        else:
            max_grant_cards = 10  # Show 10 for discovery queries

        return {
            "response": response,
            "grants": grants[:max_grant_cards] if max_grant_cards > 0 else [],
            "intent": intent,
            "user_profile": updated_profile
        }

    def _get_specific_grants(self, grant_names: List[str]) -> List[str]:
        """
        Get grant IDs from grant names/titles.

        Searches PostgreSQL for grants matching the given names.

        Args:
            grant_names: List of grant names or partial titles to search

        Returns:
            List of matching grant IDs
        """
        if not grant_names:
            return []

        grant_ids = []

        try:
            for name in grant_names:
                # Use PostgresGrantStore to search by title
                # The store has a get_grant method but we need to search by title
                # Let's use vector search as a fallback since it's semantic
                if self.vector_index:
                    logger.info(f"Searching for grants matching: '{name}'")
                    results = self.vector_index.search(name, top_k=5)
                    for result in results:
                        gid = result.get('grant_id')
                        # Check if title actually contains the search term
                        title = result.get('metadata', {}).get('title', '')
                        if gid and name.lower() in title.lower():
                            if gid not in grant_ids:
                                grant_ids.append(gid)
                                logger.info(f"  Found: {gid} - {title[:60]}")

            logger.info(f"Found {len(grant_ids)} grants by name")
            return grant_ids[:10]  # Limit to 10 results

        except Exception as e:
            logger.error(f"Error in _get_specific_grants: {e}")
            return []

    def _fetch_grants_by_ids(self, grant_ids: List[str], active_only: bool = True) -> List[Dict]:
        """Fetch full grant details by IDs."""
        if not grant_ids:
            return []

        # Fetch from Postgres
        grants_objs = self.grant_store.get_grants_by_ids(grant_ids)

        logger.info(f"Fetching {len(grant_ids)} grant_ids from Postgres, got {len(grants_objs)} results")

        grants = []
        filtered_out = []
        for grant in grants_objs:
            # Filter by active status if requested
            if active_only and not grant.is_active:
                filtered_out.append(f"{grant.id} (inactive)")
                continue

            grants.append({
                "grant_id": grant.id,
                "title": grant.title,
                "source": grant.source,
                "total_fund_gbp": grant.total_fund_gbp,
                "closes_at": grant.closes_at,
                "description": grant.description,
                "url": grant.url
            })

        if filtered_out:
            logger.info(f"  Filtered out {len(filtered_out)} inactive grants: {filtered_out[:5]}")
        logger.info(f"  Returning {len(grants)} active grants")

        return grants

    def _semantic_search(self, query: str, top_k: int, active_only: bool = True) -> List[Dict]:
        """Perform semantic search using vector index."""
        if not self.vector_index:
            # Fallback to basic keyword search
            return self._keyword_search(query, top_k, active_only)

        try:
            # Use PineconeVectorIndex.search() method
            results = self.vector_index.search(query, top_k=top_k * 2)  # Get extra for filtering

            # Extract grant IDs from Pinecone results
            # Results format: [{"grant_id": "...", "score": 0.x, "metadata": {...}}, ...]
            grant_ids_raw = [r['grant_id'] for r in results if 'grant_id' in r]
            grant_ids_unique = list(set(grant_ids_raw))[:top_k]

            logger.info(f"Semantic search: {len(grant_ids_raw)} grant_ids from Pinecone, {len(grant_ids_unique)} unique, fetching {len(grant_ids_unique[:top_k])}")
            if len(grant_ids_raw) != len(grant_ids_unique):
                logger.info(f"  Deduplication removed {len(grant_ids_raw) - len(grant_ids_unique)} duplicate grant_ids")

            # Build score map to preserve Pinecone ranking
            score_map = {}
            for result in results:
                gid = result.get('grant_id')
                score = result.get('score', 0)
                # Keep best score for each grant (in case of duplicates from chunks)
                if gid not in score_map or score > score_map[gid]:
                    score_map[gid] = score

            # Fetch grants from Postgres
            grants = self._fetch_grants_by_ids(grant_ids_unique, active_only)

            # Attach Pinecone scores to grants for later use
            for grant in grants:
                grant['pinecone_score'] = score_map.get(grant['grant_id'], 0)

            # Sort by Pinecone score to preserve semantic ranking
            grants.sort(key=lambda g: g.get('pinecone_score', 0), reverse=True)

            return grants

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return self._keyword_search(query, top_k, active_only)

    def _keyword_search(self, query: str, top_k: int, active_only: bool = True) -> List[Dict]:
        """Fallback keyword search."""
        # Use Postgres list_grants as a fallback
        # Note: This doesn't actually do keyword search, just returns recent grants
        # A proper implementation would need full-text search in Postgres
        logger.warning("Keyword search fallback - returning recent grants instead")

        grants_objs = self.grant_store.list_grants(
            active_only=active_only,
            limit=top_k
        )

        grants = []
        for grant in grants_objs:
            grants.append({
                "grant_id": grant.id,
                "title": grant.title,
                "source": grant.source,
                "total_fund_gbp": grant.total_fund_gbp,
                "closes_at": grant.closes_at,
                "description": grant.description,
                "url": grant.url
            })

        return grants
