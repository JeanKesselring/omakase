#!/usr/bin/env python3
"""Generate localized sales sheets for non-Euro markets.

Outputs one printable HTML file per currency to data/sales_sheets/.
Open any file in a browser and use Print → Save as PDF.

Exchange rates are indicative as of early 2026.
EUR base: RRP 25 € incl. 19% VAT; wholesale 15.00 / 13.75 / 12.50 € excl. VAT.
"""

from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "data" / "sales_sheets"

EUR_RRP = 25.00
EUR_WHOLESALE = [15.00, 13.75, 12.50]
ORDER_TIERS = ["10 – 24", "25 – 49", "50 – 100"]

SHEETS = [
    {
        "filename": "bgn_bulgaria",
        "label": "Bulgaria",
        "countries": "Bulgaria",
        "currency": "BGN",
        "vat": 20,
        "rate": 1.956,
        "rrp": 49.00,
        "decimals": 2,
        "symbol": "BGN",
        "symbol_before": False,
        "thousands_sep": ",",
        "decimal_sep": ".",
        "note": "1 EUR ≈ 1.956 BGN (fixed peg). Wholesale invoiced in EUR.",
    },
    {
        "filename": "czk_czech_republic",
        "label": "Czech Republic",
        "countries": "Czech Republic",
        "currency": "CZK",
        "vat": 21,
        "rate": 25.0,
        "rrp": 625.00,
        "decimals": 0,
        "symbol": "Kč",
        "symbol_before": False,
        "thousands_sep": " ",
        "decimal_sep": ",",
        "note": "1 EUR ≈ 25.0 CZK (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "dkk_denmark",
        "label": "Denmark",
        "countries": "Denmark",
        "currency": "DKK",
        "vat": 25,
        "rate": 7.46,
        "rrp": 189.00,
        "decimals": 0,
        "symbol": "kr",
        "symbol_before": False,
        "thousands_sep": ".",
        "decimal_sep": ",",
        "note": "1 EUR ≈ 7.46 DKK (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "huf_hungary",
        "label": "Hungary",
        "countries": "Hungary",
        "currency": "HUF",
        "vat": 27,
        "rate": 400.0,
        "rrp": 9990.00,
        "decimals": 0,
        "symbol": "Ft",
        "symbol_before": False,
        "thousands_sep": " ",
        "decimal_sep": ",",
        "note": "1 EUR ≈ 400 HUF (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "isk_iceland",
        "label": "Iceland",
        "countries": "Iceland",
        "currency": "ISK",
        "vat": 24,
        "rate": 152.0,
        "rrp": 3800.00,
        "decimals": 0,
        "symbol": "kr",
        "symbol_before": False,
        "thousands_sep": ".",
        "decimal_sep": ",",
        "note": "1 EUR ≈ 152 ISK (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "mdl_moldova",
        "label": "Moldova",
        "countries": "Moldova",
        "currency": "MDL",
        "vat": 20,
        "rate": 19.2,
        "rrp": 480.00,
        "decimals": 0,
        "symbol": "MDL",
        "symbol_before": False,
        "thousands_sep": ",",
        "decimal_sep": ".",
        "note": "1 EUR ≈ 19.2 MDL (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "nok_norway",
        "label": "Norway",
        "countries": "Norway",
        "currency": "NOK",
        "vat": 25,
        "rate": 11.8,
        "rrp": 299.00,
        "decimals": 0,
        "symbol": "kr",
        "symbol_before": False,
        "thousands_sep": " ",
        "decimal_sep": ",",
        "note": "1 EUR ≈ 11.8 NOK (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "pln_poland",
        "label": "Poland",
        "countries": "Poland",
        "currency": "PLN",
        "vat": 23,
        "rate": 4.28,
        "rrp": 109.00,
        "decimals": 2,
        "symbol": "zł",
        "symbol_before": False,
        "thousands_sep": " ",
        "decimal_sep": ",",
        "note": "1 EUR ≈ 4.28 PLN (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "ron_romania",
        "label": "Romania",
        "countries": "Romania",
        "currency": "RON",
        "vat": 19,
        "rate": 4.97,
        "rrp": 125.00,
        "decimals": 2,
        "symbol": "lei",
        "symbol_before": False,
        "thousands_sep": ".",
        "decimal_sep": ",",
        "note": "1 EUR ≈ 4.97 RON (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "sek_sweden",
        "label": "Sweden",
        "countries": "Sweden",
        "currency": "SEK",
        "vat": 25,
        "rate": 11.5,
        "rrp": 289.00,
        "decimals": 0,
        "symbol": "kr",
        "symbol_before": False,
        "thousands_sep": " ",
        "decimal_sep": ",",
        "note": "1 EUR ≈ 11.5 SEK (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "chf_switzerland",
        "label": "Switzerland & Liechtenstein",
        "countries": "Switzerland, Liechtenstein",
        "currency": "CHF",
        "vat": 8.1,
        "rate": 0.94,
        "rrp": 23.50,
        "decimals": 2,
        "symbol": "CHF",
        "symbol_before": True,
        "thousands_sep": "'",
        "decimal_sep": ".",
        "note": "1 EUR ≈ 0.94 CHF (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "try_turkey",
        "label": "Turkey",
        "countries": "Turkey",
        "currency": "TRY",
        "vat": 20,
        "rate": 38.0,
        "rrp": 950.00,
        "decimals": 0,
        "symbol": "₺",
        "symbol_before": True,
        "thousands_sep": ".",
        "decimal_sep": ",",
        "note": "1 EUR ≈ 38 TRY (indicative — rate may vary significantly). Wholesale invoiced in EUR.",
    },
    {
        "filename": "gbp_uk",
        "label": "United Kingdom",
        "countries": "United Kingdom",
        "currency": "GBP",
        "vat": 20,
        "rate": 0.86,
        "rrp": 21.99,
        "decimals": 2,
        "symbol": "£",
        "symbol_before": True,
        "thousands_sep": ",",
        "decimal_sep": ".",
        "note": "1 EUR ≈ 0.86 GBP (indicative). Wholesale invoiced in EUR.",
    },
    {
        "filename": "all_albania",
        "label": "Albania",
        "countries": "Albania",
        "currency": "ALL",
        "vat": 20,
        "rate": 100.0,
        "rrp": 2500.00,
        "decimals": 0,
        "symbol": "L",
        "symbol_before": False,
        "thousands_sep": ",",
        "decimal_sep": ".",
        "note": "1 EUR ≈ 100 ALL (indicative). Wholesale invoiced in EUR.",
    },
]


