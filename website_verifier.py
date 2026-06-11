"""
website_verifier.py — Sanity-check shop websites before scraping email.

Fetches the homepage and applies rule-based checks to filter out:
  - Parked / for-sale domains
  - HTTP 4xx / 5xx errors
  - Placeholder / coming-soon pages

Falls back to keeping the shop on any network error so valid shops are
never silently dropped due to transient issues.

No Gemini calls — all filtering is done locally on the HTTP response.
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OmakaseBot/1.0)"}

# Phrases that reliably indicate a parked or for-sale domain page.
_PARKED_SIGNALS = (
    "domain for sale",
    "buy this domain",
    "this domain is available",
    "this domain is parked",
    "domain name for sale",
    "register this domain",
    "buy this web address",
    "this site is for sale",
    "hugedomains.com",
    "sedo.com",
    "dan.com/buy",
    "afternic.com",
    "undeveloped.com",
    "this domain has expired",
    "domain has been registered",
    "web site coming soon",
    "coming soon",
    "under construction",
)


def _is_parked(html: str) -> bool:
    lower = html[:4000].lower()
    return any(sig in lower for sig in _PARKED_SIGNALS)


def verify(website: str, shop_name: str, shop_type: str) -> bool:
    """Return True if the website looks like a live retail shop.

    Rule-based: blocks parked domains and 4xx/5xx errors.
    Falls back to True on network errors (fail open).
    """
    try:
        resp = requests.get(website, timeout=10, headers=_HEADERS, allow_redirects=True)
        if resp.status_code >= 400:
            return False
        return not _is_parked(resp.text)
    except requests.RequestException:
        return True


def verify_batch(shops: list[dict]) -> list[dict]:
    """Filter a list of shops to those with live, non-parked websites.

    Each shop dict must have a 'website' key.
    Falls back to keeping shops whose websites can't be reached (fail open).
    """
    if not shops:
        return shops

    passed: list[dict] = []

    for shop in shops:
        website = (shop.get("website") or "").strip()
        if not website:
            continue
        try:
            resp = requests.get(website, timeout=10, headers=_HEADERS, allow_redirects=True)
            if resp.status_code >= 400:
                continue
            if _is_parked(resp.text):
                continue
            passed.append(shop)
        except requests.RequestException:
            passed.append(shop)

    return passed
