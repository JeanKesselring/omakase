"""
Email Orchestrator for Omakase Sales Bot

Reads shops.csv for status tracking and scraped_shops.csv for verified emails.
Only contacts shops that have a scraped email and have not been contacted yet.
Updates the 'status' column in shops.csv after each send.
"""

import csv
import time
from pathlib import Path

from email_constructor import construct_email
from email_agent import send_email

SHOPS_CSV = Path(__file__).parent / "data" / "shops.csv"
SCRAPED_CSV = Path(__file__).parent / "data" / "scraped_shops.csv"
BASEMAIL = Path(__file__).parent / "prompts" / "basemail.txt"
SALES_SHEET = Path(__file__).parent / "prompts" / "sales sheet (europe).pdf"

SHOP_FIELDS = ["name", "type", "city", "country", "website", "email", "phone", "instagram", "reason", "status"]


def load_shops() -> list[dict]:
    """Load all rows from shops.csv, adding a blank 'status' field if the column is missing."""
    with open(SHOPS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    for row in rows:
        if "status" not in row:
            row["status"] = ""

    return rows


def load_scraped_emails() -> dict[str, str]:
    """Return a dict of shop name (lowercase) -> scraped_email from scraped_shops.csv."""
    if not SCRAPED_CSV.exists():
        return {}
    with open(SCRAPED_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {
            row["name"].strip().lower(): row["scraped_email"].strip()
            for row in reader
            if row.get("scraped_email", "").strip()
        }


def save_shops(rows: list[dict]) -> None:
    """Write all rows back to shops.csv with the full SHOP_FIELDS header."""
    with open(SHOPS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SHOP_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run(top_k: int = 5, delay_seconds: float = 2.0) -> None:
    """
    Main orchestration loop.

    Args:
        top_k:         Maximum number of emails to send in this run.
        delay_seconds: Pause between sends to avoid SMTP throttling.
    """
    rows = load_shops()
    scraped_emails = load_scraped_emails()

    FINAL_STATUSES = ("contacted", "positive response", "negative response", "no email")

    # Only include shops that have a scraped email and haven't been contacted yet
    pending = []
    for i, row in enumerate(rows):
        if (row.get("status") or "").strip() in FINAL_STATUSES:
            continue
        scraped_email = scraped_emails.get(row["name"].strip().lower(), "")
        if not scraped_email:
            row["status"] = "no email"
            continue
        pending.append((i, row, scraped_email))

    save_shops(rows)  # persist any newly marked "no email" rows

    if not pending:
        print("No pending shops to contact.")
        return

    targets = pending[:top_k]
    print(f"Sending emails to {len(targets)} shop(s)...\n")

    for idx, (row_index, shop, email) in enumerate(targets):
        name = shop["name"]

        print(f"[{idx + 1}/{len(targets)}] {name} <{email}> ... ", end="", flush=True)

        try:
            email_data = construct_email(BASEMAIL, shop_name=name)
            send_email(
                to=email,
                subject=email_data["subject"],
                body=email_data["body"],
                attachments=[str(SALES_SHEET)],
            )
            rows[row_index]["status"] = "contacted"
            print("sent")
        except Exception as e:
            print(f"ERROR — {e}")

        save_shops(rows)

        if idx < len(targets) - 1:
            time.sleep(delay_seconds)

    print(f"\nDone. {SHOPS_CSV} updated.")


if __name__ == "__main__":
    run(top_k=100)