def fmt(amount: float, sheet: dict, force_decimals: int | None = None) -> str:
    decimals = force_decimals if force_decimals is not None else sheet["decimals"]
    dsep = sheet["decimal_sep"]
    tsep = sheet["thousands_sep"]
    sym = sheet["symbol"]
    before = sheet["symbol_before"]

    if decimals == 0:
        integer = f"{round(amount):,}".replace(",", tsep)
        val = integer
    else:
        rounded = round(amount, decimals)
        raw = f"{rounded:,.{decimals}f}"
        # raw uses "," as thousands and "." as decimal — swap to locale separators
        parts = raw.split(".")
        int_part = parts[0].replace(",", tsep)
        dec_part = parts[1] if len(parts) > 1 else "0" * decimals
        val = f"{int_part}{dsep}{dec_part}"

    space = " " if (before and len(sym) > 1) else ""
    if before:
        return f"{sym}{space}{val}"
    else:
        return f"{val} {sym}"


def fmt_rrp(amount: float, sheet: dict) -> str:
    """Format RRP — suppress trailing zeros for whole numbers."""
    if amount == int(amount):
        return fmt(amount, sheet, force_decimals=0)
    return fmt(amount, sheet)


def margin_pct(rrp: float, wholesale: float) -> int:
    return round((rrp - wholesale) / rrp * 100)


