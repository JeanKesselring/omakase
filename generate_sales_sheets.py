"""
Generate regional sales sheets by replacing prices/currency in the European PDF.
Outputs to data/sales_sheets/.
"""

from pathlib import Path
import fitz  # pymupdf

SOURCE = Path("prompts/sales sheet (europe).pdf")
OUT_DIR = Path("data/sales_sheets")
OUT_DIR.mkdir(parents=True, exist_ok=True)

REGIONS = [
    {
        "name": "united_states",
        "rrp": "$28",
        "rrp_note": "(excl. sales tax)",
        "unit_note": "(excl. sales tax)",
        "at_note": "(at $28)",
        "tier1": "$17.00",
        "tier2": "$15.50",
        "tier3": "$14.00",
    },
    {
        "name": "canada",
        "rrp": "$39 CAD",
        "rrp_note": "(excl. sales tax)",
        "unit_note": "(excl. sales tax)",
        "at_note": "(at $39 CAD)",
        "tier1": "$23.50",
        "tier2": "$21.50",
        "tier3": "$19.50",
    },
    {
        "name": "australia",
        "rrp": "$42 AUD",
        "rrp_note": "(incl. GST)",
        "unit_note": "(excl. GST)",
        "at_note": "(at $42 AUD)",
        "tier1": "$25.00",
        "tier2": "$23.00",
        "tier3": "$21.00",
    },
    {
        "name": "new_zealand",
        "rrp": "$46 NZD",
        "rrp_note": "(incl. GST)",
        "unit_note": "(excl. GST)",
        "at_note": "(at $46 NZD)",
        "tier1": "$28.00",
        "tier2": "$25.50",
        "tier3": "$23.00",
    },
]

def build_replacements(r):
    return {
        "25 €":            r["rrp"],
        "(incl. 19% VAT)": r["rrp_note"],
        "€":               "$",
        "(excl. VAT)":     r["unit_note"],
        "(at 25 €)":       r["at_note"],
        "15.00 €":         r["tier1"],
        "13.75 €":         r["tier2"],
        "12.50 €":         r["tier3"],
    }


def replace_text_in_pdf(src: Path, replacements: dict, dst: Path):
    doc = fitz.open(str(src))

    for page in doc:
        # Collect all spans and their replacement info first
        to_replace = []
        for block in page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    old = span["text"].strip()
                    if old in replacements:
                        to_replace.append({
                            "rect": fitz.Rect(span["bbox"]),
                            "new":  replacements[old],
                            "size": span["size"],
                            "color_int": span["color"],
                        })

        # Redact old text (removes it from content stream, no fill so background shows through)
        for item in to_replace:
            page.add_redact_annot(item["rect"], fill=None)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        # Insert new text in the same positions
        for item in to_replace:
            rect = item["rect"]
            size = item["size"]
            c = item["color_int"]
            color = (((c >> 16) & 0xFF) / 255, ((c >> 8) & 0xFF) / 255, (c & 0xFF) / 255)
            page.insert_text(
                rect.tl + fitz.Point(0, size * 0.85),
                item["new"],
                fontsize=size,
                color=color,
            )

    doc.save(str(dst))
    doc.close()


for region in REGIONS:
    dst = OUT_DIR / f"sales sheet ({region['name'].replace('_', ' ')}).pdf"
    replace_text_in_pdf(SOURCE, build_replacements(region), dst)
    print(f"  Saved -> {dst.name}")

print("\nDone.")
