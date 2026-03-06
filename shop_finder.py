"""
Shop Finder for Omakase Sales Bot

Uses Gemini Flash to find retail shops that could carry Omakase board games.
Returns structured JSON based on the prompt template in prompts/find_shops_prompt.txt.
"""

import os
import json
from pathlib import Path
import google.generativeai as genai


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-3-flash-preview"
PROMPT_FILE = Path(__file__).parent / "prompts" / "find_shops_prompt.txt"


def find_shops(country: str, city: str, filters: str = "none") -> dict:
    """
    Ask Gemini to find shops that could sell Omakase board games.

    Args:
        country:  Target country (e.g. "Switzerland", "France").
        city:     Target city (e.g. "Zurich", "Paris").
        filters:  Optional extra criteria (e.g. "English-speaking", "online shops only").

    Returns:
        Parsed JSON dict with a list of shops.
    """
    if not GEMINI_API_KEY:
        raise ValueError(
            "Gemini API key not set. Export GEMINI_API_KEY as an environment variable."
        )

    location = f"{city}, {country}"
    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
    prompt = prompt_template.replace("{location}", location).replace("{filters}", filters)

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL)

    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )

    result = json.loads(response.text)
    return result


def print_shops(data: dict) -> None:
    """Pretty-print the shop results to the terminal."""
    shops = data.get("shops", [])
    print(f"\nFound {data.get('total', len(shops))} shops in {data.get('location_queried', '')}\n")
    for i, shop in enumerate(shops, 1):
        print(f"{i}. {shop['name']} ({shop['type']})")
        print(f"   {shop['city']}, {shop['country']}")
        if shop.get("website"):
            print(f"   Website : {shop['website']}")
        if shop.get("email"):
            print(f"   Email   : {shop['email']}")
        if shop.get("phone"):
            print(f"   Phone   : {shop['phone']}")
        if shop.get("instagram"):
            print(f"   Instagram: {shop['instagram']}")
        print(f"   Why     : {shop['reason']}")
        print()
    if data.get("notes"):
        print(f"Notes: {data['notes']}")


if __name__ == "__main__":
    results = find_shops(
        country="France",
        city="Paris",
        filters="none",
    )
    print_shops(results)
    # Optionally save to file:
    # Path("shops_output.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
