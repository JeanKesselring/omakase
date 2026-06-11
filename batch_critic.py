"""
Batch Critic for Omakase Sales Bot

Filters shops that are unlikely targets for selling Omakase (a sushi-themed
board game). Two-stage approach to minimise Gemini API calls:

  1. Rule-based pre-classifier: obvious relevant/irrelevant shops are decided
     instantly from their name + type keywords — no API call needed.
  2. Gemini fallback: only truly ambiguous shops (neither clearly relevant nor
     clearly irrelevant by keyword) are sent to the model.

Typically ~70-80 % of shops are classified by rules alone.

Usage:
    python3 batch_critic.py <path_to_batch.csv>

Outputs the same CSV with irrelevant shops removed.
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

BATCH_FIELDS = ["name", "country", "city", "type", "address", "website", "email", "phone", "status"]

# ── Rule-based classifier ─────────────────────────────────────────────────────

# Checked first: if any keyword matches → relevant, skip Gemini.
_RELEVANT_KEYWORDS = (
    "board game", "tabletop", "game shop", "game store", "game cafe", "game bar",
    "game room", "hobby shop", "hobby store",
    "comic", "trading card", "card game", "role-playing", "rpg", "miniature",
    "anime", "manga", "japanese pop", "japanese gift", "japanese store",
    "japanese restaurant", "japanese cuisine", "omakase", "sushi",
    "asian lifestyle", "asian gift", "asian store", "asian import",
    "k-pop", "kpop",
    "toy shop", "toy store",
    "gift shop", "gift store", "concept store", "novelty",
    "nerd", "geek", "sci-fi", "scifi", "science fiction", "fantasy shop",
    "puzzle", "collectible",
    "design shop", "design store",
    "bookstore", "book shop",
)

# Checked second: if any keyword matches → irrelevant, skip Gemini.
_IRRELEVANT_KEYWORDS = (
    "hair salon", "hair studio", "barbershop", "barber shop", "barber",
    "nail salon", "nail studio", "nail bar",
    "day spa", "beauty spa", "massage",
    "fitness center", "fitness studio", "crossfit", "yoga studio", "pilates",
    "dental clinic", "dentist", "orthodontist",
    "medical clinic", "medical center", "urgent care",
    "pharmacy", "drugstore", "chemist",
    "clothing store", "clothing boutique", "fashion store", "apparel store",
    "shoe store", "footwear store", "sneaker store",
    "furniture store", "home furnishing", "mattress store",
    "car dealership", "auto dealer", "auto repair", "car wash",
    "insurance agency", "financial advisor",
    "real estate",
    "laundromat", "dry cleaner",
    "hardware store",
    "grocery store", "supermarket", "food market",
    "tattoo", "piercing",
    "escape room",  # fun but unlikely to stock board games for resale
)


def _quick_classify(shop: dict) -> str:
    """Return 'relevant', 'irrelevant', or 'ambiguous' based on keywords alone."""
    combined = f"{shop.get('name', '')} {shop.get('type', '')}".lower()
    for kw in _RELEVANT_KEYWORDS:
        if kw in combined:
            return "relevant"
    for kw in _IRRELEVANT_KEYWORDS:
        if kw in combined:
            return "irrelevant"
    return "ambiguous"


# ── Gemini fallback ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a sales targeting assistant for Omakase, a sushi-themed board game.

You will receive a JSON list of shops. For each shop, decide whether it is a \
relevant target for selling a sushi-themed board game. Good targets include:
- Board game shops / tabletop game stores
- Toy shops that carry games
- Gift shops / concept stores that might stock unique games
- Comic / hobby / nerd culture shops
- Japanese/Asian themed lifestyle or gift stores
- Bookstores with a games section
- Anime shops, manga shops, Japanese pop culture stores
- Sushi restaurants, Japanese restaurants, omakase restaurants

Bad targets (irrelevant) include:
- Clothing / fashion stores with no game or gift angle
- Furniture stores
- Pure art galleries
- Unrelated service businesses (salons, gyms, clinics, etc.)

Respond with a JSON array of objects, one per shop, in the same order as the input. \
Each object must have:
- "name": the shop name (exactly as provided)
- "relevant": true or false
- "reason": a short reason (1 sentence) only if irrelevant, otherwise empty string

Return ONLY the JSON array, no markdown fences or extra text.\
"""


def _call_gemini(shops: list[dict]) -> list[dict]:
    shop_summaries = [
        {"name": s["name"], "type": s.get("type", ""), "website": s.get("website", "")}
        for s in shops
    ]
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": _SYSTEM_PROMPT + "\n\nShops:\n" + json.dumps(shop_summaries)}],
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
    }
    resp = requests.post(
        GEMINI_URL,
        params={"key": GEMINI_API_KEY},
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


def _gemini_filter(shops: list[dict]) -> list[dict]:
    """Send ambiguous shops to Gemini in chunks. Returns only relevant ones."""
    chunk_size = 40
    kept: list[dict] = []

    for i in range(0, len(shops), chunk_size):
        chunk = shops[i : i + chunk_size]
        try:
            verdicts = _call_gemini(chunk)
        except Exception as e:
            print(f"  Gemini error on chunk {i // chunk_size + 1}: {e}")
            kept.extend(chunk)
            continue

        verdict_map = {v["name"]: v for v in verdicts}
        for shop in chunk:
            v = verdict_map.get(shop["name"], {})
            if not v.get("relevant", True) is False:
                kept.append(shop)
            else:
                reason = v.get("reason", "")
                print(f"    ✗ {shop['name']} — {reason}")

        if i + chunk_size < len(shops):
            time.sleep(1)

    return kept


# ── Public API ────────────────────────────────────────────────────────────────

def load_batch(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_batch(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BATCH_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def filter_irrelevant(rows: list[dict]) -> list[dict]:
    """Filter out irrelevant shops. Returns only relevant rows."""
    if not rows:
        return rows

    auto_relevant: list[dict] = []
    auto_irrelevant: list[dict] = []
    ambiguous: list[dict] = []

    for row in rows:
        verdict = _quick_classify(row)
        if verdict == "relevant":
            auto_relevant.append(row)
        elif verdict == "irrelevant":
            auto_irrelevant.append(row)
        else:
            ambiguous.append(row)

    if auto_irrelevant:
        print(f"  Rule-filtered {len(auto_irrelevant)} irrelevant / "
              f"{len(auto_relevant)} auto-approved / "
              f"{len(ambiguous)} ambiguous → Gemini")

    if not ambiguous:
        print(f"  Kept {len(auto_relevant)} / {len(rows)} shops (no Gemini needed).\n")
        return auto_relevant

    print(f"  Reviewing {len(ambiguous)} ambiguous shop(s) with Gemini...\n")
    gemini_kept = _gemini_filter(ambiguous)

    result = auto_relevant + gemini_kept
    print(f"  Kept {len(result)} / {len(rows)} shops.\n")
    return result


def review_batch(path: Path) -> None:
    """Review a batch CSV and remove irrelevant shops."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        print("Error: Set GEMINI_API_KEY in your .env file.")
        sys.exit(1)

    rows = load_batch(path)
    if not rows:
        print("Empty CSV.")
        return

    kept = filter_irrelevant(rows)
    save_batch(path, kept)
    print(f"Updated {path.name}.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 batch_critic.py <path_to_batch.csv>")
        print("Example: python3 batch_critic.py data/shop_batches/antwerp.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    review_batch(csv_path)
