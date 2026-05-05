"""
migrate.py — One-time CSV → SQLite importer for Omakase Sales Bot.

Idempotent: safe to run multiple times (deduplication via UNIQUE(name, city)).

Import order:
  1. data/contacted/*.csv  — coerce blank status → "contacted"
  2. data/shop_batches/*.csv — blank status = pending
  3. data/shops.csv         — richer schema (instagram, reason)
  4. data/scraped_shops.csv — prefer scraped_email if email blank

Usage:
    python3 migrate.py
"""

import csv
from pathlib import Path

import db

DATA = Path(__file__).parent / "data"


def import_batch_csv(conn, path: Path, default_status: str = "") -> tuple[int, int]:
    """Import a shop_batches or contacted CSV. Returns (inserted, updated)."""
    inserted = updated = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            status = (row.get("status") or "").strip() or default_status
            result = db.upsert_shop(conn, {**row, "status": status, "source": "csv"})
            if result == "inserted":
                inserted += 1
            elif result == "updated":
                updated += 1
    return inserted, updated


def import_shops_csv(conn, path: Path) -> tuple[int, int]:
    """Import shops.csv or scraped_shops.csv (wider schema)."""
    if not path.exists():
        return 0, 0
    inserted = updated = 0
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # scraped_shops.csv has a scraped_email column — prefer it
            if not row.get("email") and row.get("scraped_email"):
                row["email"] = row["scraped_email"]
            result = db.upsert_shop(conn, {**row, "source": path.name})
            if result == "inserted":
                inserted += 1
            elif result == "updated":
                updated += 1
    return inserted, updated


def run() -> None:
    db.init_db()
    conn = db.get_connection()

    total_inserted = total_updated = 0

    # 1. contacted/ — already emailed; blank status → "contacted"
    contacted_csvs = sorted((DATA / "contacted").glob("*.csv"))
    print(f"Importing {len(contacted_csvs)} contacted batch(es)...")
    for path in contacted_csvs:
        i, u = import_batch_csv(conn, path, default_status="contacted")
        total_inserted += i
        total_updated += u
        print(f"  {path.name}: +{i} inserted, {u} updated")

    # 2. shop_batches/ — pending shops
    batch_csvs = sorted((DATA / "shop_batches").glob("*.csv"))
    print(f"\nImporting {len(batch_csvs)} pending batch(es)...")
    for path in batch_csvs:
        i, u = import_batch_csv(conn, path, default_status="")
        total_inserted += i
        total_updated += u
        print(f"  {path.name}: +{i} inserted, {u} updated")

    # 3. shops.csv — manually curated list
    print("\nImporting shops.csv...")
    i, u = import_shops_csv(conn, DATA / "shops.csv")
    total_inserted += i
    total_updated += u
    print(f"  shops.csv: +{i} inserted, {u} updated")

    # 4. scraped_shops.csv
    print("\nImporting scraped_shops.csv...")
    i, u = import_shops_csv(conn, DATA / "scraped_shops.csv")
    total_inserted += i
    total_updated += u
    print(f"  scraped_shops.csv: +{i} inserted, {u} updated")

    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM shops").fetchone()[0]
    dupes = conn.execute(
        "SELECT COUNT(*) FROM (SELECT name, city FROM shops GROUP BY name, city HAVING COUNT(*) > 1)"
    ).fetchone()[0]

    conn.close()

    print(f"\n{'='*50}")
    print(f"Migration complete.")
    print(f"  Total rows in DB : {total}")
    print(f"  Inserted this run: {total_inserted}")
    print(f"  Updated this run : {total_updated}")
    print(f"  Duplicate rows   : {dupes}  ← should be 0")


if __name__ == "__main__":
    run()
