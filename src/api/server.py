"""
Grant Discovery API Server

RESTful API for searching and exploring grant opportunities.

Endpoints:
    GET  /health              - Health check
    GET  /grants              - List grants
    GET  /grants/{grant_id}   - Get grant details
    GET  /search              - Semantic search
    POST /search/explain      - LLM-powered search explanation
"""

import logging
import re
import sqlite3
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from src.api.schemas import (
    HealthResponse,
    GrantSummary,
    GrantDetail,
    GrantWithDocuments,
    DocumentSummary,
    SearchResponse,
    SearchHit,
    ExplainRequest,
    ExplainResponse,
    ReferencedGrant,
    ChatTurn,
    ChatRequest,
    ChatGrant,
    ChatResponse,
)
from src.storage.grant_store import GrantStore
from src.storage.document_store import DocumentStore
from src.storage.explanation_cache import ExplanationCache
from src.index.vector_index import VectorIndex
from src.core.domain_models import Grant


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="Grant Discovery API",
    version="1.0.0",
    description="Search and explore grant opportunities. Powered by GPT-5 for intelligent explanations.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware (adjust origins for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Initialize storage and index
DB_PATH = "grants.db"
grant_store = GrantStore(DB_PATH)
doc_store = DocumentStore(DB_PATH)
vector_index = VectorIndex(db_path=DB_PATH)
explanation_cache = ExplanationCache(DB_PATH)

# LLM client (initialized on first use)
llm_client: Optional['LLMClient'] = None

# Chat LLM client (initialized lazily)
chat_llm_client = None


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

def _get_grant_summary(grant_id: str) -> Optional[str]:
    """
    Fetch cached GPT summary for a grant.

    Args:
        grant_id: Grant ID to look up

    Returns:
        Summary text if available, None otherwise
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT summary FROM grant_summaries WHERE grant_id = ?",
            (grant_id,)
        )
        row = cur.fetchone()
        conn.close()

        if row:
            return row[0]
    except Exception as e:
        # Don't break search if summary lookup fails
        logger.error(f"Failed to load summary for {grant_id}: {e}")

    return None


def _build_snippet(text: str, max_len: int = 300) -> str:
    """
    Build snippet from document text (fallback when no summary).

    Args:
        text: Document text
        max_len: Maximum snippet length

    Returns:
        Truncated snippet with ellipsis if needed
    """
    text = text.strip()
    if len(text) <= max_len:
        return text

    # Truncate at sentence boundary if possible
    truncated = text[:max_len]
    last_period = truncated.rfind('.')
    if last_period > max_len * 0.5:  # Only if we don't lose too much
        return text[:last_period + 1]

    return truncated.rstrip() + "..."


def _grant_to_summary(grant: Grant) -> GrantSummary:
    """Convert Grant domain object to GrantSummary schema."""
    return GrantSummary(
        id=grant.id,
        title=grant.title,
        url=grant.url,
        source=grant.source,
        total_fund=grant.total_fund,
        closes_at=grant.closes_at.isoformat() if grant.closes_at else None,
        is_active=grant.is_active,
        tags=grant.tags or [],
    )


# Scoring thresholds for grant filtering
MIN_SCORE_STRONG = 0.55
MIN_SCORE_WEAK = 0.48
MAX_GRANTS = 5  # Show up to 5 relevant grants

# System prompt for neutral search assistant
SYSTEM_PROMPT = """You are Ailsa, an expert UK research funding advisor with deep knowledge of NIHR and Innovate UK grant programs.

PRIMARY DIRECTIVE: Provide COMPLETE, THOROUGH, and ACTIONABLE responses about UK research funding opportunities.

CORE BEHAVIOR:
- You have access to a curated database of NIHR and Innovate UK grants through semantic search
- The grants provided in context are the MOST RELEVANT matches based on the user's query
- When specific grants are provided in context, discuss them in detail
- You can ALSO use your general knowledge about UK research funding to answer questions about:
  * Grant application processes and best practices
  * Typical eligibility requirements for different funding bodies
  * General advice about research funding strategy
  * Explanations of funding terminology (TRL levels, i4i, KTP, etc.)
  * Information about other UK funding bodies beyond NIHR/Innovate UK
- If the database has no relevant grants but the question is about general funding advice, provide helpful guidance from your knowledge
- Present ALL relevant details from the context - don't summarize away important information
- If multiple grants are relevant, discuss all of them unless user asks for specific ones

RESPONSE STRUCTURE:

1. **Brief Opening** (1-2 sentences max)
   - Direct answer with key numbers
   - Example: "You have 4 open NIHR grants for clinical trials, closing between Dec 2 and Jan 7. Here are the most urgent opportunities."

2. **Grant Sections** (CONCISE format per grant)
   Structure each grant like this:

   ## Grant Name

   One-sentence description of what it funds.

   **Why relevant:** One sentence explaining the match.

   **Key tip:** One actionable insight about the application.

   CRITICAL CONDENSING RULES FOR EACH GRANT:
   - MAX 3-4 sentences total per grant
   - NO repetition of funding/deadline (shown in cards below)
   - Focus on insights, not descriptions
   - Be direct: Cut "This grant is particularly relevant as..." → use "Perfect for..."

3. **Quick Action Steps** (3-4 bullets max)
   - Most urgent deadline first
   - One clear action per bullet
   - Example: "1. Prioritize Dec 2 deadlines - start applications now"

OVERALL CONDENSING RULES:
- No more than 3-4 grants discussed in detail
- Each grant section: 3-4 sentences maximum
- Cut verbose phrases and filler
- Be punchy and actionable

CRITICAL: The grant cards below your response show funding, deadline, and basic details.
Your text should ADD VALUE, not repeat. Focus on insights, strategy, and process details.

