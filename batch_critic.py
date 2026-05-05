"""
Batch Critic for Omakase Sales Bot

Takes a batch CSV and sends shop entries to Gemini to flag shops that
are unlikely to be good targets for selling Omakase (a sushi-themed board game).

Usage:
    python3 batch_critic.py <path_to_batch.csv>

Outputs a reviewed CSV with a "relevance" column added:
  - "relevant"   — likely a good fit
  - "irrelevant" — probably not a good target (with reason)

Irrelevant entries are removed from the batch and logged to stdout.
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
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

BATCH_FIELDS = ["name", "country", "city", "type", "address", "website", "email", "phone", "status"]

SYSTEM_PROMPT = """\
You are a sales targeting assistant for Omakase, a sushi-themed board game.

You will receive a JSON list of shops. For each shop, decide whether it is a \
relevant target for selling a sushi-themed board game. Good targets include:
- Board game shops / tabletop game stores
- Toy shops that carry games
- Gift shops / concept stores that might stock unique games
- Comic / hobby / nerd culture shops
- Japanese/Asian themed lifestyle or gift stores
- Bookstores with a games section

Bad targets (irrelevant) include:
- Sushi restaurants or food businesses
- Clothing / fashion stores with no game or gift angle
- Furniture stores
- Pure art galleries
- Unrelated service businesses (salons, gyms, etc.)

Respond with a JSON array of objects, one per shop, in the same order as the input. \
Each object must have:
- "name": the shop name (exactly as provided)
- "relevant": true or false
- "reason": a short reason (1 sentence) only if irrelevant, otherwise empty string

Return ONLY the JSON array, no markdown fences or extra text.\
"""


def load_batch(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows


def save_batch(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BATCH_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def call_gemini(shops: list[dict]) -> list[dict]:
    """Send a batch of shops to Gemini for relevance review."""
    shop_summaries = [
        {"name": s["name"], "type": s.get("type", ""), "website": s.get("website", "")}
        for s in shops
    ]

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": SYSTEM_PROMPT + "\n\nShops:\n" + json.dumps(shop_summaries)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096,
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

    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    # Strip markdown fences if Gemini wraps them anyway
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]

    return json.loads(text.strip())


def filter_irrelevant(rows: list[dict]) -> list[dict]:
    """Filter out irrelevant shops using Gemini. Returns only relevant rows."""
    if not rows:
        return rows

    print(f"  Reviewing {len(rows)} shops with Gemini...\n")

    chunk_size = 20
    all_verdicts = []

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        try:
            verdicts = call_gemini(chunk)
            all_verdicts.extend(verdicts)
        except Exception as e:
            print(f"  Gemini error on chunk {i // chunk_size + 1}: {e}")
            for shop in chunk:
                all_verdicts.append({"name": shop["name"], "relevant": True, "reason": ""})

        if i + chunk_size < len(rows):
            time.sleep(1)

    verdict_map = {v["name"]: v for v in all_verdicts}

    kept = []
    removed = []

    for row in rows:
        verdict = verdict_map.get(row["name"])
        if verdict and not verdict.get("relevant", True):
            removed.append((row["name"], verdict.get("reason", "")))
        else:
            kept.append(row)

    if removed:
        print(f"  Flagged {len(removed)} irrelevant shop(s):\n")
        for name, reason in removed:
            print(f"    ✗ {name} — {reason}")
        print()

    print(f"  Kept {len(kept)} / {len(rows)} shops.\n")
    return kept


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
