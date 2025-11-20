from typing import List, Dict, Optional
from datetime import datetime
import json

class ConversationManager:
    """Maintains conversation context and user profile across queries."""

    def __init__(self):
        self.conversations = {}  # session_id -> conversation state

    def initialize_session(self, session_id: str) -> Dict:
        """Create new conversation session."""
        self.conversations[session_id] = {
            "messages": [],
            "user_profile": {},
            "discussed_grants": [],
            "last_query_intent": None,
            "created_at": datetime.now().isoformat()
        }
        return self.conversations[session_id]

    def add_message(self, session_id: str, role: str, content: str,
                    grants: Optional[List[str]] = None):
        """Add message to conversation history."""
        if session_id not in self.conversations:
            self.initialize_session(session_id)

        message = {
            "role": role,  # 'user' or 'assistant'
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "grants_mentioned": grants or []
        }

        self.conversations[session_id]["messages"].append(message)

        # Update discussed grants
        if grants:
            self.conversations[session_id]["discussed_grants"].extend(grants)

    def extract_user_profile(self, session_id: str, new_info: Dict):
        """Extract and update user profile from conversation."""
        if session_id not in self.conversations:
            self.initialize_session(session_id)

        profile = self.conversations[session_id]["user_profile"]

        # Merge new information
        for key, value in new_info.items():
            if key not in profile:
                profile[key] = value
            elif isinstance(value, list):
                profile[key] = list(set(profile[key] + value))
            else:
                profile[key] = value

    def get_context(self, session_id: str, last_n: int = 3) -> Dict:
        """Get recent conversation context."""
        if session_id not in self.conversations:
            self.initialize_session(session_id)

        conv = self.conversations[session_id]
        recent_messages = conv["messages"][-last_n:] if conv["messages"] else []

        return {
            "recent_messages": recent_messages,
            "user_profile": conv["user_profile"],
            "discussed_grants": list(set(conv["discussed_grants"])),
            "last_intent": conv.get("last_query_intent")
        }

    def get_last_grants(self, session_id: str, n: int = 5) -> List[str]:
        """Get last N grants discussed."""
        if session_id not in self.conversations:
            return []

        messages = self.conversations[session_id]["messages"]
        grants = []

        # Work backwards through messages
        for msg in reversed(messages):
            if msg.get("grants_mentioned"):
                grants.extend(msg["grants_mentioned"])
                if len(grants) >= n:
                    break

        return grants[:n]
