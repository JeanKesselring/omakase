"""
contact_scorer.py — Gemini-based contact quality scorer for Omakase Sales Bot.

Scores each shop's email (0–10) on how likely it is to reach the right
decision maker for a board game sales pitch.

Shops scoring < 5 are skipped from email batches.

Usage:
    python3 contact_scorer.py                          # score all unscored in DB
    python3 contact_scorer.py data/shop_batches/x.csv  # score shops in a CSV
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

import db

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

SCORE_THRESHOLD = 8

SYSTEM_PROMPT = """\
You are a B2B sales assistant for Omakase, a sushi-themed board game sold to retail shops.

You will receive a JSON list of shops, each with a name, type, website, and email.
For each shop, score the email address 0–10 on how likely it is to reach the right \
decision maker (owner, buyer, or store manager who can place wholesale orders).

Scoring guide:
- info@, contact@, shop@, hallo@, hello@ on the shop's own domain → 8–10
- A named personal email (e.g. john@shopname.de) at a small/independent shop → 7–9 \
  (owner likely reads this)
- Generic chain/parent company email (e.g. service@thalia.de for a franchise) → 2–4 \
  (will not reach the shop)
- noreply@, no-reply@, info@website.com, placeholder, obfuscated → 0–1

Respond with a JSON array, one object per shop, in the same order as the input.
Each object must have:
- "name": exactly as provided
- "score": integer 0–10
- "reason": one sentence explaining the score

Return ONLY the JSON array, no markdown fences or extra text.\
"""


def _call_gemini(shops: list[dict]) -> list[dict]:
    shop_summaries = [
        {
            "name":    s.get("name", ""),
            "type":    s.get("type", ""),
            "website": s.get("website", ""),
            "email":   s.get("email", ""),
        }
        for s in shops
    ]

    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": SYSTEM_PROMPT + "\n\nShops:\n" + json.dumps(shop_summaries, ensure_ascii=False)}],
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
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


def score_shops(shops: list[dict]) -> list[dict]:
    """
    Score a list of shop dicts. Returns the same list with
    'contact_score' and 'contact_score_reason' added to each.
    Falls back to score=5 on API error.
    """
    if not shops:
        return shops

    chunk_size = 20
    all_verdicts: list[dict] = []

    for i in range(0, len(shops), chunk_size):
        chunk = shops[i : i + chunk_size]
        try:
            verdicts = _call_gemini(chunk)
            all_verdicts.extend(verdicts)
        except Exception as e:
            print(f"  contact_scorer error on chunk {i // chunk_size + 1}: {e}")
            for s in chunk:
                all_verdicts.append({"name": s["name"], "score": 5, "reason": "API error — defaulting to 5"})

        if i + chunk_size < len(shops):
            time.sleep(1)

    verdict_map = {v["name"]: v for v in all_verdicts}

    for shop in shops:
        v = verdict_map.get(shop.get("name", ""), {})
        shop["contact_score"] = int(v.get("score", 5))
        shop["contact_score_reason"] = v.get("reason", "")

    return shops


def score_pending(conn) -> int:
    """Score all unscored shops in the DB. Writes results back. Returns count scored."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        print("contact_scorer: GEMINI_API_KEY not configured — skipping.")
        return 0

    rows = db.get_shops_needing_score(conn)
    if not rows:
        return 0

    shops = [dict(r) for r in rows]
    print(f"  Scoring {len(shops)} shop(s) for contact quality...")
    scored = score_shops(shops)

    for shop in scored:
        db.update_contact_score(conn, shop["id"], shop["contact_score"], shop["contact_score_reason"])
    conn.commit()

    low = sum(1 for s in scored if s["contact_score"] < SCORE_THRESHOLD)
    print(f"  Scored {len(scored)} shop(s). {low} flagged as low confidence (score < {SCORE_THRESHOLD}).")
    return len(scored)


if __name__ == "__main__":
    if not GEMINI_API_KEY or GEMINI_API_KEY == "your_gemini_api_key_here":
        print("Error: Set GEMINI_API_KEY in your .env file.")
        sys.exit(1)

    if len(sys.argv) > 1:
        # Score shops in a given CSV file
        path = Path(sys.argv[1])
        if not path.exists():
            print(f"File not found: {path}")
            sys.exit(1)

        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        rows = [r for r in rows if r.get("email")]
        print(f"Scoring {len(rows)} shop(s) from {path.name}...")
        scored = score_shops(rows)

        for s in scored:
            flag = " ← LOW" if s["contact_score"] < SCORE_THRESHOLD else ""
            print(f"  [{s['contact_score']:2d}] {s['name']} — {s['contact_score_reason']}{flag}")
    else:
        # Score all unscored shops in the DB
        conn = db.get_connection()
        n = score_pending(conn)
        conn.close()
        print(f"Scored {n} shop(s) in the database.")
