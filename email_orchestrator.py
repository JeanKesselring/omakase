"""
Email Orchestrator for Omakase Sales Bot

Takes a batch CSV file (produced by shop_finder_orchestrator.py),
sends a personalised email with the sales sheet to each shop that
has not yet been contacted, and updates the status column in that file.
"""

import csv
import sys
import time
from pathlib import Path

from email_constructor import construct_email
from email_agent import send_email

BASEMAIL = Path(__file__).parent / "prompts" / "basemail.txt"
SALES_SHEET = Path(__file__).parent / "prompts" / "sales sheet (europe).pdf"

BATCH_FIELDS = ["name", "country", "city", "type", "address", "website", "email", "phone", "status"]
FINAL_STATUSES = ("contacted", "positive response", "negative response")


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


def run(batch_file: str | Path, top_k: int = 50, delay_seconds: float = 2.0) -> None:
    """
    Send emails to shops in a batch file.

    Args:
        batch_file:    Path to a batch CSV file from shop_finder_orchestrator.py.
        top_k:         Max number of emails to send in this run.
        delay_seconds: Pause between sends to avoid SMTP throttling.
    """
    path = Path(batch_file)
    if not path.exists():
        print(f"File not found: {path}")
        return

    rows = load_batch(path)

    pending = [
        (i, row) for i, row in enumerate(rows)
        if (row.get("status") or "").strip() not in FINAL_STATUSES
        and (row.get("email") or "").strip()
    ]

    if not pending:
        print("No pending shops in this batch.")
        return

    targets = pending[:top_k]
    print(f"Sending emails to {len(targets)} shop(s) from {path.name}...\n")

    for idx, (row_index, shop) in enumerate(targets):
        name = shop["name"]
        email = shop["email"].strip()

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
        except (OSError, ValueError) as e:
            print(f"ERROR — {e}")

        save_batch(path, rows)

        if idx < len(targets) - 1:
            time.sleep(delay_seconds)

    print(f"\nDone. {path.name} updated.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python email_orchestrator.py <path_to_batch_file.csv> [top_k]")
        print("Example: python email_orchestrator.py data/shop_batches/vienna_graz.csv 10")
        sys.exit(1)

    batch_path = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    run(batch_file=batch_path, top_k=k)
