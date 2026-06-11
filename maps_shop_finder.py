"""
Shop Finder for Omakase Sales Bot

Uses Gemini (no grounding) with three focused search passes per city to find
retail shops that could carry Omakase board games. No Google Search grounding
surcharge — relies on Gemini's training knowledge, filtered by the downstream
pipeline (website_verifier + email_scraper drop dead/wrong results).

Three passes cover distinct shop-type clusters for better recall:
  1. Game & hobby culture
  2. Japanese / Asian lifestyle & dining
  3. Gift, design & geek culture

Drop-in replacement for the Google Maps Places API version — same find_shops()
interface, so shop_finder_orchestrator.py works unchanged.
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

SEARCH_PASSES = [
    (
        "board game store, tabletop game shop, game cafe, hobby shop, comic book store, "
        "trading card shop, role-playing game store, puzzle store, miniature game shop, "
        "collectible card game store"
    ),
    (
        "anime shop, manga shop, Japanese pop culture store, Japanese gift shop, "
        "Asian lifestyle store, Japanese restaurant, omakase restaurant, sushi restaurant, "
        "Japanese grocery store, Asian import store, K-pop store"
    ),
    (
        "gift shop, concept store, design shop, toy store, novelty store, "
        "geek culture shop, nerd shop, science fiction store, fantasy shop, bookstore"
    ),
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
        f"List real, currently operating retail shops in {location} "
        f"that match any of these categories: {shop_types}.\n"
        "For each shop include its name, shop type, full street address, website URL, and phone number. "
        "Only include shops physically located in or very near that city. "
        "Aim for 35–45 results. Do not repeat the same shop twice."
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "response_mime_type": "application/json",
            "response_schema": _SHOP_SCHEMA,
        },
    }
    for attempt in range(3):
        try:
            resp = requests.post(
                GEMINI_URL,
                params={"key": GEMINI_API_KEY},
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            break
        except requests.exceptions.Timeout:
            if attempt == 2:
                raise
            print(f"  Gemini timeout (attempt {attempt + 1}/3), retrying...")
            time.sleep(5)
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
    passes_succeeded = 0

    for pass_num, shop_types in enumerate(SEARCH_PASSES, 1):
        print(f"  Pass {pass_num}/{len(SEARCH_PASSES)}: {shop_types[:60]}…")
        try:
            found = _search(location, shop_types)
            passes_succeeded += 1
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"  Gemini search error (pass {pass_num}): {e}")
            found = []

        new_in_pass = 0
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
            new_in_pass += 1

        print(f"    → {new_in_pass} new shops (total so far: {len(shops)})")
        if pass_num < len(SEARCH_PASSES):
            time.sleep(1.0)

    return {
        "shops": shops,
        "total": len(shops),
        "passes_succeeded": passes_succeeded,
        "location_queried": location,
        "notes": f"Results from Gemini (no grounding), {passes_succeeded}/{len(SEARCH_PASSES)} passes succeeded.",
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
