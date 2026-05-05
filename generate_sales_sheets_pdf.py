#!/usr/bin/env python3
"""Generate localized PDF sales sheets by patching content streams in the EUR base PDF.

The PDF stores text as readable byte literals in content streams, e.g.:
  (25 \200)Tj        ← "25 €"  (\200 is octal PDF escape for 0x80 = Windows-1252 €)
  (15.00 \200)Tj     ← wholesale price
  incl. 19% V        ← part of "(incl. 19% VAT)"

We decompress each page's content stream, do byte-level find-and-replace,
and write it back.  No image data or layout is touched.

Run from project root:  python3 generate_sales_sheets_pdf.py
"""

import pikepdf
from pathlib import Path

SOURCE = Path("prompts/sales sheet (europe).pdf")
OUTPUT_DIR = Path("data/sales_sheets")

EUR_WHOLESALE = [15.00, 13.75, 12.50]


def _fmt(amount: float, decimals: int) -> str:
    if decimals == 0:
        return str(round(amount))
    return f"{round(amount, decimals):.{decimals}f}"


# Currency sheet definitions
# curr   : ASCII currency code (safe for the embedded font)
# rate   : indicative EUR → local exchange rate
# rrp    : suggested retail price in local currency (rounded to clean number)
# vat    : local VAT rate (%)
# dec    : decimal places to show in prices
SHEETS = [
    {"file": "bgn_bulgaria",    "curr": "BGN", "rate": 1.956, "rrp": 48.90, "vat": 20,  "dec": 2},
    {"file": "czk_czech_rep",   "curr": "CZK", "rate": 25.0,  "rrp": 625,   "vat": 21,  "dec": 0},
    {"file": "dkk_denmark",     "curr": "kr",  "rate": 7.46,  "rrp": 186,   "vat": 25,  "dec": 0},
    {"file": "huf_hungary",     "curr": "Ft",  "rate": 400.0, "rrp": 10000, "vat": 27,  "dec": 0},
    {"file": "isk_iceland",     "curr": "kr",  "rate": 152.0, "rrp": 3800,  "vat": 24,  "dec": 0},
    {"file": "mdl_moldova",     "curr": "MDL", "rate": 19.2,  "rrp": 480,   "vat": 20,  "dec": 0},
    {"file": "nok_norway",      "curr": "kr",  "rate": 11.8,  "rrp": 295,   "vat": 25,  "dec": 0},
    {"file": "pln_poland",      "curr": "PLN", "rate": 4.28,  "rrp": 107.0, "vat": 23,  "dec": 2},
    {"file": "ron_romania",     "curr": "RON", "rate": 4.97,  "rrp": 124.25,"vat": 19,  "dec": 2},
    {"file": "sek_sweden",      "curr": "kr",  "rate": 11.5,  "rrp": 288,   "vat": 25,  "dec": 0},
    {"file": "chf_switzerland", "curr": "CHF", "rate": 0.94,  "rrp": 23.50, "vat": 8.1, "dec": 2},
    {"file": "try_turkey",      "curr": "TRY", "rate": 38.0,  "rrp": 950,   "vat": 20,  "dec": 0},
    {"file": "gbp_uk",          "curr": "GBP", "rate": 0.86,  "rrp": 21.50, "vat": 20,  "dec": 2},
    {"file": "all_albania",     "curr": "L",   "rate": 100.0, "rrp": 2500,  "vat": 20,  "dec": 0},
]


def _patch(data: bytes, replacements: list[tuple[bytes, bytes]]) -> bytes:
    for old, new in replacements:
        data = data.replace(old, new)
    return data