FORMATTING GUIDELINES FOR STREAMLIT:
- Use ## for grant section headers (e.g., "## EME Programme researcher-led")
- Use ### for subsections within grants (e.g., "### Application Tips")
- Use **bold** for emphasis and labels (e.g., "**Why it's relevant:**")
- Use bullet points (- ) for lists, keep them concise (3-5 items max)
- Use numbered lists (1. 2. 3.) for sequential steps
- Keep paragraphs short (2-4 sentences)
- Add blank lines between sections for readability
- Vary sentence structure - mix short and longer sentences
- Use transition phrases: "Building on this," "Alternatively," "It's worth noting"
- Be specific and concrete, avoid vague language

Example structure:
```
Opening summary paragraph.

## Grant Name (£XM, closes DATE)

Description paragraph with **bold emphasis**.

**Why it's relevant:** Explanation here.

**Application tips:**
- Tip 1
- Tip 2
- Tip 3

## Next Grant Name

Next description.
```

DO NOT use:
- Single # headers (too large)
- More than 3 levels of headers
- Excessive bold text
- Tables (Streamlit handles them poorly)

CRITICAL RULES:
- If a grant is closed, MENTION IT but explain what it was and suggest when similar opportunities might open
- Always include relevance context (e.g., "This grant matches your query because...")
- If user asks about eligibility, be specific about requirements from the context
- Compare grants when multiple options exist
- Explain technical terms if they appear (TRL levels, i4i, KTP, etc.)

HANDLING EDGE CASES:
- If NO grants match but question is about grant processes/strategy: Provide helpful general advice from your knowledge
- If grants don't match but user asks "how to apply" or "tips": Give general application guidance
- If user asks about specific grant by name: Find it in context and provide full details
- If user asks about deadlines: Emphasize urgency and list all upcoming deadlines from context
- If comparing academic vs. commercial: Highlight eligibility differences clearly from the grants

GENERAL GRANT QUESTIONS (when no specific grants in context):
You can answer questions like:
- "What is a TRL level?" - Explain Technology Readiness Levels
- "How do I write a strong grant application?" - Provide best practices
- "What's the difference between NIHR and Innovate UK?" - Explain the funding bodies
- "What are typical eligibility requirements?" - Provide general guidance
- "Are there other UK funding bodies I should know about?" - Suggest UKRI, MRC, EPSRC, etc.

When answering general questions:
1. Acknowledge you're providing general guidance (not database-specific info)
2. Be helpful and educational
3. Suggest they ask about specific opportunities if relevant
4. Don't pretend to have database info when you don't

TONE & STYLE:
- Professional but warm and encouraging
- Write like a knowledgeable colleague, not a formal document
- Use "you" to speak directly to the user
- Show enthusiasm for relevant opportunities without overselling
- Be specific and concrete, avoid vague language

AVOID THESE PATTERNS:
- ❌ "This grant is highly relevant as it..." (too formal/robotic)
- ❌ Starting every paragraph with "This grant..."
- ❌ Overusing "notably," "particularly," "specifically"
- ❌ Passive voice: "Applications are invited" → use "You can apply"
- ❌ Repeating funding/deadline info that's in the grant cards

PREFER THESE PATTERNS:
- ✅ "This £1M prize is perfect for your AI project because..."
- ✅ "If you're working on quantum AI, consider..."
- ✅ "With just 2 days left, act quickly on..."
- ✅ "You'll need a Canadian partner organization for this one"

APPLICATION PROCESS INTELLIGENCE:
When discussing specific grants, check for and mention:
- Multi-stage processes: "This uses a two-stage process - submit an outline first"
- Interviews: "Shortlisted applicants will be invited to interviews in [date]"
- Briefing events: "A briefing webinar on [date] is highly recommended"
- Collaboration requirements: "UK-Canada partnerships required"
- Preparatory grants: "Consider the Development Award first to strengthen your proposal"

HANDLING "ANYTHING FROM [SOURCE]?" QUERIES:
When user asks about a specific funding source (NIHR, Innovate UK):
- Filter results to ONLY that source
- Lead with the count: "NIHR has 2 open opportunities right now"
- If most are closed: "NIHR has 2 open now, though several recently closed"
- Focus primarily on open grants
- For closed grants, ONLY mention if recurring: "The Mental Health Research Groups grant closed in May but typically reopens annually"

You MUST respond in valid JSON format with exactly these keys:
{
  "answer_markdown": "Your comprehensive markdown response (3-8 paragraphs depending on query complexity)",
  "recommended_grants": [
    {
      "grant_id": "grant_id_here",
      "title": "grant title",
      "source": "innovate_uk or nihr",
      "reason": "detailed explanation of why this grant is relevant (2-3 sentences)"
    }
  ]
}
"""

USER_PROMPT_TEMPLATE = """User question:
{query}

Available grants from semantic search (ranked by relevance):
{grant_summaries}

Your task:
1. Write a COMPREHENSIVE response that addresses the user's question thoroughly
2. Analyze ALL grants provided and discuss the most relevant ones in detail
3. Include specific information: funding amounts, deadlines, eligibility, and why each grant matches
4. Select up to 5 most relevant grants for the recommended_grants list (score >= {min_score_strong})
5. Do NOT hallucinate grants - only reference grants provided above

IMPORTANT INSTRUCTIONS:
- Use the grant information above to provide detailed, actionable advice
- Explain WHY each grant is relevant to the user's specific question
- If grants are closed, mention them and explain when similar opportunities might be available
- Include funding amounts and deadlines prominently
- Use markdown formatting for readability (bold for key info, bullets for lists)
- Be thorough but well-organized - aim for 3-8 paragraphs depending on complexity
- The grant cards will appear below your response, so provide context and analysis, not just repetition

Respond in valid JSON with keys:
- "answer_markdown": comprehensive markdown-formatted response that thoroughly addresses the query
- "recommended_grants": a list (max 5) of the most relevant grants with:
    - grant_id
    - title
    - source
    - reason (2-3 sentences explaining relevance and fit)
