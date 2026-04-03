"""
Email Orchestrator for Omakase Sales Bot

Automatically picks the next batch CSV from data/shop_batches/,
sends a personalised email with the sales sheet to each shop,
and moves the completed file to data/contacted/.

Usage:
    python3 email_orchestrator.py            # process the next batch
    python3 email_orchestrator.py [top_k]    # limit emails per run
"""

import csv
import re
import shutil
import sys
import time
from functools import lru_cache
from pathlib import Path

import dns.resolver
from batch_critic import filter_irrelevant, GEMINI_API_KEY
from email_constructor import construct_email
from email_agent import send_email

BATCH_DIR = Path(__file__).parent / "data" / "shop_batches"
CONTACTED_DIR = Path(__file__).parent / "data" / "contacted"
BASEMAIL = Path(__file__).parent / "prompts" / "basemail.txt"
SALES_SHEET = Path(__file__).parent / "prompts" / "sales sheet (europe).pdf"

BATCH_FIELDS = ["name", "country", "city", "type", "address", "website", "email", "phone", "status"]
FINAL_STATUSES = ("contacted", "positive response", "negative response")
VALID_EMAIL = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,15}$")

BLACKLISTED_DOMAINS = {
    "website.com", "example.com", "domain.com", "email.com",
    "test.com", "yourwebsite.com", "yourdomain.com",
    "sentry.io", "wixpress.com", "shopify.com",
    "squarespace.com", "wordpress.com",
}

BLACKLISTED_PREFIXES = (
    "noreply", "no-reply", "no_reply",
    "nospam", "nospamplease",
    "mailer-daemon", "postmaster",
)

PERSONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.de", "hotmail.com",
    "hotmail.de", "outlook.com", "aol.com", "gmx.de",
    "gmx.net", "web.de", "freenet.de", "t-online.de",
}


@lru_cache(maxsize=512)
def _has_mx_record(domain: str) -> bool:
    """Check if a domain has MX records (can receive email)."""
    try:
        dns.resolver.resolve(domain, "MX", lifetime=5)
        return True
    except Exception:
        return False


def is_valid_target_email(email: str) -> tuple[bool, str]:
    """Validate an email for B2B outreach. Returns (ok, reason)."""
    if not VALID_EMAIL.match(email):
        return False, "malformed"

    local, domain = email.rsplit("@", 1)

    if domain.lower() in BLACKLISTED_DOMAINS:
        return False, f"blacklisted domain ({domain})"

    if any(local.lower().startswith(p) for p in BLACKLISTED_PREFIXES):
        return False, f"blacklisted prefix ({local})"

    if domain.lower() in PERSONAL_DOMAINS:
        return False, f"personal email ({domain})"

    if not _has_mx_record(domain):
        return False, f"no MX record ({domain})"

    return True, ""


def load_batch(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if "status" not in row:
            row["status"] = ""
    return rows


def save_batch(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=BATCH_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def pick_next_batch() -> Path | None:
    """Return the first CSV in shop_batches/ that still has pending shops, or None."""
    csvs = sorted(BATCH_DIR.glob("*.csv"))
    for csv_path in csvs:
        rows = load_batch(csv_path)
        pending = [
            row for row in rows
            if (row.get("status") or "").strip() not in FINAL_STATUSES
            and (row.get("email") or "").strip()
        ]
        if pending:
            return csv_path
    return None


def run(top_k: int = 50, delay_seconds: float = 2.0) -> None:
    """
    Pick the next batch and send emails to all pending shops in it.

    Args:
        top_k:         Max number of emails to send in this run.
        delay_seconds: Pause between sends to avoid SMTP throttling.
    """
    CONTACTED_DIR.mkdir(parents=True, exist_ok=True)

    path = pick_next_batch()
    if path is None:
        print("No pending batches found in shop_batches/.")
        return

    rows = load_batch(path)

    pending = [
        (i, row) for i, row in enumerate(rows)
        if (row.get("status") or "").strip() not in FINAL_STATUSES
        and (row.get("email") or "").strip()
    ]

    targets = pending[:top_k]
    print(f"Batch: {path.name}")
    print(f"Sending emails to {len(targets)} shop(s)...\n")

    for idx, (row_index, shop) in enumerate(targets):
        name = shop["name"]
        email = shop["email"].strip()

        print(f"[{idx + 1}/{len(targets)}] {name} <{email}> ... ", end="", flush=True)

        ok, reason = is_valid_target_email(email)
        if not ok:
            print(f"skipped ({reason})")
            continue

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
        except (OSError, ValueError) as e:
            print(f"ERROR — {e}")

        save_batch(path, rows)

        if idx < len(targets) - 1:
            time.sleep(delay_seconds)

    # Check if all shops in this batch are now done
    remaining = [
        row for row in rows
        if (row.get("status") or "").strip() not in FINAL_STATUSES
        and (row.get("email") or "").strip()
    ]

    if not remaining:
        dest = CONTACTED_DIR / path.name
        shutil.move(str(path), str(dest))
        print(f"\nAll done. Moved {path.name} -> data/contacted/")
    else:
        print(f"\nDone. {len(remaining)} shop(s) still pending in {path.name}.")


if __name__ == "__main__":
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    run(top_k=k)
