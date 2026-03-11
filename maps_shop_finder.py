"""
Maps Shop Finder for Omakase Sales Bot

Uses the Google Maps Places API to find retail shops in a given city.
Returns results in the same format as shop_finder.py so it works
as a drop-in with shop_finder_orchestrator.py.
"""

import os
import time
import requests

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Search queries run for each city — each targets a different shop type
SEARCH_QUERIES = [
    "board game store",
    "game shop",
    "toy store",
    "Japanese store",
    "Japan shop",
    "hobby shop",
    "gift shop",
    "concept store",
]

DETAILS_FIELDS = "name,formatted_address,website,formatted_phone_number,url"


def text_search(query: str, location: str) -> list[dict]:
    """Run a Places Text Search and return raw place results."""
    params = {
        "query": f"{query} in {location}",
        "key": GOOGLE_MAPS_API_KEY,
    }
    response = requests.get(TEXT_SEARCH_URL, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data.get("results", [])


def place_details(place_id: str) -> dict:
    """Fetch additional details (website, phone) for a place."""
    params = {
        "place_id": place_id,
        "fields": DETAILS_FIELDS,
        "key": GOOGLE_MAPS_API_KEY,
    }
    response = requests.get(DETAILS_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json().get("result", {})


def parse_city_country(address: str, fallback_city: str, fallback_country: str) -> tuple[str, str]:
    """Best-effort city/country extraction from a formatted address."""
    parts = [p.strip() for p in address.split(",")]
    city = parts[-3] if len(parts) >= 3 else fallback_city
    country = parts[-1] if len(parts) >= 1 else fallback_country
    return city, country


def find_shops(country: str, city: str) -> dict:
    """
    Search Google Maps for shops that could carry Omakase in a given city.

    Args:
        country: Target country (e.g. "Austria").
        city:    Target city (e.g. "Vienna").

    Returns:
        Dict with a 'shops' list, matching the format used by shop_finder.py.
    """
    if not GOOGLE_MAPS_API_KEY:
        raise ValueError(
            "Google Maps API key not set. Export GOOGLE_MAPS_API_KEY as an environment variable."
        )

    location = f"{city}, {country}"
    seen_place_ids: set[str] = set()
    shops = []

    for query in SEARCH_QUERIES:
        results = text_search(query, location)
        time.sleep(0.3)  # stay within rate limits

        for place in results:
            place_id = place.get("place_id")
            if not place_id or place_id in seen_place_ids:
                continue
            seen_place_ids.add(place_id)

            details = place_details(place_id)
            time.sleep(0.2)

            address = place.get("formatted_address", "")
            parsed_city, parsed_country = parse_city_country(address, city, country)

            shops.append({
                "name": place.get("name", ""),
                "type": query,
                "city": parsed_city,
                "country": parsed_country,
                "address": address,
                "website": details.get("website") or None,
                "email": None,  # Maps API does not provide email; scraped separately
                "phone": details.get("formatted_phone_number") or None,
            })

    return {
        "shops": shops,
        "total": len(shops),
        "location_queried": location,
        "notes": f"Results sourced from Google Maps Places API across {len(SEARCH_QUERIES)} search queries.",
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