"""


def apply_semantic_boost(query: str, title: str, base_score: float) -> float:
    """
    Apply semantic boosting based on query and grant title keywords.

    Args:
        query: User's search query
        title: Grant title
        base_score: Base relevance score

    Returns:
        Boosted score
    """
    q = query.lower()
    t = title.lower()

    score = base_score

    # Cancer / oncology boosting
    if "cancer" in q or "oncolog" in q:
        if "cancer" in t or "oncolog" in t:
            score *= 1.12

    # Therapeutics / therapy
    if "therap" in q:
        if "therap" in t or "treatment" in t:
            score *= 1.08

    # Paediatrics / pediatrics
    if "paediatr" in q or "pediatr" in q:
        if "paediatr" in t or "pediatr" in t or "children" in t or "child" in t:
            score *= 1.10

    # AI / agentic / LLM
    if any(term in q for term in ["ai", "artificial intelligence", "llm", "agentic"]):
        if any(term in t for term in ["ai", "artificial intelligence", "agentic", "llm"]):
            score *= 1.10

    return score


def select_top_grants(hits, query: str = ""):
    """
    Filter and deduplicate grants by score threshold with semantic boosting.

    Args:
        hits: List of search results with grant_id, score, metadata
        query: User query for semantic boosting

    Returns:
        List of top grant summaries (up to MAX_GRANTS)
    """
    from collections import defaultdict

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

        # Apply semantic boosting
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

    for item in items:
        if item["best_score"] < MIN_SCORE_STRONG:
            continue  # Skip low-relevance grants entirely

        # Check if grant is truly open based on deadline
        is_open = item["status"] == "open"
        if item["closes_at"]:
            try:
                deadline_dt = datetime.fromisoformat(item["closes_at"].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                is_open = deadline_dt > now
            except:
                pass  # Keep original status if parsing fails

        if is_open:
            open_grants.append(item)
        else:
            closed_grants.append(item)

    # Sort each group by score
    open_grants.sort(key=lambda x: x["best_score"], reverse=True)
    closed_grants.sort(key=lambda x: x["best_score"], reverse=True)

    # Prioritize open grants but include 1-2 closed if we have few open grants
    relevant = open_grants[:MAX_GRANTS]

    # Only add closed grants if we have fewer than 3 open grants
    if len(relevant) < 3 and closed_grants:
        # Add up to 2 closed grants to provide context
        relevant.extend(closed_grants[:2])
        relevant = relevant[:MAX_GRANTS]  # Ensure we don't exceed max

    logger.info(f"Selected {len(open_grants)} open and {len(closed_grants)} closed grants, returning {len(relevant)} total")

    return relevant


def build_llm_context(query: str, hits, grants_for_llm):
    """
    Build comprehensive LLM context from selected grants with rich detail.

    Args:
        query: User query
        hits: All search hits
        grants_for_llm: Selected grant summaries

    Returns:
        Formatted context string with detailed grant information
    """
    from datetime import datetime, timezone

    selected_ids = {g["grant_id"] for g in grants_for_llm}

    # Group hits by grant to combine information
    from collections import defaultdict
    grant_hits = defaultdict(list)

    for h in hits:
        if h.grant_id in selected_ids:
            grant_hits[h.grant_id].append(h)

    context_blocks = []

    for grant_summary in grants_for_llm:
        gid = grant_summary["grant_id"]
        grant = grant_store.get_grant(gid)

        if not grant:
            continue

        # Calculate deadline urgency
        deadline_display = "Not specified"
        urgency_note = ""
        if grant.closes_at:
            deadline_display = grant.closes_at.isoformat()
            try:
                now = datetime.now(timezone.utc)
                deadline_dt = grant.closes_at
                if deadline_dt.tzinfo is None:
                    from datetime import timezone
                    deadline_dt = deadline_dt.replace(tzinfo=timezone.utc)

                days_until = (deadline_dt - now).days

                if days_until < 0:
                    urgency_note = " (⚠️ CLOSED)"
                elif days_until < 30:
                    urgency_note = f" (⚠️ Closing soon: {days_until} days remaining)"
                elif days_until < 90:
                    urgency_note = f" ({days_until} days remaining)"
            except:
                pass

        # Format funding amount
        funding_amount = getattr(grant, 'total_fund_gbp', None) or grant.total_fund
        if funding_amount:
            if isinstance(funding_amount, (int, float)):
                funding_display = f"£{funding_amount:,.0f}"
            else:
                funding_display = str(funding_amount)
        else:
            funding_display = "Not specified"

        # Get best snippet from hits
        relevant_snippets = []
        for h in grant_hits[gid]:
            if hasattr(h, 'text') and h.text:
                doc_type = h.metadata.get("doc_type", "general") if hasattr(h, 'metadata') else "general"
                snippet_text = h.text[:600].strip()
                if snippet_text:
                    relevant_snippets.append(f"  [{doc_type.upper()}] {snippet_text}")

        snippets_text = "\n".join(relevant_snippets[:3]) if relevant_snippets else "  No additional context available"

        # Build rich context block
        context_blocks.append(f"""
═══════════════════════════════════════════════════════════
GRANT | Relevance Score: {grant_summary['best_score']:.3f}
═══════════════════════════════════════════════════════════

Title: {grant.title}
Grant ID: {gid}
Source: {grant.source.upper()}
Status: {grant_summary['status'].upper()}{urgency_note}

💰 Funding Amount: {funding_display}
📅 Deadline: {deadline_display}{urgency_note}
🔗 URL: {grant.url or 'Not available'}

Relevant Context Snippets:
{snippets_text}

---
""")

    header = f"""Found {len(grants_for_llm)} highly relevant grants ranked by semantic similarity.
Use ALL of this information to provide a comprehensive, thorough response.
Higher relevance scores indicate better matches to the user's query.

IMPORTANT: Analyze all grants below and provide detailed insights about each relevant one.

