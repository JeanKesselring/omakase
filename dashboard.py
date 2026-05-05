"""
dashboard.py — Omakase Sales Dashboard

Run with:
    .venv/bin/streamlit run dashboard.py
"""

import csv
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import db

load_dotenv()

HERE        = Path(__file__).parent
PYTHON      = sys.executable
CITIES_CSV  = HERE / "data" / "cities.csv"
PROCESSED   = HERE / "data" / "processed_cities.txt"

STATUS_LABELS = {
    "contacted":         "Contacted",
    "positive response": "Positive Response",
    "negative response": "Negative Response",
    "low_confidence":    "Low Confidence",
    "irrelevant":        "Irrelevant",
    "no email":          "No Email",
    "":                  "Pending",
}

st.set_page_config(page_title="Omakase Sales Dashboard", page_icon="🍣", layout="wide")


# ── cached loaders ────────────────────────────────────────────────────────────

@st.cache_resource
def get_conn():
    return db.get_connection()


@st.cache_data
def load_cities() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    with open(CITIES_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            result.setdefault(row["Country"].strip(), []).append(row["City"].strip())
    return {k: sorted(v) for k, v in sorted(result.items())}


def load_processed() -> set[tuple[str, str]]:
    if not PROCESSED.exists():
        return set()
    out = set()
    for line in PROCESSED.read_text(encoding="utf-8").splitlines():
        if "," in line:
            city, country = line.split(",", 1)
            out.add((city.strip().lower(), country.strip().lower()))
    return out


def load_data(conn) -> pd.DataFrame:
    rows = db.get_all_shops(conn)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame([dict(r) for r in rows])
    df["status"] = df["status"].fillna("")
    df["status_label"] = df["status"].map(STATUS_LABELS).fillna(df["status"])
    return df


# ── helpers ───────────────────────────────────────────────────────────────────

def stream_script(script: str, args: list[str] = []):
    proc = subprocess.Popen(
        [PYTHON, "-u", str(HERE / script)] + args,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, cwd=str(HERE),
    )
    for line in proc.stdout:
        yield line.rstrip()
    proc.wait()
    yield proc.returncode


def run_panel(script: str, args: list[str], log_slot, success_msg: str) -> int:
    lines = []
    returncode = None
    for item in stream_script(script, args):
        if isinstance(item, int):
            returncode = item
        else:
            lines.append(item)
            log_slot.code("\n".join(lines[-60:]))
    if returncode == 0:
        st.success(success_msg)
    else:
        st.error("Script exited with an error — see output above.")
    return returncode


def city_stats(conn, cities_by_country: dict) -> pd.DataFrame:
    """Build a per-city status table merging cities.csv + processed list + DB counts."""
    processed = load_processed()

    db_rows = conn.execute("""
        SELECT city, country,
               COUNT(*) AS total_shops,
               SUM(CASE WHEN status = 'contacted'         THEN 1 ELSE 0 END) AS contacted,
               SUM(CASE WHEN status = 'positive response' THEN 1 ELSE 0 END) AS positive,
               SUM(CASE WHEN status = ''  OR status IS NULL THEN 1 ELSE 0 END) AS pending,
               SUM(CASE WHEN status = 'irrelevant'        THEN 1 ELSE 0 END) AS irrelevant
        FROM shops
        GROUP BY LOWER(city), LOWER(country)
    """).fetchall()
    db_map = {(r["city"].lower(), r["country"].lower()): dict(r) for r in db_rows}

    rows = []
    for country, cities in cities_by_country.items():
        for city in cities:
            key = (city.lower(), country.lower())
            searched = key in processed
            db = db_map.get(key, {})
            rows.append({
                "Country":      country,
                "City":         city,
                "Searched":     "✅" if searched else "—",
                "Shops in DB":  db.get("total_shops", 0),
                "Contacted":    db.get("contacted", 0),
                "Positive":     db.get("positive", 0),
                "Pending":      db.get("pending", 0),
                "Irrelevant":   db.get("irrelevant", 0),
            })
    return pd.DataFrame(rows)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    st.title("🍣 Omakase Sales Dashboard")

    conn            = get_conn()
    cities_by_country = load_cities()

    tab_overview, tab_find, tab_email, tab_inspect = st.tabs([
        "Overview", "Find Shops", "Send Emails", "Inspect Data"
    ])

    # ── Overview ──────────────────────────────────────────────────────────────
    with tab_overview:
        kpis = db.get_kpi_counts(conn)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Shops",        kpis.get("total", 0))
        c2.metric("Contacted",          kpis.get("contacted", 0))
        c3.metric("Positive Responses", kpis.get("positive", 0))
        c4.metric("Pending",            kpis.get("pending", 0))
        c5.metric("Low Confidence",     kpis.get("low_confidence", 0))

        st.divider()

        df = load_data(conn)
        if df.empty:
            st.warning("No data found. Run `python migrate.py` first.")
            return

        with st.expander("Filters", expanded=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                f_countries = st.multiselect("Country", options=sorted(df["country"].dropna().unique()))
            with col2:
                f_statuses  = st.multiselect("Status",  options=sorted(df["status_label"].dropna().unique()))
            with col3:
                f_types     = st.multiselect("Shop type", options=sorted(df["type"].dropna().unique()))

        filtered = df.copy()
        if f_countries: filtered = filtered[filtered["country"].isin(f_countries)]
        if f_statuses:  filtered = filtered[filtered["status_label"].isin(f_statuses)]
        if f_types:     filtered = filtered[filtered["type"].isin(f_types)]

        st.caption(f"Showing {len(filtered):,} of {len(df):,} shops")

        display_cols = ["name", "city", "country", "type", "status_label", "email", "website", "contact_score"]
        display_cols = [c for c in display_cols if c in filtered.columns]
        st.dataframe(
            filtered[display_cols].rename(columns={"status_label": "status"}),
            use_container_width=True, hide_index=True,
        )

        if st.button("Refresh data"):
            st.cache_data.clear()
            st.rerun()

    # ── Find Shops ────────────────────────────────────────────────────────────
    with tab_find:
        st.subheader("City status")
        stats_df = city_stats(conn, cities_by_country)

        # Summary chips
        n_searched = (stats_df["Searched"] == "✅").sum()
        n_total    = len(stats_df)
        st.caption(f"{n_searched} of {n_total} cities searched")

        # Filter to make it easy to find unsearched cities
        show_filter = st.radio(
            "Show", ["All cities", "Not yet searched", "Already searched"],
            horizontal=True,
        )
        display_stats = stats_df.copy()
        if show_filter == "Not yet searched":
            display_stats = display_stats[display_stats["Searched"] == "—"]
        elif show_filter == "Already searched":
            display_stats = display_stats[display_stats["Searched"] == "✅"]

        st.dataframe(display_stats, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Run shop finder")

        mode = st.radio("Mode", ["Single city", "Batch (multiple cities)"], horizontal=True)

        if mode == "Single city":
            col_country, col_city = st.columns(2)
            with col_country:
                country = st.selectbox("Country", list(cities_by_country.keys()))
            with col_city:
                city = st.selectbox("City", cities_by_country.get(country, []))
            selected_cities = [{"city": city, "country": country}]
        else:
            country_b = st.selectbox("Country", list(cities_by_country.keys()), key="batch_country")
            all_cities = cities_by_country.get(country_b, [])
            processed  = load_processed()
            unsearched = [c for c in all_cities if (c.lower(), country_b.lower()) not in processed]

            chosen = st.multiselect(
                f"Cities ({len(unsearched)} not yet searched)",
                options=all_cities,
                default=unsearched[:5],
                format_func=lambda c: f"{c} {'✅' if (c.lower(), country_b.lower()) in processed else ''}",
            )
            selected_cities = [{"city": c, "country": country_b} for c in chosen]

        log_area = st.empty()

        if st.button("Find shops", type="primary", use_container_width=True, disabled=not selected_cities):
            for entry in selected_cities:
                st.write(f"**Searching {entry['city']}, {entry['country']}...**")
                log_area = st.empty()
                run_panel(
                    "shop_finder_orchestrator.py",
                    ["--city", entry["city"], "--country", entry["country"]],
                    log_area,
                    f"Done — {entry['city']}",
                )
            st.success(f"Finished searching {len(selected_cities)} city/cities.")
            st.cache_data.clear()
            st.rerun()

    # ── Send Emails ───────────────────────────────────────────────────────────
    with tab_email:
        st.subheader("Outreach status by city")

        stats_df2 = city_stats(conn, cities_by_country)
        # Only show cities that have at least one shop in DB
        stats_with_shops = stats_df2[stats_df2["Shops in DB"] > 0].copy()

        e_filter = st.radio(
            "Show", ["All", "Has pending shops", "Fully contacted"],
            horizontal=True, key="email_filter",
        )
        if e_filter == "Has pending shops":
            stats_with_shops = stats_with_shops[stats_with_shops["Pending"] > 0]
        elif e_filter == "Fully contacted":
            stats_with_shops = stats_with_shops[
                (stats_with_shops["Contacted"] > 0) & (stats_with_shops["Pending"] == 0)
            ]

        st.dataframe(stats_with_shops, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Send outreach emails")

        col_n, col_check = st.columns([1, 1])
        with col_n:
            n_emails = st.number_input("Emails to send", min_value=1, max_value=200, value=50)
        with col_check:
            st.write(""); st.write("")
            check_replies = st.checkbox("Also scan inbox for replies afterwards", value=True)

        log_area = st.empty()

        if st.button("Send emails", type="primary", use_container_width=True):
            rc = run_panel("email_orchestrator.py", [str(n_emails)], log_area, f"Sent up to {n_emails} emails.")
            if rc == 0 and check_replies:
                st.divider()
                st.write("**Scanning inbox for replies...**")
                run_panel("response_tracker.py", [], st.empty(), "Inbox scan complete.")
            if rc == 0:
                st.cache_data.clear()

    # ── Inspect Data ──────────────────────────────────────────────────────────
    with tab_inspect:
        st.subheader("Inspect shops")

        df = load_data(conn)
        if df.empty:
            st.info("No data yet.")
            return

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            i_country = st.selectbox("Country", ["All"] + sorted(df["country"].dropna().unique().tolist()))
        with col2:
            city_opts = sorted(df[df["country"] == i_country]["city"].dropna().unique()) if i_country != "All" else sorted(df["city"].dropna().unique())
            i_city    = st.selectbox("City", ["All"] + city_opts)
        with col3:
            i_status  = st.selectbox("Status", ["All"] + sorted(df["status_label"].dropna().unique().tolist()))
        with col4:
            i_search  = st.text_input("Search name / email")

        inspected = df.copy()
        if i_country != "All": inspected = inspected[inspected["country"] == i_country]
        if i_city    != "All": inspected = inspected[inspected["city"]    == i_city]
        if i_status  != "All": inspected = inspected[inspected["status_label"] == i_status]
        if i_search:
            mask = (
                inspected["name"].str.contains(i_search, case=False, na=False) |
                inspected["email"].str.contains(i_search, case=False, na=False)
            )
            inspected = inspected[mask]

        st.caption(f"{len(inspected):,} shops")

        # Full detail table with all columns
        all_cols = ["name", "city", "country", "type", "status_label", "email",
                    "phone", "website", "contact_score", "contact_score_reason",
                    "address", "source", "created_at", "updated_at"]
        all_cols = [c for c in all_cols if c in inspected.columns]

        selected_row = st.dataframe(
            inspected[all_cols].rename(columns={"status_label": "status"}),
            use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="single-row",
        )

        # Detail panel for selected row
        if selected_row.selection.rows:
            idx  = selected_row.selection.rows[0]
            shop = inspected.iloc[idx]
            st.divider()
            st.subheader(shop["name"])
            d1, d2, d3 = st.columns(3)
            d1.write(f"**City:** {shop.get('city', '')}  \n**Country:** {shop.get('country', '')}")
            d2.write(f"**Status:** {shop.get('status_label', '')}  \n**Type:** {shop.get('type', '')}")
            d3.write(f"**Contact score:** {shop.get('contact_score', 'N/A')}")

            if shop.get("email"):    st.write(f"**Email:** {shop['email']}")
            if shop.get("phone"):    st.write(f"**Phone:** {shop['phone']}")
            if shop.get("website"):  st.write(f"**Website:** [{shop['website']}]({shop['website']})")
            if shop.get("address"):  st.write(f"**Address:** {shop['address']}")
            if shop.get("contact_score_reason"):
                st.write(f"**Score reason:** {shop['contact_score_reason']}")


if __name__ == "__main__":
    main()
