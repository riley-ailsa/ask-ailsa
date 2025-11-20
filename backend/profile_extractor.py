from typing import Dict
from openai import OpenAI
import os
import json

class ProfileExtractor:
    """Extracts user profile information from conversation."""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def extract_from_message(self, message: str, existing_profile: Dict) -> Dict:
        """
        Extract profile information from user message.

        Returns updated profile dict with keys like:
        - organization_type: "SME" | "university" | "charity" | "NHS" | "large_company"
        - sector: ["biomedical", "digital_health", "medical_devices", etc.]
        - has_partnerships: bool
        - has_patented_tech: bool
        - team_size: "small" | "medium" | "large" | None
        - funding_range: {"min": int, "max": int}
        - project_stage: "early" | "development" | "commercialization"
        """

        prompt = f"""Extract user profile information from this message.

EXISTING PROFILE:
{json.dumps(existing_profile, indent=2)}

NEW MESSAGE:
"{message}"

Extract any new profile information and merge with existing. Return JSON with these fields:
{{
    "organization_type": "SME|university|charity|NHS|large_company|null",
    "sector": ["sector1", "sector2"],  // e.g. ["biomedical", "digital_health"]
    "has_partnerships": true|false|null,
    "has_patented_tech": true|false|null,
    "team_size": "small|medium|large|null",  // small=<10, medium=10-50, large=>50
    "funding_range": {{"min": number, "max": number}} | null,
    "project_stage": "early|development|commercialization|null",
    "other_notes": "any other relevant context"
}}

Only include fields that are mentioned or can be inferred. Set to null if not mentioned."""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        extracted = json.loads(response.choices[0].message.content)

        # Merge with existing profile
        merged = existing_profile.copy()
        for key, value in extracted.items():
            if value is not None:
                if key == "sector" and isinstance(value, list):
                    # Merge sector lists
                    existing_sectors = merged.get("sector", [])
                    merged["sector"] = list(set(existing_sectors + value))
                else:
                    merged[key] = value

        return merged