"""

    return header + "\n".join(context_blocks)


def build_user_prompt(query, grants_for_llm):
    """Build user prompt with grant summaries."""
    if grants_for_llm:
        lines = []
        for g in grants_for_llm:
            lines.append(
                f"- {g['title']} (id={g['grant_id']}, "
                f"source={g['source']}, score={g['best_score']:.3f}, "
                f"status={g['status']}, closes_at={g['closes_at']}, "
                f"funding={g['total_fund_gbp']})"
            )
        summary = "\n".join(lines)
    else:
        summary = "(no suitable grants found above the score thresholds)"

    return USER_PROMPT_TEMPLATE.format(
        query=query,
        grant_summaries=summary,
        min_score_strong=MIN_SCORE_STRONG,
    )


def explain_with_gpt(client, query: str, hits):
    """
    Generate explanation using GPT with filtered grants.

    Args:
        client: LLM client
        query: User query
        hits: Search results

    Returns:
        Tuple of (answer_markdown, recommended_grants)
    """
    import json

    # Step 1: Select top grants with semantic boosting
    grants = select_top_grants(hits, query=query)

    # Step 2: Build context
    context = build_llm_context(query, hits, grants)

    # Step 3: Call GPT
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                build_user_prompt(query, grants)
                + "\n\nContext from grant documents:\n"
                + context
            ),
        },
    ]

    raw = client.chat(
        messages=messages,
        temperature=0.5,  # Slightly higher for more natural, detailed responses
        max_tokens=2000,  # Allow for thorough, comprehensive answers
    )

    # Parse JSON response
    try:
        data = json.loads(raw)
    except Exception:
        # Fallback: wrap plain text
        data = {
            "answer_markdown": raw,
            "recommended_grants": [
                {
                    "grant_id": g["grant_id"],
                    "title": g["title"],
                    "source": g["source"],
                    "reason": f"Relevance score: {g['best_score']:.3f}"
                }
                for g in grants[:3]
            ],
        }

    answer_markdown = data.get("answer_markdown", "").strip()
    recs = data.get("recommended_grants", []) or []

    # Enrich recommendations with scores from the original grants list
    grant_scores = {g["grant_id"]: g["best_score"] for g in grants}
    for rec in recs:
        if "grant_id" in rec and rec["grant_id"] in grant_scores:
            rec["best_score"] = grant_scores[rec["grant_id"]]
            rec["url"] = next((g["url"] for g in grants if g["grant_id"] == rec["grant_id"]), "#")

    return answer_markdown, recs


def _chat_retrieve(
    query_text: str,
    top_k: int,
    active_only: bool,
    sources: Optional[List[str]],
) -> tuple:
    """
    Retrieve relevant grants for chat using vector search.

    Args:
        query_text: User's question/query
        top_k: Number of results to retrieve
        active_only: Filter to active grants only
        sources: Optional source filter (innovate_uk, nihr)

    Returns:
        Tuple of (hits, grants_by_id)
    """
    # Use existing vector index
    hits = vector_index.query(
        query_text=query_text,
        top_k=top_k * 2,  # Over-fetch for filtering
        filter_scope=None
    )

    # Load and filter grants
    grants_by_id = {}

    for hit in hits:
        gid = hit.grant_id
        if not gid or gid in grants_by_id:
            continue

        grant = grant_store.get_grant(gid)
        if not grant:
            continue

        # Apply filters
        if active_only and not grant.is_active:
            continue

        if sources and grant.source not in sources:
            continue

        grants_by_id[gid] = grant

        # Stop when we have enough
        if len(grants_by_id) >= top_k:
            break

    # Filter hits to only those with valid grants
    filtered_hits = [h for h in hits if h.grant_id in grants_by_id]

    return filtered_hits, grants_by_id


def group_results_by_grant(hits: list, max_grants: int = 5) -> list:
    """
    Group document-level search hits by grant and aggregate content.

    Args:
        hits: List of document-level search results
        max_grants: Maximum number of grants to return

    Returns:
        List of grant groups with aggregated content
    """
    from collections import defaultdict
    from datetime import datetime

    # Group hits by grant_id
    grant_groups = defaultdict(list)
    for hit in hits:
        if hit.grant_id:
            grant_groups[hit.grant_id].append(hit)

    # Build aggregated grant objects
    results = []

    for grant_id, grant_hits in grant_groups.items():
        # Get grant metadata
        grant = grant_store.get_grant(grant_id)
        if not grant:
            continue

        # Calculate max score for this grant
        max_score = max(h.score for h in grant_hits)

        # Aggregate text from all documents (limit to 4000 chars)
        texts = []
        total_chars = 0
        for hit in sorted(grant_hits, key=lambda h: h.score, reverse=True):
            if total_chars >= 4000:
                break
            chunk = hit.text[:1000]  # Limit each chunk
            texts.append(chunk)
            total_chars += len(chunk)

        aggregated_text = "\n\n".join(texts)

        # Get or generate description
        description = _get_grant_summary(grant_id) or grant.description or ""

        # Determine status
        status = "open" if grant.is_active else "closed"
        if grant.opens_at and grant.opens_at > datetime.now():
            status = "upcoming"

        results.append({
            "grant_id": grant_id,
            "score": max_score,
            "title": grant.title,
            "source": grant.source,
            "funding": grant.total_fund or "Not specified",
            "status": status,
            "is_active": grant.is_active,
            "deadline": grant.closes_at.isoformat() if grant.closes_at else None,
            "opens_at": grant.opens_at.isoformat() if grant.opens_at else None,
            "closes_at": grant.closes_at.isoformat() if grant.closes_at else None,
            "description": description,
            "aggregated_text": aggregated_text,
            "documents": grant_hits,
            "url": grant.url
        })

    # Sort by score and take top N
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_grants]


def _grant_to_detail(grant: Grant) -> GrantDetail:
    """Convert Grant domain object to GrantDetail schema."""
    return GrantDetail(
        id=grant.id,
        title=grant.title,
        url=grant.url,
        source=grant.source,
        description=grant.description,
        total_fund=grant.total_fund,
        project_size=grant.project_size,
        opens_at=grant.opens_at.isoformat() if grant.opens_at else None,
        closes_at=grant.closes_at.isoformat() if grant.closes_at else None,
        is_active=grant.is_active,
        funding_rules=grant.funding_rules or {},
        tags=grant.tags or [],
    )


def _truncate(text: str, max_chars: int = 900) -> str:
    """Truncate text to max_chars, adding ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Health check endpoint.

    Returns:
        System health status
    """
    # Count documents as a proxy for index size
    # In production, get this from vector index stats
    vector_size = len(vector_index._vectors) if hasattr(vector_index, '_vectors') else 0

    return HealthResponse(
        status="healthy",
        database=DB_PATH,
        vector_index_size=vector_size,
    )


@app.get("/grants", response_model=List[GrantSummary])
async def list_grants(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of grants to return"),
    offset: int = Query(0, ge=0, description="Number of grants to skip"),
    active_only: bool = Query(False, description="Only return active grants"),
):
    """
    List grants with pagination.

    Args:
        limit: Maximum number of results
        offset: Pagination offset
        active_only: Filter for active grants only

    Returns:
        List of grant summaries
    """
    grants = grant_store.list_grants(limit=limit, offset=offset, active_only=active_only)
    return [_grant_to_summary(g) for g in grants]


@app.get("/grants/{grant_id}", response_model=GrantWithDocuments)
async def get_grant(grant_id: str):
    """
    Get detailed information about a specific grant.

    Args:
        grant_id: Grant identifier

    Returns:
        Grant details with associated documents

    Raises:
        HTTPException: If grant not found
    """
    grant = grant_store.get_grant(grant_id)

    if not grant:
        raise HTTPException(status_code=404, detail=f"Grant not found: {grant_id}")

    # Get associated documents
    docs = doc_store.get_documents_for_grant(grant_id)

    return GrantWithDocuments(
        grant=_grant_to_detail(grant),
        documents=[
            DocumentSummary(
                id=d.id,
                doc_type=d.doc_type,
                scope=d.scope,
                source_url=d.source_url,
                length=len(d.text),
            )
            for d in docs
        ],
    )


@app.get("/search", response_model=SearchResponse)
async def search(
    query: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(10, ge=1, le=100, description="Number of results to return"),
    active_only: bool = Query(True, description="Only return active grants"),
    min_funding: Optional[int] = Query(None, description="Minimum funding in GBP"),
    max_funding: Optional[int] = Query(None, description="Maximum funding in GBP"),
    sources: Optional[List[str]] = Query(None, description="Filter by source (innovate_uk, nihr)"),
    filter_scope: Optional[str] = Query(None, description="Filter by scope: 'competition' or 'global'"),
):
    """
    Perform semantic search over indexed documents with optional filters.

    Args:
        query: Natural language search query
        top_k: Maximum number of results (1-100)
        active_only: Only return active grants
        min_funding: Minimum funding amount in GBP
        max_funding: Maximum funding amount in GBP
        sources: List of sources to include (e.g., ["nihr", "innovate_uk"])
        filter_scope: Optional scope filter

    Returns:
        Search results with relevance scores
    """
    logger.info(f"Search query: {query} (top_k={top_k}, active_only={active_only}, scope={filter_scope})")

    # Over-fetch to account for filtering
    fetch_k = min(top_k * 3, 150)

    # Query vector index
    hits = vector_index.query(
        query_text=query,
        top_k=fetch_k,
        filter_scope=filter_scope,
    )

    # Convert to API schema with filtering
    results: List[SearchHit] = []

    for hit in hits:
        # Get grant details
        grant = grant_store.get_grant(hit.grant_id) if hit.grant_id else None

        if not grant:
            continue

        # Apply filters
        if active_only and not grant.is_active:
            continue

        if min_funding is not None:
            # Parse total_fund to get GBP amount
            fund_amount = None
            if grant.total_fund:
                # Extract numeric value from total_fund string
                import re
                match = re.search(r'[\d,]+', grant.total_fund)
                if match:
                    try:
                        fund_amount = int(match.group().replace(',', ''))
                    except ValueError:
                        pass

            if fund_amount is None or fund_amount < min_funding:
                continue

        if max_funding is not None:
            # Parse total_fund to get GBP amount
            fund_amount = None
            if grant.total_fund:
                import re
                match = re.search(r'[\d,]+', grant.total_fund)
                if match:
                    try:
                        fund_amount = int(match.group().replace(',', ''))
                    except ValueError:
                        pass

            if fund_amount is not None and fund_amount > max_funding:
                continue

        if sources:
            sources_lower = [s.lower() for s in sources]
            if grant.source.lower() not in sources_lower:
                continue

        # Try cached GPT summary first, fallback to chunk snippet
        summary = None
        if hit.grant_id:
            summary = _get_grant_summary(hit.grant_id)

        # Use summary if available, otherwise fallback to snippet
        if summary:
            snippet = summary
        else:
            snippet = _build_snippet(hit.text)

        results.append(
            SearchHit(
                grant_id=hit.grant_id or "unknown",
                title=grant.title,
                source=grant.source,
                score=round(hit.score, 4),
                doc_type=hit.metadata.get("doc_type", "unknown"),
                scope=hit.metadata.get("scope", "unknown"),
                source_url=hit.source_url,
                snippet=snippet,
            )
        )

        # Stop when we have enough results
        if len(results) >= top_k:
            break

    logger.info(f"Search returned {len(results)} results (filtered from {len(hits)} candidates)")

    return SearchResponse(
        query=query,
        total_results=len(results),
        results=results,
    )


@app.post("/search/explain", response_model=ExplainResponse)
async def search_explain(req: ExplainRequest):
    """
    Use GPT-5 to explain which grants best match the query.

    Includes caching to avoid duplicate API calls.

    Process:
    1. Check cache first
    2. Perform semantic search over indexed documents
    3. Retrieve top_k most relevant chunks
    4. Build context from grant details and snippets
    5. Send to GPT-5 for natural language explanation
    6. Cache the result
    7. Return explanation with cited grants

    Args:
        req: Search query and parameters

    Returns:
        GPT-5 generated explanation with grant references

    Raises:
        HTTPException: If GPT-5 client initialization fails or API call fails
    """
    global llm_client

    # Check cache first
    cached = explanation_cache.get(req.query, model="gpt-4o-mini")
    if cached:
        logger.info(f"Returning cached explanation for: {req.query}")
        return ExplainResponse(
            query=req.query,
            explanation=cached["explanation"],
            referenced_grants=[
                ReferencedGrant(**grant)
                for grant in cached["referenced_grants"]
            ],
        )

    # Lazy initialization of GPT-5-mini client
    if llm_client is None:
        try:
            from src.llm.client import LLMClient
            llm_client = LLMClient(model="gpt-4o-mini")
            logger.info("✓ Initialized GPT-5-mini client for /search/explain")
        except ValueError as e:
            logger.error(f"✗ Failed to initialize GPT client: {e}")
            raise HTTPException(
                status_code=500,
                detail="GPT client not configured. Set OPENAI_API_KEY environment variable."
            )
        except Exception as e:
            logger.error(f"✗ Unexpected error initializing GPT: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Perform semantic search
    logger.info(f"Explain query: {req.query} (top_k={req.top_k})")

    hits = vector_index.query(query_text=req.query, top_k=req.top_k * 2)  # Over-fetch

    if not hits:
        logger.info("No relevant grants found")
        return ExplainResponse(
            query=req.query,
            explanation="No relevant grants found for your query. Try broader search terms or different keywords.",
            referenced_grants=[],
        )

    # Group by grant_id and keep best-scoring chunk per grant
    by_grant = {}
    for hit in hits:
        if not hit.grant_id:
            continue
        current = by_grant.get(hit.grant_id)
        if current is None or hit.score > current.score:
            by_grant[hit.grant_id] = hit

    # Sort grants by score, take top N for LLM context
    max_grants_for_llm = 5
    sorted_hits = sorted(by_grant.values(), key=lambda h: h.score, reverse=True)
    selected_hits = sorted_hits[:max_grants_for_llm]

    # Build context from deduplicated grants
    context_blocks: List[str] = []
    referenced_grants: List[ReferencedGrant] = []

    for hit in selected_hits:
        grant = grant_store.get_grant(hit.grant_id)

        if not grant:
            logger.warning(f"Grant not found: {hit.grant_id}")
            continue

        # Extract metadata
        doc_type = hit.metadata.get("doc_type", "unknown")
        scope = hit.metadata.get("scope", "unknown")

        # Get snippet (longer, since we have fewer grants)
        snippet = hit.text[:700] if hasattr(hit, "text") else ""

        # Build context block
        context_blocks.append(
            f"Grant: {grant.title} (source: {grant.source}, id: {grant.id})\n"
            f"Status: {'active' if grant.is_active else 'closed'}\n"
            f"Funding: {grant.total_fund or 'unknown'}\n"
            f"Deadline: {grant.closes_at.isoformat() if grant.closes_at else 'unknown'}\n"
            f"Doc type: {doc_type}, scope: {scope}\n"
            f"Snippet:\n{snippet}\n"
            f"URL: {grant.url}\n"
        )

        referenced_grants.append(
            ReferencedGrant(
                grant_id=grant.id,
                title=grant.title,
                url=grant.url,
                score=round(hit.score, 4),
            )
        )

    logger.info(f"Built context from {len(context_blocks)} unique grants (deduped from {len(hits)} hits)")

    # Improved opinionated prompt
    system_prompt = """You are an expert UK grant funding strategist.

