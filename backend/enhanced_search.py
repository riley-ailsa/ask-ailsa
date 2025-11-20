from typing import List, Dict, Optional
import numpy as np
from openai import OpenAI
import os
import sqlite3
import logging

from backend.conversation_manager import ConversationManager
from backend.intent_classifier import IntentClassifier
from backend.eligibility_filter import EligibilityFilter
from backend.strategic_advisor import StrategicAdvisor
from backend.profile_extractor import ProfileExtractor

logger = logging.getLogger(__name__)


class EnhancedGrantSearch:
    """Context-aware grant search with strategic advisory."""

    def __init__(self, db_path: str, vector_index=None):
        self.db_path = db_path
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.vector_index = vector_index

        # Initialize new components
        self.conv_manager = ConversationManager()
        self.intent_classifier = IntentClassifier()
        self.eligibility_filter = EligibilityFilter(db_path)
        self.strategic_advisor = StrategicAdvisor()
        self.profile_extractor = ProfileExtractor()

    def search(self, query: str, session_id: str, top_k: int = 10,
               active_only: bool = True) -> Dict:
        """
        Enhanced search with context awareness and strategic advice.

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

        # 4. Get relevant grants based on intent
        if intent == "comparative" and intent_info.get("referenced_grants"):
            # User is comparing specific grants from conversation
            grant_ids = self._get_specific_grants(intent_info["referenced_grants"])
            grants = self._fetch_grants_by_ids(grant_ids, active_only)

        elif intent == "followup":
            # Use last discussed grants + do light search
            last_grant_ids = self.conv_manager.get_last_grants(session_id, n=3)
            grants = self._fetch_grants_by_ids(last_grant_ids, active_only)

            # Optionally add a few more via search
            if self.vector_index:
                additional = self._semantic_search(query, top_k=5, active_only=active_only)
                grants.extend(additional)

        else:
            # Do full semantic search
            grants = self._semantic_search(query, top_k=top_k, active_only=active_only)

        # 5. Filter by eligibility
        grant_ids = [g["grant_id"] for g in grants]
        filtered_ids = self.eligibility_filter.filter_grants(grant_ids, updated_profile)
        grants = [g for g in grants if g["grant_id"] in filtered_ids]

        # 6. Rank by fit
        if grants:
            ranked = self.eligibility_filter.rank_by_fit(
                [g["grant_id"] for g in grants],
                updated_profile
            )

            # Reorder grants by ranking
            id_to_score = dict(ranked)
            grants.sort(key=lambda g: id_to_score.get(g["grant_id"], 0), reverse=True)

        # 7. Generate strategic advice
        response = self.strategic_advisor.generate_advice(
            query=query,
            grants=grants[:5],  # Top 5
            user_profile=updated_profile,
            context=context
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

        return {
            "response": response,
            "grants": grants[:10],  # Return top 10
            "intent": intent,
            "user_profile": updated_profile
        }

    def _get_specific_grants(self, grant_names: List[str]) -> List[str]:
        """Get grant IDs from grant names/titles."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        grant_ids = []
        for name in grant_names:
            cursor.execute("""
                SELECT id FROM grants
                WHERE title LIKE ? OR id LIKE ?
                LIMIT 1
            """, (f"%{name}%", f"%{name}%"))

            result = cursor.fetchone()
            if result:
                grant_ids.append(result[0])

        conn.close()
        return grant_ids

    def _fetch_grants_by_ids(self, grant_ids: List[str], active_only: bool = True) -> List[Dict]:
        """Fetch full grant details by IDs."""
        if not grant_ids:
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        grants = []
        for gid in grant_ids:
            if active_only:
                cursor.execute("""
                    SELECT id, title, source, total_fund_gbp, closes_at,
                           description, url
                    FROM grants WHERE id = ? AND is_active = 1
                """, (gid,))
            else:
                cursor.execute("""
                    SELECT id, title, source, total_fund_gbp, closes_at,
                           description, url
                    FROM grants WHERE id = ?
                """, (gid,))

            result = cursor.fetchone()
            if result:
                grants.append({
                    "grant_id": result[0],
                    "title": result[1],
                    "source": result[2],
                    "total_fund_gbp": result[3],
                    "closes_at": result[4],
                    "description": result[5],
                    "url": result[6]
                })

        conn.close()
        return grants

    def _semantic_search(self, query: str, top_k: int, active_only: bool = True) -> List[Dict]:
        """Perform semantic search using vector index."""
        if not self.vector_index:
            # Fallback to basic keyword search
            return self._keyword_search(query, top_k, active_only)

        try:
            # Use existing vector index search
            hits = self.vector_index.query(query, top_k=top_k * 2)  # Get extra for filtering

            # Convert hits to grant format
            grant_ids = list(set([hit.grant_id for hit in hits if hit.grant_id]))[:top_k]

            return self._fetch_grants_by_ids(grant_ids, active_only)

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return self._keyword_search(query, top_k, active_only)

    def _keyword_search(self, query: str, top_k: int, active_only: bool = True) -> List[Dict]:
        """Fallback keyword search."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Simple keyword search
        search_query = f"%{query}%"

        if active_only:
            cursor.execute("""
                SELECT id, title, source, total_fund_gbp, closes_at,
                       description, url
                FROM grants
                WHERE (title LIKE ? OR description LIKE ?)
                  AND is_active = 1
                ORDER BY closes_at DESC
                LIMIT ?
            """, (search_query, search_query, top_k))
        else:
            cursor.execute("""
                SELECT id, title, source, total_fund_gbp, closes_at,
                       description, url
                FROM grants
                WHERE (title LIKE ? OR description LIKE ?)
                ORDER BY closes_at DESC
                LIMIT ?
            """, (search_query, search_query, top_k))

        grants = []
        for row in cursor.fetchall():
            grants.append({
                "grant_id": row[0],
                "title": row[1],
                "source": row[2],
                "total_fund_gbp": row[3],
                "closes_at": row[4],
                "description": row[5],
                "url": row[6]
            })

        conn.close()
        return grants
