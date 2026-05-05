"""
Shop Finder Orchestrator

Iterates over cities.csv, finds shops via the Google Maps API,
scrapes each shop's website for an email address, and saves results
in batch CSV files of exactly 50 shops (with email) each.

Batch files are saved to data/shop_batches/ and named after the
cities they contain. A processed_cities.txt file tracks which cities
have already been searched so the script can safely resume.
"""

import csv
import re
import time
from pathlib import Path

import db
import contact_scorer
from batch_critic import filter_irrelevant
from maps_shop_finder import find_shops
from email_scraper import scrape_email
from website_verifier import verify as verify_website

CITIES_CSV = Path(__file__).parent / "data" / "cities.csv"
BATCH_DIR = Path(__file__).parent / "data" / "shop_batches"
PROCESSED_FILE = Path(__file__).parent / "data" / "processed_cities.txt"

BATCH_SIZE = 50
BATCH_FIELDS = ["name", "country", "city", "type", "address", "website", "email", "phone", "status"]


# ── helpers ──────────────────────────────────────────────────────────────────

def load_processed_cities() -> set[tuple[str, str]]:
    if not PROCESSED_FILE.exists():
        return set()
    lines = PROCESSED_FILE.read_text(encoding="utf-8").splitlines()
    result = set()
    for line in lines:
        if "," in line:
            city, country = line.split(",", 1)
            result.add((city.strip().lower(), country.strip().lower()))
    return result


def mark_city_processed(city: str, country: str) -> None:
    PROCESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{city},{country}\n")


def sanitize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def batch_filename(cities_in_batch: list[str]) -> Path:
    """Build a filename from the city names in the batch."""
    unique = list(dict.fromkeys(cities_in_batch))  # preserve order, deduplicate
    if len(unique) <= 4:
        name = "_".join(sanitize(c) for c in unique)
    else:
        name = f"{sanitize(unique[0])}_to_{sanitize(unique[-1])}"
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    # avoid collisions if a file with this name already exists
    path = BATCH_DIR / f"{name}.csv"
    counter = 2
    while path.exists():
        path = BATCH_DIR / f"{name}_{counter}.csv"
        counter += 1
    return path


def save_batch(shops: list[dict]) -> None:
    cities_in_batch = [s["city"] for s in shops]
    path = batch_filename(cities_in_batch)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BATCH_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(shops)
    print(f"\n  Batch saved → {path.name} ({len(shops)} shops)")


# ── main loop ────────────────────────────────────────────────────────────────

def run(top_k: int | None = None, cities: list[dict] | None = None) -> None:
    """
    Args:
        top_k:  Process at most this many cities from the queue. None = all.
        cities: If provided, process exactly these cities (skips the queue).
    """
    db.init_db()
    conn = db.get_connection()

    if cities is not None:
        pending_cities = cities
    else:
        processed = load_processed_cities()
        with open(CITIES_CSV, newline="", encoding="utf-8") as f:
            all_cities = [
                {"city": row["City"].strip(), "country": row["Country"].strip()}
                for row in csv.DictReader(f)
            ]
        pending_cities = [
            c for c in all_cities
            if (c["city"].lower(), c["country"].lower()) not in processed
        ]
        if top_k is not None:
            pending_cities = pending_cities[:top_k]

    print(f"{len(pending_cities)} cities to process.\n")

    buffer: list[dict] = []

    for ci, entry in enumerate(pending_cities, 1):
        city, country = entry["city"], entry["country"]
        print(f"[{ci}/{len(pending_cities)}] {city}, {country}")

        try:
            result = find_shops(country=country, city=city)
            shops_found = result.get("shops", [])
        except (OSError, ValueError, KeyError) as e:
            print(f"  Maps API error: {e}")
            mark_city_processed(city, country)
            continue

        print(f"  {len(shops_found)} places found via Maps — scraping emails...")

        for shop in shops_found:
            website = (shop.get("website") or "").strip()
            if not website:
                continue

            if not verify_website(website, shop.get("name", ""), shop.get("type", "")):
                print(f"    - {shop['name']} — skipped (wrong business at {website})")
                continue

            email = scrape_email(website)
            time.sleep(0.8)

            if not email:
                continue

            shop_dict = {
                "name":    shop.get("name", ""),
                "country": country,
                "city":    city,
                "type":    shop.get("type", ""),
                "address": shop.get("address", ""),
                "website": website,
                "email":   email,
                "phone":   shop.get("phone") or "",
                "status":  "",
            }

            # Score contact quality with Gemini; skip low-confidence contacts
            scored = contact_scorer.score_shops([shop_dict])[0]
            score = scored.get("contact_score", 5)
            reason = scored.get("contact_score_reason", "")
            if score < contact_scorer.SCORE_THRESHOLD:
                print(f"    - {shop['name']} — skipped (score {score}: {reason})")
                continue

            shop_dict["contact_score"] = score
            shop_dict["contact_score_reason"] = reason
            buffer.append(shop_dict)
            print(f"    + {shop['name']} — {email} (score {score})")

            if len(buffer) >= BATCH_SIZE:
                buffer = filter_irrelevant(buffer)
                save_batch(buffer)
                for s in buffer:
                    db.upsert_shop(conn, s)
                conn.commit()
                buffer = []

        mark_city_processed(city, country)

    # save any remaining shops that didn't fill a full batch
    if buffer:
        buffer = filter_irrelevant(buffer)
        save_batch(buffer)
        for s in buffer:
            db.upsert_shop(conn, s)
        conn.commit()

    conn.close()
    print("\nAll done.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--city",    help="Target a specific city")
    parser.add_argument("--country", help="Country for the target city")
    parser.add_argument("--top_k",   type=int, default=5, help="Number of cities to process (ignored if --city is set)")
    args = parser.parse_args()

    if args.city and args.country:
        # Run for a single specific city, bypassing the processed-cities queue
        run(cities=[{"city": args.city, "country": args.country}])
    else:
        run(top_k=args.top_k)
