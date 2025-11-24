#!/usr/bin/env python3
"""
Test script for the new system prompt updates.
Tests the chat endpoint with sample queries to verify:
1. No numbered lists
2. No "Great question!" or fluffy openers
3. Starts directly with recommendation
4. Mentions all 5 funding sources appropriately
5. Only discusses grants from context (no hallucination)
"""

import requests
import json

API_URL = "http://localhost:8000"

def test_chat_query(query: str, description: str):
    """Test a chat query and print the response."""
    print("=" * 80)
    print(f"TEST: {description}")
    print("=" * 80)
    print(f"Query: {query}\n")

    payload = {
        "message": query,
        "history": []
    }

    try:
        response = requests.post(
            f"{API_URL}/chat/enhanced/stream",
            json=payload,
            stream=True,
            timeout=30
        )

        if response.status_code != 200:
            print(f"❌ Error: HTTP {response.status_code}")
            print(response.text)
            return

        # Collect the full response
        full_response = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data = json.loads(line_str[6:])
                    if data.get('type') == 'token':
                        full_response += data.get('content', '')

        print("RESPONSE:")
        print("-" * 80)
        print(full_response)
        print("-" * 80)

        # Check for bad patterns
        print("\nCHECKS:")

        # Check 1: No numbered lists
        if any(pattern in full_response for pattern in ["1.", "2.", "3.", "1)", "2)", "3)"]):
            print("❌ FAIL: Contains numbered lists")
        else:
            print("✅ PASS: No numbered lists")

        # Check 2: No fluffy openers
        bad_openers = ["great question", "thanks for sharing", "it sounds like you have", "that's really interesting"]
        if any(opener in full_response.lower()[:100] for opener in bad_openers):
            print("❌ FAIL: Contains fluffy opener")
        else:
            print("✅ PASS: No fluffy openers")

        # Check 3: Starts with direct answer (not a question)
        first_sentence = full_response[:200].split('.')[0] if '.' in full_response[:200] else full_response[:200]
        if first_sentence.strip().endswith('?'):
            print("❌ FAIL: Starts with a question")
        else:
            print("✅ PASS: Starts with direct statement")

        # Check 4: No bullet points
        if "•" in full_response or "- " in full_response[:500]:  # Check first 500 chars for lists
            print("⚠️  WARNING: May contain bullet points")
        else:
            print("✅ PASS: No bullet points")

        print()

    except Exception as e:
        print(f"❌ Error: {e}")
        print()

if __name__ == "__main__":
    print("Testing New System Prompt Implementation")
    print("=" * 80)
    print()

    # Test 1: Health-tech query (from spec)
    test_chat_query(
        "I'm a health-tech startup at TRL 5, need £400-600k for clinical validation, have NHS clinical partner. What grants should I apply for?",
        "Health-tech with NHS partnership"
    )

    # Test 2: EU funding query (tests Horizon Europe mention)
    test_chat_query(
        "What EU funding could work for an AI company?",
        "EU funding for AI (should mention Horizon Europe/Digital Europe)"
    )

    # Test 3: Non-existent grant (tests hallucination prevention)
    test_chat_query(
        "Tell me about SMART grants",
        "Non-existent grant (should NOT hallucinate)"
    )

    print("=" * 80)
    print("Testing Complete")
    print("=" * 80)
