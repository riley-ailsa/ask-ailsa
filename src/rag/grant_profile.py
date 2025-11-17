"""
Grant Profile Builder - Creates structured profiles from aggregated grant data.
"""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def build_grant_profile(grant_group: Dict[str, Any]) -> str:
    """
    Build a structured, comprehensive profile for a grant.

    Args:
        grant_group: Aggregated grant data from group_results_by_grant()

    Returns:
        Formatted grant profile string
    """
    # Extract metadata
    title = grant_group["title"]
    source = grant_group["source"]
    funding = grant_group["funding"]
    status = grant_group["status"]
    is_active = grant_group["is_active"]
    deadline = grant_group.get("deadline", "Not specified")
    opens = grant_group.get("opens_at", "Not specified")
    aggregated_text = grant_group["aggregated_text"]
    description = grant_group.get("description", "")

    # Format source name
    source_name = "Innovate UK" if source == "innovate_uk" else "NIHR"

    # Use existing description if available, otherwise generate from aggregated text
    if description:
        summary = description
    elif aggregated_text:
        # Use the aggregated text directly as context (LLM will synthesize)
        summary = _build_summary_from_text(aggregated_text)
    else:
        summary = "No description available."

    # Build profile with clear status indicators
    status_emoji = "🟢" if is_active else "🔴"
    status_text = f"{status_emoji} {status.capitalize()}"

    profile = f"""**{title}**
Source: {source_name}
Funding: {funding}
Status: {status_text}
Deadline: {deadline if deadline != "Not specified" else "Not specified"}
Opens: {opens if opens != "Not specified" else "Not specified"}

{summary}

---
Additional Context:
{aggregated_text[:800] if aggregated_text else "No additional context available"}
"""

    return profile


def _build_summary_from_text(aggregated_text: str) -> str:
    """
    Build a summary from aggregated text (simple extraction).

    Args:
        aggregated_text: Combined text from all documents

    Returns:
        Summary text
    """
    # Simple approach: take first 500 chars as summary
    # In production, this would use LLM summarization
    if len(aggregated_text) <= 500:
        return aggregated_text

    # Find sentence boundary
    summary = aggregated_text[:500]
    last_period = summary.rfind('.')
    if last_period > 250:  # Only if we don't lose too much
        return aggregated_text[:last_period + 1]

    return summary + "..."


def generate_grant_summary_with_llm(title: str, aggregated_text: str, llm_client) -> str:
    """
    Generate a concise summary from aggregated grant text using LLM.

    Args:
        title: Grant title
        aggregated_text: Combined text from all documents
        llm_client: Initialized LLM client

    Returns:
        2-3 paragraph summary
    """
    # Truncate text if too long
    if len(aggregated_text) > 4000:
        aggregated_text = aggregated_text[:4000] + "..."

    # Build prompt
    system_prompt = (
        "You create concise, informative summaries of funding opportunities.\n\n"
        "Requirements:\n"
        "- Write 2-3 paragraphs (150-250 words)\n"
        "- Cover: what the funding is for, who can apply, key themes\n"
        "- Include eligibility if mentioned\n"
        "- Mention typical project scope if mentioned\n"
        "- Be specific and factual\n"
        "- Use clear, professional language\n"
    )

    user_prompt = (
        f"Grant Title: {title}\n\n"
        f"Grant Content:\n{aggregated_text}\n\n"
        "Generate a comprehensive summary covering purpose, eligibility, and scope."
    )

    try:
        summary = llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,
            max_tokens=400
        )
        return summary.strip()
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return "Summary generation failed."
