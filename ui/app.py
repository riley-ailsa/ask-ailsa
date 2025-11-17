#!/usr/bin/env python3
"""
Ask Ailsa - AI-powered UK Research Funding Discovery
"""

import streamlit as st
import requests
import json
from typing import List, Dict, Iterable

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BACKEND_URL = "http://localhost:8000"
STREAM_ENDPOINT = f"{BACKEND_URL}/chat/stream"

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG & STYLING
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Ask Ailsa",
    page_icon="🔬",
    layout="wide",
)

st.markdown(
    """
    <style>
        /* Main header styling */
        .ask-ailsa-header {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 2rem;
            border-radius: 1rem;
            margin-bottom: 2rem;
            border: 1px solid rgba(148, 163, 184, 0.2);
        }
        .ask-ailsa-title {
            font-size: 2.5rem;
            font-weight: 700;
            color: #f1f5f9;
            margin: 0;
            margin-bottom: 0.5rem;
        }
        .ask-ailsa-subtitle {
            font-size: 1.1rem;
            color: #94a3b8;
            margin: 0;
        }

        /* Grant card styling */
        .grant-card {
            border: 1px solid rgba(148, 163, 184, 0.3);
            border-left: 4px solid #6366f1;
            border-radius: 0.75rem;
            padding: 1.25rem;
            margin: 1rem 0;
            background: rgba(30, 41, 59, 0.4);
            transition: all 0.2s;
        }
        .grant-card:hover {
            border-left-color: #818cf8;
            background: rgba(30, 41, 59, 0.6);
        }
        .grant-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #e2e8f0;
            margin: 0 0 0.5rem 0;
        }
        .grant-meta {
            font-size: 0.875rem;
            color: #94a3b8;
            margin: 0.25rem 0;
        }
        .grant-detail {
            font-size: 0.875rem;
            color: #cbd5e1;
            margin: 0.5rem 0;
        }
        .relevance-badge {
            display: inline-block;
            background: rgba(99, 102, 241, 0.2);
            color: #a5b4fc;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        /* Sample question buttons */
        .stButton button {
            width: 100%;
            text-align: left;
            background: rgba(30, 41, 59, 0.4);
            border: 1px solid rgba(148, 163, 184, 0.3);
            color: #cbd5e1;
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            transition: all 0.2s;
        }
        .stButton button:hover {
            background: rgba(30, 41, 59, 0.6);
            border-color: #6366f1;
        }

        /* Reduce padding in main container */
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }

        /* Chat message styling - reduce font sizes */
        .stChatMessage {
            font-size: 0.9rem;
            line-height: 1.5;
            padding: 1.5rem 1rem !important;
        }

        .stChatMessage p {
            font-size: 0.9rem;
            margin-bottom: 0.5rem;
            line-height: 1.7 !important;
            color: #cbd5e1 !important;
        }

        .stChatMessage h1 {
            font-size: 1.4rem;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
        }

        .stChatMessage h2 {
            font-size: 1.1rem;
            margin-top: 0.8rem;
            margin-bottom: 0.4rem;
        }

        .stChatMessage h3 {
            font-size: 1rem;
            margin-top: 1.5rem !important;
            margin-bottom: 0.75rem !important;
            padding-top: 0.5rem !important;
            color: #e2e8f0 !important;
        }

        .stChatMessage ul, .stChatMessage ol {
            font-size: 0.9rem;
            margin-left: 1.5rem !important;
            margin-bottom: 1rem !important;
        }

        .stChatMessage li {
            margin-bottom: 0.5rem !important;
            line-height: 1.6 !important;
            color: #cbd5e1 !important;
        }

        .stChatMessage code {
            font-size: 0.85rem;
        }

        .stChatMessage strong {
            font-weight: 600;
            color: #e2e8f0 !important;
        }

        /* Better spacing between elements in chat */
        .element-container {
            margin-bottom: 0.75rem !important;
        }

        /* Divider styling */
        hr {
            margin: 1.5rem 0 !important;
            border-color: rgba(148, 163, 184, 0.2) !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages: List[Dict] = [
        {
            "role": "assistant",
            "content": "Hi, I'm Ailsa 👋\n\nI can help you discover UK research funding from NIHR and Innovate UK. Ask me about specific grants, deadlines, or funding amounts, or try one of the examples below.",
            "grants": []
        }
    ]

if "pending_sample_question" not in st.session_state:
    st.session_state.pending_sample_question = None

# ─────────────────────────────────────────────────────────────
# BACKEND COMMUNICATION
# ─────────────────────────────────────────────────────────────

def ask_ailsa_stream(user_prompt: str) -> Iterable[Dict]:
    """
    Stream response from Ask Ailsa backend.
    Yields dictionaries with 'token', 'grants', 'error', or 'done' keys.
    """
    try:
        response = requests.post(
            STREAM_ENDPOINT,
            json={"message": user_prompt, "history": [], "active_only": True, "sources": None},
            stream=True,
            timeout=60,
        )
        response.raise_for_status()

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue

            data_str = line[6:]  # Remove "data: " prefix
            try:
                data = json.loads(data_str)
                yield data
            except json.JSONDecodeError:
                continue

    except requests.exceptions.RequestException as e:
        yield {"error": f"Failed to connect to Ailsa backend: {str(e)}"}


def render_grant_card(grant: Dict):
    """Render a single grant card with proper styling."""
    from datetime import datetime, timezone

    title = grant.get("title", "Untitled Grant")
    source = grant.get("source", "Unknown")

    # Handle source display
    if source == "innovate_uk":
        source_display = "Innovate UK"
    elif source == "nihr":
        source_display = "NIHR"
    else:
        source_display = source

    relevance = grant.get("score", 0.0)

    # Format funding amount
    funding = grant.get("total_fund_gbp", "Not specified")
    if funding and funding != "Not specified":
        if isinstance(funding, (int, float)):
            if funding >= 1_000_000:
                funding = f"£{funding/1_000_000:.1f}M"
            else:
                funding = f"£{funding:,.0f}"
        else:
            funding = str(funding)

    # Format deadline with urgency indicator
    deadline = grant.get("closes_at", "Not specified")
    urgency_emoji = ""
    if deadline and deadline != "Not specified":
        try:
            # Parse ISO format deadline
            deadline_dt = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            days_until = (deadline_dt - now).days

            # Format as readable date
            deadline = deadline_dt.strftime("%B %d, %Y")

            # Add urgency indicator
            if days_until < 0:
                urgency_emoji = " ⚠️ CLOSED"
            elif days_until <= 7:
                urgency_emoji = f" ⚠️ {days_until} days left"
            elif days_until <= 30:
                urgency_emoji = f" ({days_until} days)"
        except:
            pass  # Keep original deadline string if parsing fails

    url = grant.get("url", "#")

    st.markdown(
        f"""
        <div class="grant-card">
            <h4 class="grant-title">{title}</h4>
            <p class="grant-meta">
                <strong>{source_display}</strong> •
                <span class="relevance-badge">Relevance: {relevance:.3f}</span>
            </p>
            <p class="grant-detail">
                💰 <strong>Funding:</strong> {funding}<br>
                📅 <strong>Deadline:</strong> {deadline}{urgency_emoji}
            </p>
            <a href="{url}" target="_blank" style="color: #818cf8; text-decoration: none; font-size: 0.875rem;">
                View details →
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ailsa_response(response_text: str):
    """
    Render Ailsa's response with proper Streamlit formatting.
    Handles headers, paragraphs, lists, and emphasis.
    """
    if not response_text:
        return

    # Split into lines
    lines = response_text.split('\n')

    # Process line by line
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip completely empty lines
        if not line:
            i += 1
            continue

        # Main section header (##)
        if line.startswith('## '):
            header_text = line.replace('##', '').strip()
            st.markdown("")  # Add spacing
            st.markdown(f"### {header_text}")  # Render as h3 for better size
            st.markdown("")  # Add spacing after
            i += 1
            continue

        # Subsection header (###)
        if line.startswith('### '):
            subheader_text = line.replace('###', '').strip()
            st.markdown(f"**{subheader_text}**")
            i += 1
            continue

        # List item (bullet or numbered)
        if line.startswith(('- ', '* ')) or (len(line) > 0 and line[0].isdigit() and len(line) > 1 and line[1] in '.):'):
            # Collect consecutive list items
            list_block = []
            while i < len(lines):
                current_line = lines[i].strip()
                if not current_line:
                    break
                # Check if it's a list item
                is_bullet = current_line.startswith(('- ', '* '))
                is_numbered = len(current_line) > 0 and current_line[0].isdigit() and len(current_line) > 1 and current_line[1] in '.):'

                if is_bullet or is_numbered:
                    list_block.append(current_line)
                    i += 1
                else:
                    break

            # Render list block
            if list_block:
                st.markdown('\n'.join(list_block))
            continue

        # Regular paragraph - collect until empty line or special formatting
        paragraph = []
        while i < len(lines):
            current = lines[i].strip()

            # Stop at empty line or special formatting
            if not current:
                break
            if current.startswith(('#', '-', '*')):
                break
            if len(current) > 0 and current[0].isdigit() and len(current) > 1 and current[1] in '.):':
                break

            paragraph.append(current)
            i += 1

        # Render paragraph
        if paragraph:
            st.markdown(' '.join(paragraph))

    # Final spacing
    st.markdown("")


def handle_user_message(user_text: str):
    """Process user message and stream response with proper formatting."""
    # Add user message to history
    st.session_state.messages.append({
        "role": "user",
        "content": user_text,
        "grants": []
    })

    # Display user message
    with st.chat_message("user"):
        st.markdown(user_text)

    # Stream assistant response
    with st.chat_message("assistant"):
        full_response = ""
        grants_data = []

        # Container for streaming text
        text_placeholder = st.empty()

        # Stream the response
        for chunk in ask_ailsa_stream(user_text):
            if "error" in chunk:
                st.error(chunk["error"])
                full_response = f"❌ {chunk['error']}"
                break

            if "type" in chunk and chunk["type"] == "token":
                full_response += chunk.get("content", "")
                # Update placeholder with streaming text + cursor
                text_placeholder.markdown(full_response + " ●")

            if "type" in chunk and chunk["type"] == "grants":
                grants_data = chunk.get("grants", [])

            if "type" in chunk and chunk["type"] == "done":
                break

        # Clear the placeholder and render final formatted version
        text_placeholder.empty()

        # NOW render with proper formatting
        render_ailsa_response(full_response)

        # Render grant cards
        if grants_data:
            st.markdown("---")
            st.markdown("### 📋 Matched Grants")
            for grant in grants_data:
                render_grant_card(grant)

    # Save to history
    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "grants": grants_data
    })

