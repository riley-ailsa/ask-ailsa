from typing import Dict, List
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm.client import LLMClient

class StrategicAdvisor:
    """Provides strategic funding advice based on user profile and grants."""

    def __init__(self):
        # Use the project's LLMClient which properly handles GPT-5.1
        self.llm_client = LLMClient(model="gpt-5.1-chat-latest")

    def generate_advice(self, query: str, grants: List[Dict],
                       user_profile: Dict, context: Dict) -> str:
        """
        Generate strategic advisory response.

        Args:
            query: User's question
            grants: List of matched grants with details
            user_profile: Extracted user profile
            context: Conversation context

        Returns:
            Strategic advice as string
        """

        # Build prompt with all context
        prompt = self._build_strategic_prompt(
            query, grants, user_profile, context
        )

        # Use LLMClient which handles GPT-5.1 parameters correctly
        response = self.llm_client.chat(
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            model_override="gpt-5.1-chat-latest"  # Force GPT-5.1
        )

        return response

    def _get_system_prompt(self) -> str:
        return """You are Ailsa, an expert UK research funding strategist with deep knowledge of NIHR and Innovate UK funding.

YOUR ROLE:
- Provide strategic, personalized funding advice
- Analyze user's actual situation vs. grant requirements
- Identify gaps and suggest solutions
- Be direct and honest about fit
- Ask strategic follow-up questions

CONVERSATION STYLE:
- Natural, conversational, supportive
- No bullet points unless comparing specific criteria
- Acknowledge previous context
- Use strategic reasoning, not just facts
- Help users think through their approach

CRITICAL RULES:
1. Always reference conversation context - never ignore what was just discussed
2. If asked to compare grants, COMPARE THOSE SPECIFIC GRANTS
3. Focus on user's actual situation (team size, funding capacity, stage)
4. Highlight both opportunities AND gaps/challenges
5. End with a strategic question to guide next steps

NEVER:
- Recommend irrelevant sectors (don't suggest aerospace for biomedical)
- Ignore previous conversation context
- Just list grants without strategic analysis
- Provide vague general advice
"""

    def _build_strategic_prompt(self, query: str, grants: List[Dict],
                                user_profile: Dict, context: Dict) -> str:
        """Build detailed prompt with all context."""

        # Format user profile
        profile_text = self._format_profile(user_profile)

        # Format grants
        grants_text = self._format_grants(grants)

        # Format conversation history
        history_text = self._format_conversation(context.get("recent_messages", []))

        # Format discussed grants
        discussed = context.get("discussed_grants", [])
        discussed_text = f"Recently discussed: {', '.join(discussed)}" if discussed else ""

        prompt = f"""USER PROFILE:
{profile_text}

CONVERSATION HISTORY:
{history_text}
{discussed_text}

MATCHED GRANTS:
{grants_text}

CURRENT QUERY: "{query}"

Provide strategic advice that:
1. References the conversation context appropriately
2. Analyzes the user's situation vs. grant requirements
3. Identifies specific strengths and gaps
4. Suggests concrete next steps
5. Asks a strategic follow-up question

Be natural and conversational. Don't use bullet points unless comparing specific criteria."""

        return prompt

    def _format_profile(self, profile: Dict) -> str:
        """Format user profile for prompt."""
        if not profile:
            return "No profile information yet"

        parts = []

        if profile.get("organization_type"):
            parts.append(f"Organization: {profile['organization_type']}")

        if profile.get("sector"):
            parts.append(f"Sectors: {', '.join(profile['sector'])}")

        if profile.get("has_partnerships"):
            parts.append("Has university partnerships")

        if profile.get("has_patented_tech"):
            parts.append("Has patented technology")

        if profile.get("team_size"):
            parts.append(f"Team size: {profile['team_size']}")

        if profile.get("funding_range"):
            fr = profile['funding_range']
            parts.append(f"Funding capacity: £{fr.get('min', 0):,} - £{fr.get('max', 0):,}")

        return "\n".join(parts) if parts else "No profile information yet"

    def _format_grants(self, grants: List[Dict]) -> str:
        """Format grants for prompt."""
        if not grants:
            return "No grants provided"

        formatted = []
        for i, grant in enumerate(grants[:5], 1):  # Top 5
            # Handle different grant data structures
            title = grant.get('title') or grant.get('grant_id', 'Unknown')
            source = grant.get('source', 'Unknown')
            funding = grant.get('total_fund_gbp') or grant.get('funding_amount', 'TBC')
            deadline = grant.get('closes_at') or grant.get('deadline', 'TBC')
            eligibility = grant.get('eligibility') or grant.get('eligibility_text', 'See grant details')

            # Format funding
            if isinstance(funding, (int, float)):
                funding_str = f"£{funding:,.0f}"
            else:
                funding_str = str(funding)

            formatted.append(f"""
{i}. {title}
   Source: {source}
   Funding: {funding_str}
   Deadline: {deadline}
   Eligibility: {eligibility[:200]}...
""")

        return "\n".join(formatted)

    def _format_conversation(self, messages: List[Dict]) -> str:
        """Format recent conversation."""
        if not messages:
            return "No previous conversation"

        formatted = []
        for msg in messages[-3:]:
            role = msg["role"].upper()
            content = msg["content"][:300]
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)
