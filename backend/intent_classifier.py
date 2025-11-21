from typing import Dict, List
from openai import OpenAI
import os
import json

class IntentClassifier:
    """Classifies user query intent to determine response strategy."""

    INTENT_TYPES = {
        "comparative": "Comparing specific grants already discussed",
        "followup": "Following up on previous topic",
        "discovery": "Finding new grants",
        "eligibility": "Checking eligibility for grants",
        "strategic": "Asking for strategic advice",
        "clarification": "Asking for details about a grant"
    }

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def classify(self, query: str, context: Dict) -> Dict:
        """
        Classify query intent given conversation context.

        Returns:
            {
                "intent": "comparative",
                "confidence": 0.95,
                "reasoning": "User asking 'which one' referring to previous grants",
                "requires_context": True
            }
        """

        # Build context summary
        recent_grants = context.get("discussed_grants", [])
        last_messages = context.get("recent_messages", [])

        context_summary = f"""
Recent conversation:
{self._format_messages(last_messages)}

Recently discussed grants: {', '.join(recent_grants[:5]) if recent_grants else 'None'}
"""

        prompt = f"""Classify the user's query intent. Choose ONE of these intents:

{self._format_intents()}

IMPORTANT - FOLLOW-UP DETECTION:
If the query is a short question about dates, deadlines, funding amounts, requirements, or application process WITHOUT naming a specific grant, classify as "followup" if there are recently discussed grants.

Examples of FOLLOW-UP queries:
- "what are the dates?" (after discussing Biomedical Catalyst)
- "how much funding?" (after discussing i4i Programme)
- "what's the deadline?" (after discussing Horizon Europe)
- "who can apply?" (after discussing any grant)
- "tell me more" (after any discussion)
- "how do I apply?" (after discussing grants)

These should be "followup" NOT "discovery" - the user wants info about what was JUST discussed.

Context:
{context_summary}

User Query: "{query}"

Respond in JSON:
{{
    "intent": "the intent type",
    "confidence": 0.0-1.0,
    "reasoning": "why you chose this intent",
    "requires_context": true/false,
    "referenced_grants": ["grant names if referring to specific ones"]
}}"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap for classification
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        return json.loads(response.choices[0].message.content)

    def _format_intents(self) -> str:
        return "\n".join([f"- {k}: {v}" for k, v in self.INTENT_TYPES.items()])

    def _format_messages(self, messages: List[Dict]) -> str:
        if not messages:
            return "No previous messages"

        formatted = []
        for msg in messages[-3:]:  # Last 3 messages
            role = msg["role"].upper()
            content = msg["content"][:200]  # Truncate
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)