def build_price_rows(sheet: dict) -> str:
    rrp = sheet["rrp"]
    rate = sheet["rate"]
    rows = []
    for tier, eur_w in zip(ORDER_TIERS, EUR_WHOLESALE):
        w_local = eur_w * rate
        m = margin_pct(rrp, w_local)
        rows.append(
            f'<tr>'
            f'<td>{tier}</td>'
            f'<td>{fmt(w_local, sheet)}</td>'
            f'<td>{m} %</td>'
            f'</tr>'
        )
    return "\n".join(rows)


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>OMAKASE — Sales Sheet | {label}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
  font-family: Arial, Helvetica, sans-serif;
  color: #1a1a1a;
  background: #e8e8e8;
}}

.page {{
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto 16px;
  background: white;
  overflow: hidden;
  position: relative;
}}

@media print {{
  body {{ background: white; }}
  .page {{ margin: 0; page-break-after: always; box-shadow: none; }}
}}

/* ── PAGE 1 ─────────────────────────────────────────── */
.page-1 {{
  background: linear-gradient(150deg, #f7bcbc 0%, #e85070 55%, #f2a8b8 100%);
  display: flex;
  flex-direction: column;
}}

.hero {{
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 52px 40px 40px;
  min-height: 195mm;
}}

/* CSS-only game box illustration */
.game-box {{
  width: 230px;
  height: 295px;
  background: linear-gradient(135deg, #faf2de 0%, #e8d498 100%);
  border-radius: 14px;
  box-shadow:
    18px 18px 50px rgba(0,0,0,0.32),
    -6px -6px 18px rgba(255,255,255,0.35),
    inset 0 1px 0 rgba(255,255,255,0.55);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 22px;
  transform: perspective(900px) rotateY(-9deg) rotateX(2deg);
}}

.sushi-outer {{
  width: 165px;
  height: 165px;
  border-radius: 50%;
  background: linear-gradient(180deg, #f6e4a8 0%, #f6e4a8 50%, #4a9952 50%, #4a9952 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 2px 12px rgba(0,0,0,0.12);
}}

.sushi-inner {{
  width: 105px;
  height: 105px;
  border-radius: 50%;
  background: radial-gradient(circle at 38% 36%, #d4956a 0%, #9b6040 50%, #5c3520 100%);
  box-shadow: inset 0 -5px 14px rgba(0,0,0,0.28);
}}

.box-brand {{
  font-size: 27px;
  font-weight: 900;
  letter-spacing: 6px;
  color: #2a1508;
}}

/* Bottom white info bar */
.info-bar {{
  background: white;
  padding: 26px 38px 28px;
}}

.info-grid {{
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 18px;
  align-items: center;
}}

.game-heading {{
  font-size: 24px;
  font-weight: 900;
  letter-spacing: 2px;
  margin-bottom: 12px;
}}

.game-heading span {{
  font-weight: 400;
  font-size: 20px;
  letter-spacing: 0;
  color: #555;
}}

.two-col {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 12px;
}}

.desc {{
  font-size: 12.5px;
  line-height: 1.65;
  color: #333;
}}

.contents {{
  font-size: 12.5px;
  line-height: 1.65;
  color: #333;
}}

.contents b {{ font-weight: 700; }}

.price-block {{
  text-align: right;
  padding-left: 22px;
  border-left: 2px solid #ececec;
  min-width: 120px;
}}

.rrp-label {{
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: #aaa;
  margin-bottom: 2px;
}}

.rrp-price {{
  font-size: 44px;
  font-weight: 900;
  line-height: 1.05;
  white-space: nowrap;
}}

.vat-note {{
  font-size: 10px;
  color: #999;
  margin-top: 2px;
}}

/* ── PAGE 2 ─────────────────────────────────────────── */
.page-2 {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr auto;
}}

.left-visual {{
  background: linear-gradient(150deg, #f7bcbc 0%, #e85070 55%, #f2a8b8 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 30px 24px;
  min-height: 175mm;
}}

/* Card grid mockup */
.cards-grid {{
  display: grid;
  grid-template-columns: repeat(3, 62px);
  grid-template-rows: repeat(3, 84px);
  gap: 8px;
}}

.card {{
  border-radius: 7px;
  border: 2.5px solid rgba(255,255,255,0.7);
  box-shadow: 3px 3px 10px rgba(0,0,0,0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}}

.card.blue   {{ background: linear-gradient(135deg, #b8cce8, #8aacd8); }}
.card.purple {{ background: linear-gradient(135deg, #c8b8e8, #a898d8); }}
.card.gold   {{ background: linear-gradient(135deg, #f0d898, #d8b868); }}

.gameplay-col {{
  padding: 28px 32px 24px;
}}

.gameplay-title {{
  font-size: 22px;
  font-weight: 900;
  letter-spacing: 3px;
  text-transform: uppercase;
  margin-bottom: 20px;
}}

.step {{
  display: flex;
  gap: 9px;
  margin-bottom: 13px;
  align-items: flex-start;
}}

.step-num {{
  font-weight: 700;
  font-size: 12.5px;
  min-width: 16px;
  padding-top: 1px;
}}

.step-text {{
  font-size: 12px;
  line-height: 1.55;
  color: #333;
}}

.step-text b {{ font-weight: 700; color: #1a1a1a; }}

.mini-icons {{
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 5px;
}}

.mini-card {{
  width: 18px;
  height: 25px;
  background: #c8d4e8;
  border-radius: 3px;
  border: 1px solid #a8b8cc;
}}

.mini-slot {{
  width: 18px;
  height: 25px;
  border: 1.5px solid #bbb;
  border-radius: 3px;
}}

.mini-slot.filled {{ background: #c8d4e8; }}

.arr {{ font-size: 11px; color: #777; line-height: 25px; }}

/* Pricing row — full width */
.pricing-row {{
  grid-column: 1 / 3;
  padding: 20px 38px 24px;
  border-top: 1px solid #e4e4e4;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 36px;
  align-items: start;
}}

table.pt {{
  border-collapse: collapse;
  font-size: 13.5px;
}}

table.pt th {{
  font-weight: 700;
  font-size: 12.5px;
  padding: 0 22px 9px 0;
  text-align: left;
  border-bottom: 2.5px solid #1a1a1a;
  white-space: nowrap;
}}

table.pt td {{
  padding: 9px 22px 9px 0;
  border-bottom: 1px solid #ebebeb;
  color: #444;
}}

table.pt td:first-child {{ color: #666; }}

.exchange-note {{
  font-size: 9.5px;
  color: #bbb;
  margin-top: 9px;
  font-style: italic;
}}

.contact {{
  font-size: 11.5px;
  line-height: 2;
  color: #555;
}}

.contact a {{ color: #555; text-decoration: underline; }}
</style>
</head>
<body>

<!-- ══════════ PAGE 1 ══════════ -->
<div class="page page-1">
  <div class="hero">
    <div class="game-box">
      <div class="sushi-outer">
        <div class="sushi-inner"></div>
      </div>
      <div class="box-brand">OMAKASE</div>
    </div>
  </div>
  <div class="info-bar">
    <div class="info-grid">
      <div>
        <div class="game-heading">OMAKASE <span>The Sushi Game</span></div>
        <div class="two-col">
          <p class="desc">Compete with other diners to collect the most valuable sushi sets.
          Strategize, swap, and use action cards to outsmart your opponents.</p>
          <p class="desc">Strong, modern theme (sushi &amp; Japan) with wide appeal. Simple rules,
          easy to demo and explain in under 5 minutes.</p>
        </div>
        <p class="contents"><b>45</b> Sushi Cards, <b>17</b> Action Cards, <b>1</b> Rulebook, <b>1</b> Menu</p>
      </div>
      <div class="price-block">
        <div class="rrp-label">RRP</div>
        <div class="rrp-price">{rrp_display}</div>
        <div class="vat-note">(incl. {vat_pct}% VAT)</div>
      </div>
    </div>
  </div>
</div>

<!-- ══════════ PAGE 2 ══════════ -->
<div class="page page-2">
  <div class="left-visual">
    <div class="cards-grid">
      <div class="card blue">🍣</div>
      <div class="card purple">🍱</div>
      <div class="card gold">🐟</div>
      <div class="card gold">🦐</div>
      <div class="card blue">🍙</div>
      <div class="card purple">🥢</div>
      <div class="card purple">🫧</div>
      <div class="card gold">🍤</div>
      <div class="card blue">🌊</div>
    </div>
  </div>

  <div class="gameplay-col">
    <div class="gameplay-title">Gameplay</div>

    <div class="step">
      <span class="step-num">1.</span>
      <div class="step-text">
        <b>Draw a Card:</b> Draw one card from the deck.
        <div class="mini-icons">
          <div class="mini-card"></div>
          <span class="arr">→</span>
          <div class="mini-card"></div><div class="mini-card"></div><div class="mini-card"></div>
        </div>
      </div>
    </div>

    <div class="step">
      <span class="step-num">2.</span>
      <div class="step-text">
        <b>Play an Action Card:</b> If you have one, you can play it by putting it into the trash.
        <div class="mini-icons">
          <div class="mini-card"></div><div class="mini-card"></div>
          <span class="arr">→</span>
          <div class="mini-card"></div>
        </div>
      </div>
    </div>

    <div class="step">
      <span class="step-num">3.</span>
      <div class="step-text">
        <b>Exchange a Card:</b> Exchange one card from your hand with any card on the conveyor belt.
        <div class="mini-icons">
          <div class="mini-slot"></div><div class="mini-slot"></div>
          <div class="mini-slot"></div><div class="mini-slot"></div>
          <div class="mini-slot"></div>
          <span class="arr">⇄</span>
          <div class="mini-card"></div>
        </div>
      </div>
    </div>

    <div class="step">
      <span class="step-num">4.</span>
      <div class="step-text">
        <b>Play an Action Card:</b> After swapping a card, you have another opportunity
        to play an action card.
      </div>
    </div>

    <div class="step">
      <span class="step-num">5.</span>
      <div class="step-text">
        <b>Move the Conveyor Belt:</b> Add a new card to the belt. Move all cards one spot
        to the right. The card that falls off goes to the trash.
        <div class="mini-icons">
          <div class="mini-card"></div>
          <span class="arr">→</span>
          <div class="mini-slot filled"></div><div class="mini-slot filled"></div>
          <div class="mini-slot filled"></div><div class="mini-slot filled"></div>
          <span class="arr">→</span>
          <div class="mini-card"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Full-width pricing section -->
  <div class="pricing-row">
    <div>
      <table class="pt">
        <thead>
          <tr>
            <th>Order Size</th>
            <th>{currency_col_header}<br>(excl. VAT)</th>
            <th>Store margin<br>(at {rrp_display})</th>
          </tr>
        </thead>
        <tbody>
{price_rows}
        </tbody>
      </table>
      <div class="exchange-note">{exchange_note}</div>
    </div>
    <div class="contact">
      @omakasegame<br>
      info@omakasegame.com<br>
      <a href="https://www.omakasegame.com">www.omakasegame.com</a>
    </div>
  </div>
</div>

</body>
</html>
"""


def generate_sheet(sheet: dict) -> str:
    rrp_display = fmt_rrp(sheet["rrp"], sheet)
    price_rows = build_price_rows(sheet)
    vat_raw = sheet["vat"]
    vat_pct = f"{vat_raw:.4g}"  # strips unnecessary trailing zeros (e.g. 8.1, not 8.10)

    return HTML_TEMPLATE.format(
        label=sheet["label"],
        rrp_display=rrp_display,
        vat_pct=vat_pct,
        currency_col_header=sheet["currency"],
        price_rows=price_rows,
        exchange_note=sheet["note"],
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for sheet in SHEETS:
        html = generate_sheet(sheet)
        path = OUTPUT_DIR / f"{sheet['filename']}.html"
        path.write_text(html, encoding="utf-8")
        rrp_display = fmt_rrp(sheet["rrp"], sheet)
        w_prices = [fmt(w * sheet["rate"], sheet) for w in EUR_WHOLESALE]
        print(
            f"  ✓ {sheet['label']:<30} "
            f"RRP {rrp_display:<12} "
            f"VAT {sheet['vat']:>4}%  "
            f"wholesale: {' / '.join(w_prices)}"
        )
        print(f"    → {path}")

    print(f"\n{len(SHEETS)} sales sheets written to {OUTPUT_DIR}/")
    print("Open any .html file in a browser and use File → Print → Save as PDF.")


if __name__ == "__main__":
    main()
