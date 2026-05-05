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
import smtplib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import dns.resolver

import db
from email_constructor import construct_email
from email_agent import send_email

BATCH_DIR = Path(__file__).parent / "data" / "shop_batches"
CONTACTED_DIR = Path(__file__).parent / "data" / "contacted"
BASEMAIL = Path(__file__).parent / "prompts" / "basemail.txt"
SALES_SHEET_EUR = Path(__file__).parent / "prompts" / "sales sheet (europe).pdf"
SALES_SHEET_DIR = Path(__file__).parent / "data" / "sales_sheets"

_COUNTRY_TO_PDF: dict[str, str] = {
    "Albania":        "all_albania.pdf",
    "Bulgaria":       "bgn_bulgaria.pdf",
    "Czech Republic": "czk_czech_rep.pdf",
    "Denmark":        "dkk_denmark.pdf",
    "Hungary":        "huf_hungary.pdf",
    "Iceland":        "isk_iceland.pdf",
    "Moldova":        "mdl_moldova.pdf",
    "Norway":         "nok_norway.pdf",
    "Poland":         "pln_poland.pdf",
    "Romania":        "ron_romania.pdf",
    "Sweden":         "sek_sweden.pdf",
    "Switzerland":    "chf_switzerland.pdf",
    "Turkey":         "try_turkey.pdf",
    "United Kingdom": "gbp_uk.pdf",
    "UK":             "gbp_uk.pdf",
}


def sales_sheet_for(country: str) -> Path:
    """Return the correct sales-sheet PDF for a given country."""
    name = _COUNTRY_TO_PDF.get(country)
    if name:
        return SALES_SHEET_DIR / name
    return SALES_SHEET_EUR

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

}


def _domain_is_dead(domain: str) -> bool:
    """Returns True only if DNS definitively says the domain doesn't exist."""
    try:
        dns.resolver.resolve(domain, "A", lifetime=5)
        return False
    except dns.resolver.NXDOMAIN:
        return True
    except Exception:
        return False  # timeout / no answer / network error = assume alive


def purge_dead_domains(conn) -> int:
    """Scan all pending shops via DNS in parallel, mark dead ones 'no email'. Returns count purged."""
    rows = conn.execute(
        "SELECT id, name, email FROM shops WHERE (status='' OR status IS NULL) AND email != ''"
    ).fetchall()

    domain_cache: dict[str, bool] = {}
    to_purge: list[tuple[int, str, str]] = []

    def check(row):
        domain = row["email"].split("@")[-1].lower()
        if domain not in domain_cache:
            domain_cache[domain] = _domain_is_dead(domain)
        return row, domain_cache[domain]

    print(f"Scanning {len(rows)} pending shops for dead domains...")
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(check, r): r for r in rows}
        for i, f in enumerate(as_completed(futures), 1):
            row, dead = f.result()
            if dead:
                to_purge.append((row["id"], row["name"], row["email"]))
            if i % 50 == 0:
                print(f"  {i}/{len(rows)} checked, {len(to_purge)} dead so far...")

    for shop_id, name, email in to_purge:
        db.update_status(conn, shop_id, "no email")
        print(f"  purged: {name} <{email}>")
    conn.commit()
    print(f"\nPurged {len(to_purge)} dead shops. {len(rows) - len(to_purge)} remain in queue.")
    return len(to_purge)


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


def _send_to_shops(shops: list[dict], conn, delay_seconds: float) -> int:
    """
    Core send loop shared by both DB and CSV pipelines.
    Updates status in DB (if conn provided) and returns count sent.
    """
    sent = 0
    for idx, shop in enumerate(shops):
        name  = shop["name"]
        email = (shop.get("email") or "").strip()
        shop_id = shop.get("id")

        print(f"[{idx + 1}/{len(shops)}] {name} <{email}> ... ", end="", flush=True)

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
                attachments=[str(sales_sheet_for(shop.get("country", "")))],
            )
            if conn and shop_id:
                db.update_status(conn, shop_id, "contacted")
                conn.commit()
            print("sent")
            sent += 1
        except smtplib.SMTPRecipientsRefused as e:
            print(f"bounced — {e}")
            if conn and shop_id:
                db.update_status(conn, shop_id, "no email")
                conn.commit()
        except (OSError, ValueError) as e:
            print(f"ERROR — {e}")

        if idx < len(shops) - 1:
            time.sleep(delay_seconds)

    return sent


def _run_db(top_k: int, delay_seconds: float) -> bool:
    """DB-first pipeline. Returns True if it found and processed pending shops."""
    conn = db.get_connection()
    pending_rows = db.get_pending_shops(conn)
    if not pending_rows:
        conn.close()
        return False

    shops = [dict(r) for r in pending_rows]
    targets = shops[:top_k]
    print(f"Sending emails to {len(targets)} shop(s)...\n")
    _send_to_shops(targets, conn, delay_seconds)
    conn.close()
    return True


def _run_csv(top_k: int, delay_seconds: float) -> None:
    """CSV fallback pipeline (used when DB has no pending shops)."""
    CONTACTED_DIR.mkdir(parents=True, exist_ok=True)

    path = pick_next_batch()
    if path is None:
        print("No pending batches found in shop_batches/.")
        return

    rows = load_batch(path)
    pending_rows = [
        row for row in rows
        if (row.get("status") or "").strip() not in FINAL_STATUSES
        and (row.get("email") or "").strip()
    ]

    print(f"Batch: {path.name}")
    targets = pending_rows[:top_k]
    print(f"Sending emails to {len(targets)} shop(s)...\n")

    for idx, shop in enumerate(targets):
        name  = shop["name"]
        email = (shop.get("email") or "").strip()
        row_index = rows.index(shop)

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
                attachments=[str(sales_sheet_for(shop.get("country", "")))],
            )
            rows[row_index]["status"] = "contacted"
            print("sent")
        except (OSError, ValueError) as e:
            print(f"ERROR — {e}")

        save_batch(path, rows)

        if idx < len(targets) - 1:
            time.sleep(delay_seconds)

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


def run(top_k: int = 50, delay_seconds: float = 2.0) -> None:
    """Pick pending shops from DB (or CSV fallback) and send outreach emails."""
    if not _run_db(top_k, delay_seconds):
        _run_csv(top_k, delay_seconds)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "purge":
        _conn = db.get_connection()
        purge_dead_domains(_conn)
        _conn.close()
    else:
        k = int(sys.argv[1]) if len(sys.argv) > 1 else 50
        run(top_k=k)
