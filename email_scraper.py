"""
Email Scraper for Omakase Sales Bot

Reads shops.csv, scrapes each shop's website to find a contact email address,
and writes the results to scraped_shops.csv.
"""

import csv
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SHOPS_CSV = Path(__file__).parent / "data" / "shops.csv"
OUTPUT_CSV = Path(__file__).parent / "data" / "scraped_shops.csv"

SHOP_FIELDS = ["name", "type", "city", "country", "website", "email", "phone", "instagram", "reason", "status"]

# Common paths to try when looking for a contact page
CONTACT_PATHS = [
    "/contact", "/contact-us", "/contacts",
    "/kontakt",           # German
    "/contact.html", "/kontakt.html",
    "/about", "/impressum",
    "/info",
]

# Domains to ignore when extracting emails (common false positives)
IGNORED_EMAIL_DOMAINS = {
    "example.com", "sentry.io", "wixpress.com", "shopify.com",
    "squarespace.com", "wordpress.com", "googletagmanager.com",
    "schema.org", "w3.org",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def extract_emails_from_html(html: str) -> list[str]:
    """Extract all email addresses from raw HTML, filtering out noise."""
    # Also decode mailto: links
    soup = BeautifulSoup(html, "html.parser")
    found = set()

    # From mailto: href attributes
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.startswith("mailto:"):
            email = href[7:].split("?")[0].strip()
            if email:
                found.add(email.lower())

    # From raw text via regex
    for match in EMAIL_REGEX.finditer(soup.get_text()):
        found.add(match.group(0).lower())

    # Filter out noise
    return [
        e for e in found
        if not any(domain in e for domain in IGNORED_EMAIL_DOMAINS)
        and "." in e.split("@")[-1]
    ]


def rank_emails(emails: list[str], domain: str) -> list[str]:
    """
    Sort emails so the most likely contact address comes first.
    Prefers emails on the shop's own domain, then common prefixes.
    """
    preferred_prefixes = ("info", "contact", "shop", "hello", "mail", "office", "hallo")

    def score(email: str) -> int:
        local, host = email.split("@", 1)
        s = 0
        if domain and domain in host:
            s += 10
        if any(local.startswith(p) for p in preferred_prefixes):
            s += 5
        return s

    return sorted(emails, key=score, reverse=True)


def fetch(url: str, timeout: int = 8) -> str | None:
    """Fetch a URL and return the HTML, or None on failure."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if response.ok:
            return response.text
    except Exception:
        pass
    return None


def scrape_email(website: str) -> str | None:
    """
    Try to find a contact email for a shop by scraping its website.
    Checks the homepage first, then common contact page paths.
    """
    if not website or website.strip() in ("", "null"):
        return None

    website = website.strip().rstrip("/")
    parsed = urlparse(website)
    domain = parsed.netloc.replace("www.", "")

    pages_to_try = [website] + [urljoin(website, path) for path in CONTACT_PATHS]
    all_emails: list[str] = []

    for url in pages_to_try:
        html = fetch(url)
        if html:
            emails = extract_emails_from_html(html)
            all_emails.extend(emails)
        # Stop early if we already have a confident match on the shop's domain
        ranked = rank_emails(list(set(all_emails)), domain)
        if ranked and domain and domain in ranked[0]:
            return ranked[0]

    if all_emails:
        return rank_emails(list(set(all_emails)), domain)[0]

    return None


def last_scraped_name() -> str | None:
    """Return the name of the last shop in scraped_shops.csv, or None if the file is empty."""
    if not OUTPUT_CSV.exists() or OUTPUT_CSV.stat().st_size == 0:
        return None
    with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    return rows[-1].get("name", "").strip().lower()


def append_to_output(rows: list[dict]) -> None:
    """Append rows with a scraped email to scraped_shops.csv."""
    rows_with_email = [r for r in rows if r.get("scraped_email")]
    if not rows_with_email:
        return
    write_header = not OUTPUT_CSV.exists() or OUTPUT_CSV.stat().st_size == 0
    output_fields = SHOP_FIELDS + ["scraped_email"]
    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows_with_email)


def run() -> None:
    with open(SHOPS_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Find resume point: skip everything up to and including the last scraped shop
    resume_after = last_scraped_name()
    if resume_after:
        start_index = next(
            (i + 1 for i, r in enumerate(rows) if r.get("name", "").strip().lower() == resume_after),
            0,
        )
        print(f"Resuming from shop {start_index + 1} (after '{resume_after}').\n")
        rows = rows[start_index:]
    else:
        print("Starting fresh.\n")

    total = len(rows)
    print(f"Scraping emails for {total} remaining shops...\n")

    for i, row in enumerate(rows, 1):
        name = row.get("name", "")
        website = row.get("website", "")

        print(f"[{i}/{total}] {name} — {website or 'no website'} ... ", end="", flush=True)

        if not website or website.strip() in ("", "null"):
            print("skipped (no website)")
            row["scraped_email"] = ""
            time.sleep(0.5)
            continue

        scraped = scrape_email(website)
        row["scraped_email"] = scraped or ""

        if scraped:
            print(f"found: {scraped}")
            append_to_output([row])
        else:
            print("not found")

        time.sleep(1.0)

    found_count = sum(1 for r in rows if r.get("scraped_email"))
    print(f"\nDone. {found_count}/{total} shops had an email. Results appended to {OUTPUT_CSV}")


if __name__ == "__main__":
    run()
