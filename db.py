"""
Database module for Omakase Sales Bot.

Single source of truth: data/omakase.db (SQLite).
All pipeline scripts import from here.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "omakase.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS shops (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT    NOT NULL,
    city                 TEXT    NOT NULL,
    country              TEXT    NOT NULL,
    type                 TEXT    DEFAULT '',
    address              TEXT    DEFAULT '',
    website              TEXT    DEFAULT '',
    email                TEXT    DEFAULT '',
    phone                TEXT    DEFAULT '',
    instagram            TEXT    DEFAULT '',
    reason               TEXT    DEFAULT '',
    status               TEXT    DEFAULT '',
    contact_score        INTEGER DEFAULT NULL,
    contact_score_reason TEXT    DEFAULT '',
    lat                  REAL,
    lng                  REAL,
    source               TEXT    DEFAULT 'csv',
    created_at           TEXT    DEFAULT (datetime('now')),
    updated_at           TEXT    DEFAULT (datetime('now')),
    UNIQUE(name, city)
);
CREATE INDEX IF NOT EXISTS idx_shops_status  ON shops(status);
CREATE INDEX IF NOT EXISTS idx_shops_country ON shops(country);
CREATE INDEX IF NOT EXISTS idx_shops_city    ON shops(city);
"""


def get_connection() -> sqlite3.Connection:
    """Return a connection with row_factory and WAL mode enabled."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    conn = get_connection()
    conn.executescript(_CREATE_TABLE)
    conn.commit()
    conn.close()


def upsert_shop(conn: sqlite3.Connection, shop: dict) -> str:
    """
    Insert a shop or update its fields if name+city already exists.
    Returns 'inserted', 'updated', or 'skipped'.
    """
    name = (shop.get("name") or "").strip()
    city = (shop.get("city") or "").strip()
    if not name or not city:
        return "skipped"

    conn.execute("""
        INSERT OR IGNORE INTO shops (name, city, country, type, address, website, email, phone, instagram, reason, status, source)
        VALUES (:name, :city, :country, :type, :address, :website, :email, :phone, :instagram, :reason, :status, :source)
    """, {
        "name":      name,
        "city":      city,
        "country":   (shop.get("country") or "").strip(),
        "type":      (shop.get("type") or "").strip(),
        "address":   (shop.get("address") or "").strip(),
        "website":   (shop.get("website") or "").strip(),
        "email":     (shop.get("email") or "").strip(),
        "phone":     (shop.get("phone") or "").strip(),
        "instagram": (shop.get("instagram") or "").strip(),
        "reason":    (shop.get("reason") or "").strip(),
        "status":    (shop.get("status") or "").strip(),
        "source":    (shop.get("source") or "csv").strip(),
    })

    if conn.execute("SELECT changes()").fetchone()[0] > 0:
        return "inserted"

    # Row already existed — update non-empty fields without overwriting status
    conn.execute("""
        UPDATE shops SET
            country   = CASE WHEN :country   != '' THEN :country   ELSE country   END,
            type      = CASE WHEN :type       != '' THEN :type      ELSE type      END,
            address   = CASE WHEN :address    != '' THEN :address   ELSE address   END,
            website   = CASE WHEN :website    != '' THEN :website   ELSE website   END,
            email     = CASE WHEN :email      != '' THEN :email     ELSE email     END,
            phone     = CASE WHEN :phone      != '' THEN :phone     ELSE phone     END,
            instagram = CASE WHEN :instagram  != '' THEN :instagram ELSE instagram END,
            reason    = CASE WHEN :reason     != '' THEN :reason    ELSE reason    END,
            updated_at = datetime('now')
        WHERE name = :name AND city = :city
    """, {
        "name": name, "city": city,
        "country": (shop.get("country") or "").strip(),
        "type":    (shop.get("type") or "").strip(),
        "address": (shop.get("address") or "").strip(),
        "website": (shop.get("website") or "").strip(),
        "email":   (shop.get("email") or "").strip(),
        "phone":   (shop.get("phone") or "").strip(),
        "instagram": (shop.get("instagram") or "").strip(),
        "reason":  (shop.get("reason") or "").strip(),
    })
    return "updated"


def update_status(conn: sqlite3.Connection, shop_id: int, status: str) -> None:
    conn.execute(
        "UPDATE shops SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, shop_id),
    )


def update_geocode(conn: sqlite3.Connection, shop_id: int, lat: float, lng: float) -> None:
    conn.execute(
        "UPDATE shops SET lat = ?, lng = ?, updated_at = datetime('now') WHERE id = ?",
        (lat, lng, shop_id),
    )


def update_contact_score(conn: sqlite3.Connection, shop_id: int, score: int, reason: str) -> None:
    conn.execute(
        "UPDATE shops SET contact_score = ?, contact_score_reason = ?, updated_at = datetime('now') WHERE id = ?",
        (score, reason, shop_id),
    )


def get_kpi_counts(conn: sqlite3.Connection) -> dict:
    row = conn.execute("""
        SELECT
            COUNT(*)                                                      AS total,
            SUM(CASE WHEN status = 'contacted'         THEN 1 ELSE 0 END) AS contacted,
            SUM(CASE WHEN status = 'positive response' THEN 1 ELSE 0 END) AS positive,
            SUM(CASE WHEN status = 'negative response' THEN 1 ELSE 0 END) AS negative,
            SUM(CASE WHEN status = 'low_confidence'    THEN 1 ELSE 0 END) AS low_confidence,
            SUM(CASE WHEN status = 'irrelevant'        THEN 1 ELSE 0 END) AS irrelevant,
            SUM(CASE WHEN status = '' OR status IS NULL
                      AND email != ''                  THEN 1 ELSE 0 END) AS pending
        FROM shops
    """).fetchone()
    return dict(row)


def get_all_shops(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM shops ORDER BY country, city, name"
    ).fetchall()


def get_pending_shops(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Shops that have an email, haven't been contacted, and aren't flagged low-confidence."""
    return conn.execute("""
        SELECT * FROM shops
        WHERE email != ''
          AND (status = '' OR status IS NULL)
          AND (contact_score IS NULL OR contact_score >= 5)
        ORDER BY country, city, name
    """).fetchall()


def get_shops_needing_geocode(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT * FROM shops
        WHERE lat IS NULL
          AND (address != '' OR (city != '' AND country != ''))
        ORDER BY id
    """).fetchall()


def get_shops_needing_score(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT * FROM shops
        WHERE contact_score IS NULL AND email != ''
        ORDER BY id
    """).fetchall()


def find_shop_by_name(conn: sqlite3.Connection, name: str, status_filter: str = "contacted") -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM shops WHERE LOWER(name) = LOWER(?) AND status = ? LIMIT 1",
        (name, status_filter),
    ).fetchone()