# ─────────────────────────────────────────────────────────────
# LAYOUT
# ─────────────────────────────────────────────────────────────

# Sidebar
with st.sidebar:
    st.markdown("### About Ask Ailsa")
    st.markdown(
        """
        **Ask Ailsa** helps you discover UK research funding through conversational AI.

        - 🔍 Semantic search across NIHR & Innovate UK
        - 💬 Natural language queries
        - 📊 Relevance-ranked results
        - 🎯 Smart filtering by deadline, amount, eligibility
        """
    )

    st.markdown("---")
    st.markdown("### Tips")
    st.markdown(
        """
        - Be specific about your research area
        - Ask about deadlines or funding amounts
        - Request comparisons between grants
        - Follow up to refine results
        """
    )

    st.markdown("---")
    st.markdown("### Data Sources")
    st.markdown("🏥 NIHR Funding  \n💡 Innovate UK Competitions")

    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Chat cleared. How can I help you find funding?",
                "grants": []
            }
        ]
        st.rerun()

# Header
st.markdown(
    """
    <div class="ask-ailsa-header">
        <h1 class="ask-ailsa-title">🔬 Ask Ailsa</h1>
        <p class="ask-ailsa-subtitle">Your AI guide to UK research funding opportunities</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sample questions
st.markdown("#### Try asking:")
cols = st.columns(3)

sample_questions = [
    "Show me NIHR grants for clinical trials closing in the next 3 months",
    "Find Innovate UK competitions for AI and machine learning",
    "What funding is available for early-stage health technology research?",
    "Compare grant options for academic vs. commercial applicants",
    "Show me grants over £1M for medical device development",
    "What NIHR i4i programs are currently open?",
]

for i, question in enumerate(sample_questions):
    col = cols[i % 3]
    with col:
        if st.button(question, key=f"sample-{i}", use_container_width=True):
            st.session_state.pending_sample_question = question

st.markdown("---")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            # Use enhanced rendering for assistant messages
            render_ailsa_response(msg["content"])
        else:
            # Simple markdown for user messages
            st.markdown(msg["content"])

        # Render grants if this message has them
        if msg.get("grants"):
            st.divider()
            st.markdown("### 📋 Matched Grants")
            for grant in msg["grants"]:
                render_grant_card(grant)

# Handle pending sample question
if st.session_state.pending_sample_question:
    q = st.session_state.pending_sample_question
    st.session_state.pending_sample_question = None
    handle_user_message(q)
    st.rerun()

# Chat input
user_input = st.chat_input("Describe your project or ask about funding...")

if user_input:
    handle_user_message(user_input)
    st.rerun()