You are given:
- A user query
- A set of candidate grants with snippets and metadata

Your job is to:
- Decide which 1–3 grants are the strongest match.
- Explain your reasoning clearly and efficiently.
- Avoid hedging and fluff.

RULES
- Be opinionated: say which single grant is the top recommendation, if there is one.
- If the matches are weak, say that explicitly and explain why.
- Do NOT invent grants or details that are not supported by the snippets.
- No flattery, no "great question", no long intros. Just answer.

OUTPUT STRUCTURE
1. Short direct answer: 1–2 sentences summarising the overall situation.
2. "Best fits":
   - For each top grant:
     - Name and source (Innovate UK or NIHR)
     - 2–3 bullets on why it fits
     - Funding amount and deadline if available
3. "If you only apply for one…":
   - State which one and why.
4. "Next steps":
   - 2–3 concrete actions (e.g. download specification, check eligibility section, etc.).

Keep it concise. Aim for roughly 400–600 words.
"""

    user_prompt = (
        f"USER QUERY:\n{req.query}\n\n"
        f"RELEVANT GRANTS (ordered by relevance):\n\n" +
        "\n---\n\n".join(context_blocks) +
        "\n\nBased on these grants, explain which ones best match the user's query and why."
    )

    # Call GPT
    try:
        logger.info("Calling GPT...")

        explanation = llm_client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,  # Lower temperature for more focused responses
            max_tokens=1500,
        )

        logger.info(f"✓ GPT response received ({len(explanation)} chars)")

    except Exception as e:
        logger.error(f"✗ GPT API call failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate explanation: {str(e)}"
        )

    # Cache the result
    explanation_cache.set(
        query=req.query,
        explanation=explanation,
        model="gpt-4o-mini",
        referenced_grants=[grant.dict() for grant in referenced_grants],
    )

    return ExplainResponse(
        query=req.query,
        explanation=explanation,
        referenced_grants=referenced_grants,
    )


def normalize_markdown(text: str) -> str:
    """
    Normalize LLM output to ensure clean Markdown formatting.

    Args:
        text: Raw LLM response

    Returns:
        Cleaned Markdown text
    """
    # Ensure headings have blank line before them
    text = re.sub(r'([^\n])(##\s)', r'\1\n\n\2', text)

    # Ensure bullets have proper spacing
    text = re.sub(r'([^\n])(-\s)', r'\1\n\2', text)

    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Prevent accidental bold/heading concatenation
    text = re.sub(r'([A-Za-z])([#*])', r'\1 \2', text)

    return text.strip()


def filter_grants_by_relevance(grant_refs: list, min_score: float = 0.40, max_grants: int = 3) -> list:
    """
    Filter grants to only relevant, high-quality matches.

    Args:
        grant_refs: List of grant references with scores
        min_score: Minimum relevance score threshold
        max_grants: Maximum number of grants to return

    Returns:
        Filtered list of grant references
    """
    # Filter by score
    filtered = [g for g in grant_refs if g.score >= min_score]

    # Sort by score (descending)
    filtered.sort(key=lambda g: g.score, reverse=True)

    # Limit to max_grants
    return filtered[:max_grants]


def classify_grant_matches(
    grouped_grants: list[dict],
    strong_threshold: float = 0.65,
    weak_threshold: float = 0.45,
) -> tuple[list[dict], list[dict]]:
    """
    Classify grants as strong or weak matches based on relevance score.

    Args:
        grouped_grants: List of grant buckets from grant-level aggregation
        strong_threshold: Minimum score for strong match (default 0.65)
        weak_threshold: Minimum score for weak match (default 0.45)

    Returns:
        Tuple of (strong_matches, weak_matches)
    """
    strong = []
    weak = []

    for entry in grouped_grants:
        score = entry["best_score"]
        if score >= strong_threshold:
            strong.append(entry)
        elif score >= weak_threshold:
            weak.append(entry)
        # Below weak_threshold: discard

    return strong, weak


def build_referenced_grants(
    strong_matches: list[dict],
    weak_matches: list[dict],
) -> list[ChatGrant]:
    """
    Build the list of ChatGrant objects for the response,
    marking weak matches as "stretch fit".

    Args:
        strong_matches: List of strong grant buckets
        weak_matches: List of weak grant buckets

    Returns:
        List of ChatGrant objects with stretch_fit flag set appropriately
    """
    chat_grants = []

    # Strong matches first
    for bucket in strong_matches:
        g = bucket["grant"]
        score = bucket["best_score"]

        chat_grants.append(
            ChatGrant(
                grant_id=g.id,
                title=g.title,
                url=g.url,
                source=g.source,
                is_active=g.is_active,
                total_fund_gbp=getattr(g, "total_fund_gbp", None),
                closes_at=g.closes_at.isoformat() if g.closes_at else None,
                score=round(score, 3),
            )
        )

    # Weak matches (stretch fits)
    for bucket in weak_matches:
        g = bucket["grant"]
        score = bucket["best_score"]

        chat_grants.append(
            ChatGrant(
                grant_id=g.id,
                title=g.title,
                url=g.url,
                source=g.source,
                is_active=g.is_active,
                total_fund_gbp=getattr(g, "total_fund_gbp", None),
                closes_at=g.closes_at.isoformat() if g.closes_at else None,
                score=round(score, 3),
            )
        )

    return chat_grants


@app.post("/chat", response_model=ChatResponse)
async def chat_with_grants(req: ChatRequest):
    """
    Chat endpoint with filtered recommendations.

    Uses explain_with_gpt for opinionated, concise responses.
    """
    global chat_llm_client

    query = req.message.strip()
    if not query:
        return ChatResponse(answer="Ask me something about funding.", grants=[])

    logger.info(f"/chat query: {query!r}")

    # Initialize LLM client if needed
    if chat_llm_client is None:
        try:
            from src.llm.client import LLMClient
            chat_llm_client = LLMClient(model="gpt-4o-mini")
            logger.info("✓ Initialized GPT-4o-mini client for /chat")
        except Exception as e:
            logger.error(f"✗ Failed to initialize GPT client: {e}")
            return ChatResponse(
                answer="GPT client not configured. Set OPENAI_API_KEY environment variable.",
                grants=[],
            )

    # Get search hits
    try:
        hits = vector_index.query(
            query_text=query,
            top_k=20,
            filter_scope=None
        )
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return ChatResponse(
            answer="Search failed unexpectedly. Try rephrasing or asking again in a moment.",
            grants=[],
        )

    if not hits:
        return ChatResponse(
            answer="I don't see anything in the current Innovate UK or NIHR data that clearly matches that. "
                   "You might need a different funding body or a more general innovation grant.",
            grants=[],
        )

    # Generate response with filtering
    try:
        answer_markdown, recommended_grants = explain_with_gpt(
            chat_llm_client,
            query,
            hits
        )
    except Exception as e:
        logger.error(f"GPT explanation failed: {e}")
        return ChatResponse(
            answer="I found relevant grants, but the AI layer failed while drafting the explanation. "
                   "Try asking again or narrow your question.",
            grants=[],
        )

    # Build response - convert recommended_grants to ChatGrant objects
    grant_refs = []
    for g in recommended_grants:
        grant_refs.append(
            ChatGrant(
                grant_id=g.get("grant_id", ""),
                title=g.get("title", ""),
                url=g.get("url", "#"),
                source=g.get("source", ""),
                is_active=True,  # Default since we're filtering by active
                total_fund_gbp=g.get("total_fund_gbp"),
                closes_at=g.get("closes_at"),
                score=g.get("best_score", 0.0)
            )
        )

    return ChatResponse(answer=answer_markdown, grants=grant_refs[:5])


@app.post("/chat/stream")
async def chat_with_grants_stream(req: ChatRequest):
    """
    Streaming chat endpoint with real-time responses.

    Returns Server-Sent Events with JSON chunks:
    - {"type": "token", "content": "..."}  - Streamed response text
    - {"type": "grants", "grants": [...]}  - Recommended grants at the end
    - {"type": "done"}                      - End of stream
    """
    import json

    global chat_llm_client

    query = req.message.strip()
    if not query:
        async def empty_generator():
            yield f"data: {json.dumps({'type': 'token', 'content': 'Ask me something about funding.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(empty_generator(), media_type="text/event-stream")

    logger.info(f"/chat/stream query: {query!r}")

    # Initialize LLM client if needed
    if chat_llm_client is None:
        try:
            from src.llm.client import LLMClient
            chat_llm_client = LLMClient(model="gpt-4o-mini")
            logger.info("✓ Initialized GPT-4o-mini client for /chat/stream")
        except Exception as e:
            logger.error(f"✗ Failed to initialize GPT client: {e}")
            async def error_generator():
                yield f"data: {json.dumps({'type': 'token', 'content': 'GPT client not configured. Set OPENAI_API_KEY environment variable.'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return StreamingResponse(error_generator(), media_type="text/event-stream")

    # Get search hits
    try:
        hits = vector_index.query(
            query_text=query,
            top_k=20,
            filter_scope=None
        )
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        async def error_generator():
            yield f"data: {json.dumps({'type': 'token', 'content': 'Search failed unexpectedly. Try rephrasing or asking again in a moment.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(error_generator(), media_type="text/event-stream")

    if not hits:
        async def no_results_generator():
            msg = "I don't see anything in the current Innovate UK or NIHR data that clearly matches that. You might need a different funding body or a more general innovation grant."
            yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(no_results_generator(), media_type="text/event-stream")

    # Generate streaming response
    async def generate():
        try:
            # Step 1: Select top grants
            grants = select_top_grants(hits, query=query)

            # Step 2: Build context
            context = build_llm_context(query, hits, grants)

            # Step 3: Stream GPT response
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        build_user_prompt(query, grants)
                        + "\n\nContext from grant documents:\n"
                        + context
                    ),
                },
            ]

            # Stream the response tokens as they arrive from LLM
            full_response = ""
            for chunk in chat_llm_client.chat_stream(
                messages=messages,
                temperature=0.5,  # Slightly higher for more natural, detailed responses
                max_tokens=2000,  # Allow for thorough, comprehensive answers
            ):
                full_response += chunk
                # Stream each token immediately to the client
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

            # Parse the full response to extract grant recommendations
            try:
                data = json.loads(full_response)
                recs = data.get("recommended_grants", []) or []
            except Exception:
                # If not JSON, use top grants from search
                recs = [
                    {
                        "grant_id": g["grant_id"],
                        "title": g["title"],
                        "source": g["source"],
                        "reason": f"Relevance score: {g['best_score']:.3f}"
                    }
                    for g in grants[:3]
                ]

            # Build lookup map from original grants data
            grants_by_id = {g["grant_id"]: g for g in grants}

            # Debug: Log original grant data
            logger.info(f"Original grants data ({len(grants)} grants):")
            for g in grants[:3]:  # Log first 3
                logger.info(f"  - {g['title']}: funding={g.get('total_fund_gbp')}, deadline={g.get('closes_at')}, score={g.get('best_score')}")

            # Build grant references by enriching LLM recommendations with full grant data
            grant_refs = []
            for rec in recs:
                grant_id = rec.get("grant_id", "")

                # Get full grant data from original grants list
                full_grant = grants_by_id.get(grant_id)

                if full_grant:
                    enriched_grant = {
                        "grant_id": grant_id,
                        "title": rec.get("title", full_grant["title"]),
                        "url": full_grant.get("url", "#"),
                        "source": rec.get("source", full_grant["source"]),
                        "is_active": full_grant["status"] == "open",
                        "total_fund_gbp": full_grant.get("total_fund_gbp"),
                        "closes_at": full_grant.get("closes_at"),
                        "score": full_grant.get("best_score", 0.0)
                    }
                    logger.info(f"Enriched grant card: {enriched_grant['title']} - funding={enriched_grant['total_fund_gbp']}, deadline={enriched_grant['closes_at']}")
                    grant_refs.append(enriched_grant)
                else:
                    # Fallback if grant not found in original list
                    logger.warning(f"Grant {grant_id} recommended by LLM but not found in original grants list")
                    grant_refs.append({
                        "grant_id": grant_id,
                        "title": rec.get("title", ""),
                        "url": "#",
                        "source": rec.get("source", ""),
                        "is_active": True,
                        "total_fund_gbp": None,
                        "closes_at": None,
                        "score": 0.0
                    })

            # Send grants
            yield f"data: {json.dumps({'type': 'grants', 'grants': grant_refs[:5]})}\n\n"

            # Done
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"data: {json.dumps({'type': 'token', 'content': 'I found relevant grants, but the AI layer failed while drafting the explanation. Try asking again or narrow your question.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# -----------------------------------------------------------------------------
# Startup Event
# -----------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """
    Run on application startup.

    Load existing documents into vector index.
    """
    logger.info("=" * 80)
    logger.info("Grant Discovery API - Starting")
    logger.info("=" * 80)
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Embeddings: text-embedding-3-small (OpenAI)")
    logger.info(f"LLM: GPT-4o-mini via OpenAI (lazy init)")
    logger.info(f"Docs: http://localhost:8000/docs")
    logger.info("=" * 80)

    # Load all grants and documents into vector index
    try:
        grants = grant_store.list_grants(limit=1000)
        logger.info(f"Found {len(grants)} grants in database")

        total_docs = 0
        for grant in grants:
            docs = doc_store.get_documents_for_grant(grant.id)
            if docs:
                vector_index.index_documents(docs)
                total_docs += len(docs)

        logger.info(f"Loaded {total_docs} documents into vector index")
    except Exception as e:
        logger.error(f"Error loading documents into vector index: {e}")

    logger.info("=" * 80)
