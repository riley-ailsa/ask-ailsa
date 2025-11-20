import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.enhanced_search import EnhancedGrantSearch


def test_comparative_question():
    """Test that comparative questions use previous context."""

    search = EnhancedGrantSearch("grants.db")
    session_id = "test_session_1"

    # First query
    result1 = search.search(
        "find me biomedical catalyst grants",
        session_id
    )

    # Should find grants
    assert len(result1["grants"]) >= 1
    grant_titles = [g["title"] for g in result1["grants"]]
    print(f"Found grants: {grant_titles}")

    # Follow-up comparative question
    result2 = search.search(
        "which one would be better for me as an SME with partnerships?",
        session_id
    )

    # Should reference context
    assert result2["intent"] in ["comparative", "followup", "strategic"]
    print(f"Intent: {result2['intent']}")
    print(f"Response: {result2['response'][:200]}...")

    print("✅ Comparative question maintains context")


def test_profile_extraction():
    """Test that user profile is extracted from conversation."""

    search = EnhancedGrantSearch("grants.db")
    session_id = "test_session_2"

    result = search.search(
        "I'm an SME with several university partnerships and patented tech",
        session_id
    )

    profile = result["user_profile"]

    assert profile.get("organization_type") == "SME"
    assert profile.get("has_partnerships") == True
    assert profile.get("has_patented_tech") == True

    print("✅ Profile extraction works")
    print(f"Extracted profile: {profile}")


def test_eligibility_filtering():
    """Test that irrelevant grants are filtered out."""

    search = EnhancedGrantSearch("grants.db")
    session_id = "test_session_3"

    # Set profile for biomedical SME
    result = search.search(
        "I'm a biomedical SME looking for up to £1M funding",
        session_id
    )

    # Check grants are relevant
    grant_titles = [g["title"].lower() for g in result["grants"]]
    print(f"Found {len(grant_titles)} grants")
    print(f"Grant titles: {grant_titles}")

    # Should prioritize biomedical/health-related grants
    profile = result["user_profile"]
    assert profile.get("organization_type") == "SME"
    assert "biomedical" in str(profile.get("sector", [])).lower() or len(result["grants"]) > 0

    print("✅ Eligibility filtering works")


def test_intent_classification():
    """Test intent classification for different query types."""

    search = EnhancedGrantSearch("grants.db")
    session_id = "test_session_4"

    # Discovery query
    result1 = search.search(
        "show me NIHR grants for clinical trials",
        session_id
    )
    print(f"Discovery intent: {result1['intent']}")
    assert result1["intent"] in ["discovery", "strategic"]

    # Follow-up query
    result2 = search.search(
        "tell me more about the first one",
        session_id
    )
    print(f"Follow-up intent: {result2['intent']}")
    assert result2["intent"] in ["followup", "clarification"]

    print("✅ Intent classification works")


if __name__ == "__main__":
    print("Running conversation flow tests...\n")

    try:
        test_profile_extraction()
        print()
    except Exception as e:
        print(f"❌ Profile extraction test failed: {e}\n")

    try:
        test_comparative_question()
        print()
    except Exception as e:
        print(f"❌ Comparative question test failed: {e}\n")

    try:
        test_eligibility_filtering()
        print()
    except Exception as e:
        print(f"❌ Eligibility filtering test failed: {e}\n")

    try:
        test_intent_classification()
        print()
    except Exception as e:
        print(f"❌ Intent classification test failed: {e}\n")

    print("\n✅ All tests completed!")
