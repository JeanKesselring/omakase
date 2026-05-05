"""
Response Tracker for Omakase Sales Bot

Connects to the info@omakasegame.com inbox via IMAP, finds replies to our shop outreach,
classifies each reply as positive or negative using Gemini, and updates shops.csv.
"""

import csv
import email
import imaplib
import os
from pathlib import Path

import google.generativeai as genai
import db

IMAP_HOST = "mail.infomaniak.com"
IMAP_PORT = 993
INBOX_EMAIL = "info@omakasegame.com"
IMAP_PASSWORD = os.environ.get("OMAKASE_EMAIL_PASSWORD")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = "gemini-3-flash-preview"

SHOPS_CSV = Path(__file__).parent / "data" / "shops.csv"
SHOP_FIELDS = ["name", "type", "city", "country", "website", "email", "phone", "instagram", "reason", "status"]

# Subject prefix our emails use — replies will start with "Re: " followed by this
SUBJECT_PREFIX = "Omakase at "


def load_shops() -> list[dict]:
    with open(SHOPS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_shops(rows: list[dict]) -> None:
    with open(SHOPS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SHOP_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def classify_response(reply_body: str) -> str:
    """
    Use Gemini to classify a shop's reply as 'positive response' or 'negative response'.

    Returns:
        'positive response' or 'negative response'
    """
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL)

    prompt = f"""You are analyzing a reply from a retail shop to a sales outreach email for Omakase, a card game.

Classify the reply as exactly one of:
- "positive response" — the shop is interested, wants more info, agrees to a call, places an order, or responds warmly
- "negative response" — the shop declines, is not interested, says they are not taking new products, or does not respond relevantly

Reply:
---
{reply_body}
---

Respond with only "positive response" or "negative response". Nothing else."""

    response = model.generate_content(prompt)
    classification = response.text.strip().lower()

    if "positive" in classification:
        return "positive response"
    return "negative response"


def extract_body(msg: email.message.Message) -> str:
    """Extract plain text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and part.get("Content-Disposition") is None:
                return part.get_payload(decode=True).decode(errors="replace")
    else:
        return msg.get_payload(decode=True).decode(errors="replace")
    return ""


def run() -> None:
    if not IMAP_PASSWORD:
        raise ValueError("IMAP password not set. Export OMAKASE_EMAIL_PASSWORD.")
    if not GEMINI_API_KEY:
        raise ValueError("Gemini API key not set. Export GEMINI_API_KEY.")

    # Build contacted lookup — prefer DB, fall back to CSV
    use_db = db.DB_PATH.exists()
    if use_db:
        conn = db.get_connection()
        db_rows = conn.execute(
            "SELECT id, name FROM shops WHERE status = 'contacted'"
        ).fetchall()
        contacted = {row["name"].lower(): row["id"] for row in db_rows}
    else:
        rows = load_shops()
        contacted = {
            row["name"].lower(): i
            for i, row in enumerate(rows)
            if row.get("status") == "contacted"
        }

    if not contacted:
        print("No contacted shops to check replies for.")
        return

    print(f"Connecting to {IMAP_HOST}...")
    with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
        imap.login(INBOX_EMAIL, IMAP_PASSWORD)
        imap.select("INBOX")

        _, message_ids = imap.search(None, f'SUBJECT "Re: {SUBJECT_PREFIX}"')
        ids = message_ids[0].split()
        print(f"Found {len(ids)} reply email(s) to check.\n")

        updates = 0
        for msg_id in ids:
            _, msg_data = imap.fetch(msg_id, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = msg.get("Subject", "")
            sender  = msg.get("From", "")

            if SUBJECT_PREFIX not in subject:
                continue
            shop_name_raw = subject.split(SUBJECT_PREFIX, 1)[1].rstrip("?").strip()
            shop_key = shop_name_raw.lower()

            if shop_key not in contacted:
                continue

            body           = extract_body(msg)
            classification = classify_response(body)

            if use_db:
                shop_id = contacted[shop_key]
                # Check current status before overwriting
                current = conn.execute(
                    "SELECT status FROM shops WHERE id = ?", (shop_id,)
                ).fetchone()
                if current and current["status"] in ("positive response", "negative response"):
                    continue
                db.update_status(conn, shop_id, classification)
                conn.commit()
            else:
                row_index = contacted[shop_key]
                if rows[row_index].get("status") in ("positive response", "negative response"):
                    continue
                rows[row_index]["status"] = classification

            print(f"  {shop_name_raw} ({sender}): {classification}")
            updates += 1

    if use_db:
        conn.close()
    elif updates:
        save_shops(rows)

    if updates:
        print(f"\n{updates} shop(s) updated.")
    else:
        print("No new replies to process.")


if __name__ == "__main__":
    run()
