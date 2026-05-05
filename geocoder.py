"""
geocoder.py — Lazy geocoding for Omakase Sales Bot.

Uses the Google Maps Geocoding API (same key as Places API).
Results are cached permanently in the SQLite DB.

Usage:
    python3 geocoder.py [max_batch]   # geocode up to N shops (default 100)
"""

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

import db

load_dotenv()

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def geocode_address(address: str, api_key: str) -> tuple[float, float] | None:
    """Call the Geocoding API. Returns (lat, lng) or None on failure."""
    try:
        resp = requests.get(
            GEOCODE_URL,
            params={"address": address, "key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            loc = results[0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    except Exception:
        pass
    return None


def geocode_pending(conn, api_key: str, max_batch: int = 100) -> int:
    """
    Geocode up to max_batch shops with missing lat/lng.
    Commits after each shop so progress survives interruption.
    Returns the number of shops geocoded.
    """
    shops = db.get_shops_needing_geocode(conn)[:max_batch]
    geocoded = 0

    for shop in shops:
        # Prefer full address; fall back to "city, country"
        address = shop["address"] or f"{shop['city']}, {shop['country']}"
        coords = geocode_address(address, api_key)

        if coords:
            db.update_geocode(conn, shop["id"], coords[0], coords[1])
            conn.commit()
            geocoded += 1

        time.sleep(0.1)  # stay within rate limits

    return geocoded


def ensure_geocoded(conn, api_key: str, max_batch: int = 200) -> None:
    """Called by dashboard before rendering the map."""
    pending = conn.execute(
        "SELECT COUNT(*) FROM shops WHERE lat IS NULL AND (address != '' OR (city != '' AND country != ''))"
    ).fetchone()[0]

    if pending == 0:
        return

    print(f"Geocoding {min(pending, max_batch)} shop(s)...")
    n = geocode_pending(conn, api_key, max_batch)
    print(f"  Geocoded {n} shop(s).")


if __name__ == "__main__":
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Error: GOOGLE_MAPS_API_KEY not set in .env")
        sys.exit(1)

    max_b = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    conn = db.get_connection()
    n = geocode_pending(conn, api_key, max_batch=max_b)
    conn.close()
    print(f"Geocoded {n} shop(s).")
