"""
website_verifier.py — Sanity-check shop websites before scraping email.

Fetches the homepage and asks Gemini whether it actually belongs to the
expected type of retail shop. Catches hallucinations (wrong domain, closed
shop, domain-for-sale pages) before we waste an email scrape or, worse,
pitch a pregnancy centre.

Falls back to True on any network/API error so it never silently drops
valid shops due to transient issues.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OmakaseBot/1.0)"}


def verify(website: str, shop_name: str, shop_type: str) -> bool:
    """Return True if the website looks like the expected retail shop.

    Fetches the homepage, sends the first 2 000 chars to Gemini, and expects
    a YES / NO answer. Returns True on any error (fail open).
    """
    if not GEMINI_API_KEY:
        return True

    try:
        resp = requests.get(website, timeout=10, headers=_HEADERS, allow_redirects=True)
        if resp.status_code >= 400:
            return False
        snippet = resp.text[:2000]
    except requests.RequestException:
        return True

    prompt = (
        f'We are looking for a retail shop named "{shop_name}" of type "{shop_type}".\n'
        f"Here is the start of its website content:\n\n{snippet}\n\n"
        "Does this website belong to the expected type of retail shop? "
        "Answer with exactly one word: YES or NO."
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 5},
    }

    try:
        r = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        answer = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().upper()
        return "YES" in answer
    except (requests.RequestException, KeyError, ValueError):
        return True
