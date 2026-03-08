"""
Shop Finder Orchestrator

Reads cities.csv, runs find_shops() for each city, and appends results to shops.csv.
Supports a top-k filter and automatically skips cities already present in shops.csv.
"""

import csv
import time
from pathlib import Path

from shop_finder import find_shops

CITIES_CSV = Path(__file__).parent / "data" / "cities.csv"
SHOPS_CSV = Path(__file__).parent / "data" / "shops.csv"

SHOP_FIELDS = ["name", "type", "city", "country", "website", "email", "phone", "instagram", "reason"]


def already_processed_cities() -> set[tuple[str, str]]:
    """Return a set of (city, country) tuples already present in shops.csv."""
    if not SHOPS_CSV.exists() or SHOPS_CSV.stat().st_size == 0:
        return set()
    with open(SHOPS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {
            (row["city"].strip().lower(), row["country"].strip().lower())
            for row in reader
            if row.get("city") and row.get("country")
        }


def load_cities(top_k: int | None = None) -> list[dict]:
    """
    Load unprocessed cities from cities.csv, skipping any city already in shops.csv.
    top_k applies to the remaining unprocessed cities.

    Args:
        top_k: If set, return at most the first N unprocessed cities.

    Returns:
        List of dicts with 'city' and 'country' keys.
    """
    processed = already_processed_cities()
    rows = []

    with open(CITIES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = row["City"].strip()
            country = row["Country"].strip()
            if (city.lower(), country.lower()) in processed:
                continue
            rows.append({"city": city, "country": country})
            if top_k is not None and len(rows) >= top_k:
                break

    return rows


def append_shops_to_csv(shops: list[dict]) -> None:
    """Append a list of shop dicts to shops.csv, creating the file with headers if needed."""
    write_header = not SHOPS_CSV.exists() or SHOPS_CSV.stat().st_size == 0

    with open(SHOPS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SHOP_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(shops)


def run(top_k: int = 5, delay_seconds: float = 1.5) -> None:
    """
    Main orchestration loop.

    Args:
        top_k:         Only process the first N cities in the CSV. Set to None to process all.
        delay_seconds: Pause between API calls to avoid rate limiting.
    """
    cities = load_cities(top_k=top_k)
    total = len(cities)
    print(f"Processing {total} cities...\n")

    for i, entry in enumerate(cities, 1):
        city, country = entry["city"], entry["country"]
        print(f"[{i}/{total}] {city}, {country} ... ", end="", flush=True)

        try:
            result = find_shops(country=country, city=city)
            shops = result.get("shops", [])
            append_shops_to_csv(shops)
            print(f"{len(shops)} shops found")
        except Exception as e:
            print(f"ERROR — {e}")

        if i < total:
            time.sleep(delay_seconds)

    print(f"\nDone. Results saved to {SHOPS_CSV}")


if __name__ == "__main__":
    run(top_k=20)
