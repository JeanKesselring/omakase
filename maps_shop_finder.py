"""
Shop Finder for Omakase Sales Bot

Uses Gemini with Google Search grounding to find retail shops in a given city.
Drop-in replacement for the Google Maps Places API version — same find_shops()
interface, so shop_finder_orchestrator.py works unchanged.

Two search passes per city cover different shop-type clusters for better recall.
Structured JSON output (response_schema) guarantees parseable results.
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

# Two passes so the model can focus and find more shops per type cluster
SEARCH_PASSES = [
    "board game store, game shop, tabletop cafe, hobby shop, comic shop, toy store",
    "gift shop, concept store, design shop, Japanese store, Asian lifestyle store, bookstore",
]

_SHOP_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "name":    {"type": "STRING"},
            "type":    {"type": "STRING"},
            "address": {"type": "STRING"},
            "website": {"type": "STRING"},
            "phone":   {"type": "STRING"},
        },
        "required": ["name", "type", "address"],
    },
}


def _search(location: str, shop_types: str) -> list[dict]:
    prompt = (
        f"Find real, currently operating retail shops in {location} "
        f"that sell or could stock: {shop_types}.\n"
        "For each shop include its name, shop type, full address, website URL, and phone number. "
        "Only include shops physically located in or very near that city. "
        "Aim for 15–25 results."
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192,
            "response_mime_type": "application/json",
            "response_schema": _SHOP_SCHEMA,
        },
    }
    resp = requests.post(
        GEMINI_URL,
        params={"key": GEMINI_API_KEY},
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    import json
    data = resp.json()
    if "candidates" not in data:
        print(f"  [maps_shop_finder] no candidates — response: {json.dumps(data)[:400]}")
        return []
    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    return json.loads(text)


def find_shops(country: str, city: str) -> dict:
    """
    Find shops that could carry Omakase in a given city.

    Args:
        country: Target country (e.g. "Austria").
        city:    Target city   (e.g. "Vienna").

    Returns:
        Dict with a 'shops' list matching the format used by shop_finder_orchestrator.py.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set in environment / .env file.")

    location = f"{city}, {country}"
    seen: set[str] = set()
    shops: list[dict] = []

    for shop_types in SEARCH_PASSES:
        try:
            found = _search(location, shop_types)
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"  Gemini search error ({shop_types[:30]}…): {e}")
            found = []

        for place in found:
            name = (place.get("name") or "").strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            shops.append({
                "name":    name,
                "type":    place.get("type") or "",
                "city":    city,
                "country": country,
                "address": place.get("address") or "",
                "website": place.get("website") or None,
                "email":   None,
                "phone":   place.get("phone") or None,
            })

        time.sleep(1.0)

    return {
        "shops": shops,
        "total": len(shops),
        "location_queried": location,
        "notes": f"Results from Gemini + Google Search ({len(SEARCH_PASSES)} passes).",
    }


def print_shops(data: dict) -> None:
    """Pretty-print shop results to the terminal."""
    shops = data.get("shops", [])
    print(f"\nFound {len(shops)} shops in {data.get('location_queried', '')}\n")
    for i, shop in enumerate(shops, 1):
        print(f"{i}. {shop['name']} ({shop['type']})")
        print(f"   {shop['city']}, {shop['country']}")
        if shop.get("website"):
            print(f"   Website: {shop['website']}")
        if shop.get("phone"):
            print(f"   Phone  : {shop['phone']}")
        print()


if __name__ == "__main__":
    results = find_shops(country="Austria", city="Vienna")
    print_shops(results)
