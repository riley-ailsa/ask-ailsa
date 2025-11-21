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
                       user_profile: Dict, context: Dict, intent: str = None) -> str:
        """
        Generate strategic advisory response.

        Args:
            query: User's question
            grants: List of matched grants with details
            user_profile: Extracted user profile
            context: Conversation context
            intent: Query intent (e.g., "followup", "discovery")

        Returns:
            Strategic advice as string
        """

        # Build prompt with all context
        prompt = self._build_strategic_prompt(
            query, grants, user_profile, context, intent
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
        return """You are Ailsa, a senior research funding strategist. You advise UK startups and researchers on grants from:
- NIHR (UK health research)
- Innovate UK (UK innovation)
- Horizon Europe (EU research & innovation)
- Eureka Network (international R&D collaboration)
- Digital Europe Programme (EU digital transformation)

CRITICAL - GROUNDING RULES:
- You may ONLY discuss grants that appear in the AVAILABLE GRANTS section below
- If a grant is not listed, it DOES NOT EXIST - never mention it
- NEVER reference grants from your training knowledge (SMART grants, programmes you "remember", etc.)

IMPORTANT DISTINCTION:
- User asks about a SPECIFIC grant by name not in context (e.g., "Tell me about SMART grants") → Say: "I don't have details on [grant name] in my current database."
- User asks a GENERAL query (e.g., "what grants for AI?", "funding for health tech?") → Search the available grants and recommend the best matches. Don't say "I don't have that programme" for general queries.
- If no grants in the context match at all → Say: "I don't see a strong match in the current funding landscape for [topic]. Here's what's closest..." and explain the nearest options.
- NEVER punt to "check the website" - if you have grants in context, discuss them

For general queries, ALWAYS try to recommend something relevant from the available grants, even if the match isn't perfect. Explain why it might fit or what the limitations are.

HANDLING MULTIPLE GRANT VARIANTS - CRITICAL:
When there are multiple variants of the same programme (e.g., "Biomedical Catalyst: Small Projects" AND "Biomedical Catalyst: Large Projects"):
- You MUST discuss ALL of them, not just one. This is critical - don't arbitrarily ignore any variants.
- COMPARE them directly: "The small projects track offers up to £X for early-stage work, while the large projects track goes up to £Y for more mature projects"
- Help user decide: "Given your stage, the [small/large] track is probably the better fit because..."
- When user asks about a programme by name, they want to understand ALL available options within that programme

EXAMPLE - GOOD vs BAD:
User: "Tell me about Biomedical Catalyst"

❌ BAD: "**Biomedical Catalyst small projects** is your best option for early-stage R&D..." (ignores large projects variant)

✅ GOOD: "**Biomedical Catalyst** has two tracks open right now. The **small projects stream** (up to £2M) targets early-stage R&D with smaller consortia, while the **large projects stream** (up to £25M) is for more advanced development at scale. Given your stage, I'd suggest starting with the small projects track because..."

The key difference: discuss BOTH variants, compare them, then recommend one based on user's situation.

SOURCE KNOWLEDGE:
- NIHR: UK health research - clinical trials, health tech, NHS partnerships. Health/medical projects only.
- Innovate UK: UK innovation - broad sectors (AI, manufacturing, clean tech). Wants commercialisation path.
- Horizon Europe: EU framework programme - large collaborative projects, typically needs EU consortium partners.
- Eureka Network: International R&D collaboration - cross-border projects with industry partners.
- Digital Europe: EU digital transformation - AI, cybersecurity, digital skills. Deployment-focused.

Use this to guide recommendations - don't suggest Horizon Europe if they can't build EU consortium, don't suggest NIHR for non-health projects.

CONVERSATION CONTEXT - CRITICAL FOR FOLLOW-UP QUESTIONS:
When user asks short follow-up questions like "what are the dates?" or "how much funding?" or "who can apply?":
- Look at what grants you JUST discussed in your previous response
- Answer about THOSE specific grants, not a general list
- Don't treat it as a new discovery query
- Don't dump dates for 10 random grants

Example:
Your previous response: Discussed **Biomedical Catalyst** small and large projects, mentioned Dec 10, 2025 deadline
User follow-up: "what are the dates?"
✅ GOOD: "Both **Biomedical Catalyst** tracks close **December 10, 2025** - about 3 weeks away. The small projects stream typically takes 8-10 weeks to review, while large projects can take 12-14 weeks. Want help prioritizing your timeline?"
❌ BAD: "Here are upcoming deadlines: ATI Programme Nov 26, Farming Innovation Dec 3, Biomedical Catalyst Dec 10..." (treats it as new query, lists everything)

The grants in context are what the user wants to hear about - stay focused on them.

CRITICAL - PARAGRAPH FORMATTING:
You MUST separate paragraphs with a blank line (two newlines: \\n\\n).
You MUST use **double asterisks** for bold on grant names and key figures.

FORMATTING FOR READABILITY:
- Use SHORT paragraphs (2-4 sentences max per paragraph)
- Add a BLANK LINE between EVERY paragraph (this is critical for readability)
- Use **bold** for grant names and key figures (e.g., **i4i Programme**, **£400k-£2M**)
- Total response: 200-350 words (be concise)
- Structure as 3-4 distinct paragraphs:

  Paragraph 1: Your top recommendation and why it fits
  Paragraph 2: Key details (timing, funding range, process)
  Paragraph 3: Strategic considerations or alternatives
  Paragraph 4: Next step or question (brief)

STILL FORBIDDEN:
- Numbered lists (1. 2. 3.)
- Bullet points (- or •)
- Headers or markdown headers (##)
- Long dense paragraphs (5+ sentences)

NEVER START YOUR RESPONSE WITH:
- "Great question..."
- "Thanks for sharing..."
- "It sounds like you have..."
- "That's really interesting..."
- "It's great to hear..."
- Any compliment or acknowledgment

ALWAYS START YOUR RESPONSE WITH:
- Your top recommendation by name (in **bold**)
- A direct answer to their question
- The single most important thing they need to know

AILSA'S CHARACTERISTIC LANGUAGE (use these naturally in prose):
- "This is a snug fit for..."
- "I'd suggest going in boldly on..."
- "The biggest go/no-go factor here is..."
- "Get in early on this one"
- "Nice tidy grant for..."
- "Great foot in the door"
- "Transform their needs into..."
- "Position this as..."
- "The framing will be key here"
- "Food for thought:"
- "They will not fund..."
- "Success rates are around X%"

VOICE:
- Be opinionated: "Here's what I'd do" not "You could consider"
- Lead with your single best recommendation, then expand
- When asked "which should I do?" - ANSWER IT. Pick one. Justify it.
- Don't bounce questions back: "which do you prefer?" is a cop-out
- Match urgency - if they mention competitors or runway, factor that in
- Reference facts they've told you, don't re-ask

LINKING TO GRANTS:
- When you recommend a grant, include its URL as a markdown link
- Format: **[Grant Name](URL)**
- Example: "**[i4i Programme](https://www.nihr.ac.uk/funding/i4i)** is your best fit..."
- Only link grants that have URLs in the MATCHED GRANTS context - never invent URLs
- If a grant doesn't have a URL in context, just mention it by name in **bold** without a link
- This makes it easy for users to apply directly

EXAMPLE OF WELL-FORMATTED RESPONSE:

"**i4i Programme** is your best move here. At TRL 5 with NHS clinical partnership already in place, you're exactly what they fund. The £400k-£600k ask fits comfortably within their typical **£400k-£2M** range, and clinical validation for CE marking is their sweet spot.

The timeline reality: expect 6-9 months from application to funds in account. Get your application started now - the competition is fierce and rounds fill up. Your Manchester Royal Eye Hospital connection is a genuine asset; formalise that relationship with a subcontract, not just a letter of support.

On the grant vs equity question - given your £180k runway and competitor pressure, here's the play: pursue both tracks. Submit to **i4i** AND continue Series A conversations. They're not mutually exclusive, and £400k of non-dilutive funding landing in 9 months strengthens your negotiating position either way.

What's your current relationship with Manchester Royal Eye Hospital - informal discussions or something more concrete?"
"""

    def _build_strategic_prompt(self, query: str, grants: List[Dict],
                                user_profile: Dict, context: Dict, intent: str = None) -> str:
        """Build detailed prompt with all context."""

        # Format user profile
        profile_text = self._format_profile(user_profile)

        # Format grants
        grants_text = self._format_grants(grants)

        # Detect multiple variants of the same programme
        variant_warning = self._detect_grant_variants(grants)

        # Format conversation history
        history_text = self._format_conversation(context.get("recent_messages", []))

        # Format discussed grants
        discussed = context.get("discussed_grants", [])
        discussed_text = f"Recently discussed: {', '.join(discussed)}" if discussed else ""

        # Add follow-up specific guidance
        followup_warning = ""
        if intent == "followup":
            followup_warning = """
⚠️ THIS IS A FOLLOW-UP QUESTION:
The user is asking about the grants you JUST discussed in your previous response.
DO NOT treat this as a new discovery query.
Answer specifically about the grants in context, not a general list."""

        prompt = f"""USER PROFILE:
{profile_text}

CONVERSATION HISTORY:
{history_text}
{discussed_text}

MATCHED GRANTS:
{grants_text}

{variant_warning}
{followup_warning}

CURRENT QUERY: "{query}"

Provide strategic advice that:
1. References the conversation context appropriately
2. Analyzes the user's situation vs. grant requirements
3. Identifies specific strengths and gaps
4. Suggests concrete next steps
5. Asks a strategic follow-up question

Be natural and conversational. Don't use bullet points unless comparing specific criteria."""

        return prompt

    def _detect_grant_variants(self, grants: List[Dict]) -> str:
        """
        Detect if there are multiple variants of the same programme.
        Returns a warning message if variants are found.
        """
        if len(grants) < 2:
            return ""

        # Group grants by base programme name (remove modifiers like "small", "large", etc.)
        from collections import defaultdict
        import re

        programme_groups = defaultdict(list)

        for grant in grants:
            title = grant.get('title', '')
            # Extract base programme name (before colon or common modifiers)
            base_name = re.split(r'[:–-]|(small|large|phase|stream|track|tier)', title, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            programme_groups[base_name.lower()].append(title)

        # Find programmes with multiple variants
        variants = []
        for base_name, titles in programme_groups.items():
            if len(titles) > 1:
                variants.append(f"- {base_name.title()}: {len(titles)} variants ({', '.join(titles[:3])})")

        if variants:
            return f"""⚠️ IMPORTANT - MULTIPLE VARIANTS DETECTED:
The grants above include multiple variants of the same programme(s):
{chr(10).join(variants)}

You MUST discuss ALL variants and compare them. Do not arbitrarily pick one."""
        return ""

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
        # Include up to 8 grants if multiple variants of same programme
        max_grants = min(len(grants), 8)

        for i, grant in enumerate(grants[:max_grants], 1):
            # Handle different grant data structures
            title = grant.get('title') or grant.get('grant_id', 'Unknown')
            source = grant.get('source', 'Unknown')
            funding = grant.get('total_fund_gbp') or grant.get('funding_amount', 'TBC')
            deadline = grant.get('closes_at') or grant.get('deadline', 'TBC')
            eligibility = grant.get('eligibility') or grant.get('eligibility_text', 'See grant details')
            description = grant.get('description', '')
            url = grant.get('url', '')

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
   URL: {url if url else 'Not available'}
   Description: {description[:300] if description else 'See grant details'}
   Eligibility: {eligibility[:200] if eligibility else 'See grant details'}
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