def make_replacements(sheet: dict) -> tuple[list, list]:
    curr = sheet["curr"].encode()  # bytes, all ASCII
    rate = sheet["rate"]
    rrp = sheet["rrp"]
    vat = sheet["vat"]
    dec = sheet["dec"]

    # Match the Europe sheet: convert EUR wholesale tiers to local currency.
    w1 = round(EUR_WHOLESALE[0] * rate, dec)
    w2 = round(EUR_WHOLESALE[1] * rate, dec)
    w3 = round(EUR_WHOLESALE[2] * rate, dec)

    m1 = round((rrp - w1) / rrp * 100)
    m2 = round((rrp - w2) / rrp * 100)
    m3 = round((rrp - w3) / rrp * 100)

    rrp_str = _fmt(rrp, dec).encode()
    w1_str = _fmt(w1, dec).encode()
    w2_str = _fmt(w2, dec).encode()
    w3_str = _fmt(w3, dec).encode()

    vat_str = f"{vat:g}".encode()  # "20", "8.1", etc. — strips trailing zeros

    # ── Page 1 ─────────────────────────────────────────────────────────────
    # Original stream bytes (4-char octal escape \200 = Windows-1252 €):
    #   (25 \200)Tj
    #   [(\\(incl. 19% V)46.1 (A)92 (T\\))]TJ
    p1 = [
        # Large RRP price top-right: "25 €" → e.g. "49 BGN"
        (b"(25 \\200)Tj", b"(" + rrp_str + b" " + curr + b")Tj"),
        # VAT note: "incl. 19% V..." → "incl. 20% V..."
        (b"incl. 19% V", b"incl. " + vat_str + b"% V"),
    ]

    # ── Page 2 ─────────────────────────────────────────────────────────────
    # Pricing table (12pt font, bottom of page):
    #   (\(at 25 \200\))Tj   ← column header "Store margin (at 25 €)"
    #   (15.00 \200)Tj       ← wholesale tier 1
    #   (13.75 \200)Tj       ← wholesale tier 2
    #   (12.50 \200)Tj       ← wholesale tier 3
    #   (40 %)Tj / (45 %)Tj / (50 %)Tj
    #
    # "€/unit" column header: the € may be a standalone (\200)Tj at absolute
    # position just before "/".  We attempt it; if not found, no harm done.
    p2 = [
        # Try standalone € in column header (positioned just before "/unit")
        (b"(\\200/)Tj", b"(" + curr + b"/)Tj"),
        (b"(\\200)Tj", b"(" + curr + b")Tj"),   # fallback: bare € glyph
        # "(at 25 €)" in "Store margin" header — omit currency to avoid text overflow
        (b"\\(at 25 \\200\\)", b"\\(at " + rrp_str + b"\\)"),
        # Wholesale prices
        (b"(15.00 \\200)Tj", b"(" + w1_str + b" " + curr + b")Tj"),
        (b"(13.75 \\200)Tj", b"(" + w2_str + b" " + curr + b")Tj"),
        (b"(12.50 \\200)Tj", b"(" + w3_str + b" " + curr + b")Tj"),
        # Margins (unchanged for most currencies, but correct either way)
        (b"(40 %)", b"(" + str(m1).encode() + b" %)"),
        (b"(45 %)", b"(" + str(m2).encode() + b" %)"),
        (b"(50 %)", b"(" + str(m3).encode() + b" %)"),
    ]

    return p1, p2


def patch_page(page: pikepdf.Page, replacements: list[tuple[bytes, bytes]]) -> int:
    """Patch all content streams on a page. Returns count of substitutions made."""
    changes = 0
    contents = page.get("/Contents")
    if contents is None:
        return 0

    streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
    for stream in streams:
        original = stream.read_bytes()
        patched = _patch(original, replacements)
        if patched != original:
            stream.write(patched)  # write uncompressed; valid PDF
            changes += 1
    return changes


def generate_pdf(sheet: dict) -> Path:
    pdf = pikepdf.open(SOURCE)
    p1_reps, p2_reps = make_replacements(sheet)

    patch_page(pdf.pages[0], p1_reps)
    patch_page(pdf.pages[1], p2_reps)

    out = OUTPUT_DIR / f"{sheet['file']}.pdf"
    pdf.save(out)
    return out


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for sheet in SHEETS:
        try:
            path = generate_pdf(sheet)
            w1 = round(15.00 * sheet["rate"], sheet["dec"])
            print(
                f"  ✓ {sheet['file']:<25}  "
                f"RRP {_fmt(sheet['rrp'], sheet['dec'])} {sheet['curr']:<4}  "
                f"VAT {sheet['vat']:>4}%  "
                f"→ {path.name}"
            )
        except Exception as exc:
            print(f"  ✗ {sheet['file']}: {exc}")

    print(f"\n{len(SHEETS)} PDFs written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
