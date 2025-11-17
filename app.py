#!/usr/bin/env python3
"""
Grant Discovery - Clean, Dark-Mode Chat Interface
"""

import streamlit as st
import requests
import re
from typing import List, Dict

# Configuration
API_URL = "http://localhost:8000"

# Page config
st.set_page_config(
    page_title="Grant Discovery",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Dark mode styling
st.markdown("""
<style>
/* Force dark mode */
.stApp, .main, body {
    background-color: #0F1116 !important;
    color: #E6E6E6 !important;
}

/* Remove default padding */
.block-container {
    padding-top: 2rem;
    padding-bottom: 8rem;
}

/* Style text input */
.stTextInput input {
    background-color: #1A1D23 !important;
    color: #E6E6E6 !important;
    border: 1px solid #2D3139 !important;
    border-radius: 8px !important;
    padding: 0.75rem !important;
}

/* Hide default Streamlit elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Fix input container */
.fixed-input {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    padding: 1rem 2rem;
    background: #0F1116;
    border-top: 1px solid #2D3139;
    z-index: 999;
}
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "input_key" not in st.session_state:
        st.session_state.input_key = 0


def render_chat_bubble(text: str, role: str = "assistant"):
    """
    Render a chat message bubble.

    Args:
        text: Message text (Markdown formatted)
        role: 'user' or 'assistant'
    """
    bg_color = "#1A1D23" if role == "assistant" else "#24272E"
    label = "**Advisor**" if role == "assistant" else "**You**"

    st.markdown(f"""
    <div style='padding: 1.2rem; margin-bottom: 1rem;
         background: {bg_color}; border-radius: 10px; color: #E6E6E6;
         line-height: 1.7; font-size: 0.95rem; border: 1px solid #2D3139;'>
        <div style='color: #9BA1A6; font-size: 0.85rem; margin-bottom: 0.5rem;'>{label}</div>
        {text}
    </div>
    """, unsafe_allow_html=True)


def render_grant_card(grant: Dict):
    """
    Render a grant reference card.

    Args:
        grant: Grant dictionary with title, source, score, url
    """
    source_label = "Innovate UK" if grant["source"] == "innovate_uk" else "NIHR"
    source_color = "#0066CC" if grant["source"] == "innovate_uk" else "#CC0066"

    st.markdown(f"""
    <div style='padding: 1rem; margin-bottom: 0.5rem;
         background: #1A1D23; border-radius: 8px; border-left: 3px solid {source_color};'>
        <div style='font-weight: 600; color: #E6E6E6; margin-bottom: 0.3rem;'>
            {grant['title']}
        </div>
        <div style='color: #9BA1A6; font-size: 0.85rem; margin-bottom: 0.5rem;'>
            {source_label} • Relevance: {grant['score']:.3f}
        </div>
        <a href="{grant['url']}" target="_blank" style='color: #4A9EFF; text-decoration: none; font-size: 0.9rem;'>
            View details →
        </a>
    </div>
    """, unsafe_allow_html=True)


def call_chat_api(user_message: str) -> Dict:
    """
    Call the chat API and return response.

    Args:
        user_message: User's message

    Returns:
        API response dict with 'answer' and 'grants'
    """
    try:
        # Build message history
        history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in st.session_state.messages
            if msg["role"] in ["user", "assistant"]
        ]

        response = requests.post(
            f"{API_URL}/chat",
            json={
                "message": user_message,
                "history": history,
                "active_only": True,
                "sources": None
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        return {
            "answer": "## Quick take\nRequest timed out. Please try again.",
            "grants": []
        }
    except requests.exceptions.RequestException as e:
        return {
            "answer": f"## Quick take\nAPI error: {str(e)}",
            "grants": []
        }


def main():
    """Main application."""
    init_session_state()

    # Header
    st.markdown("""
    <h1 style='margin-bottom: 0.3rem; color: #E6E6E6;'>Grant Discovery</h1>
    <p style='color: #9BA1A6; margin-bottom: 2rem;'>
        Opinionated advisor for Innovate UK and NIHR funding
    </p>
    """, unsafe_allow_html=True)

    # Main content area (with space for fixed input)
    main_container = st.container()

    with main_container:
        # Render chat history
        for msg in st.session_state.messages:
            if msg["role"] in ["user", "assistant"]:
                render_chat_bubble(msg["content"], msg["role"])

                # Show grants for assistant messages
                if msg["role"] == "assistant" and msg.get("grants"):
                    st.markdown("**Matched grants:**")
                    for grant in msg["grants"]:
                        render_grant_card(grant)
                    st.markdown("---")

    # Fixed input at bottom
    input_container = st.container()

    with input_container:
        st.markdown('<div class="fixed-input">', unsafe_allow_html=True)

        # Use columns for better input styling
        col1, col2 = st.columns([6, 1])

        with col1:
            user_input = st.text_input(
                "Message",
                key=f"user_input_{st.session_state.input_key}",
                placeholder="Describe your project or ask about funding...",
                label_visibility="collapsed"
            )

        with col2:
            send_button = st.button("Send", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # Handle user input
    if send_button and user_input:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "grants": []
        })

        # Show user message immediately
        with main_container:
            render_chat_bubble(user_input, "user")

        # Get assistant response
        with st.spinner("Analyzing grants..."):
            data = call_chat_api(user_input)

        reply = data.get("answer", "").strip()
        grants = data.get("grants", [])

        # Add assistant message
        st.session_state.messages.append({
            "role": "assistant",
            "content": reply,
            "grants": grants
        })

        # Increment input key to clear field
        st.session_state.input_key += 1

        # Rerun to show new messages
        st.rerun()


if __name__ == "__main__":
    main()
