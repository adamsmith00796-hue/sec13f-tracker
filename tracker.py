"""
SEC 13F Institutional Tracker
==============================
Fetches 13F filings from SEC EDGAR, computes summary analytics,
and emails a formatted weekly digest.

Requirements: pip install requests beautifulsoup4 lxml
Email via Gmail SMTP (App Password) or SendGrid.
"""

import os
import json
import smtplib
import requests
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
from collections import defaultdict
import yfinance as yf

# ─────────────────────────────────────────────
# CONFIGURATION — edit this section
# ─────────────────────────────────────────────

EMAIL_FROM    = os.environ.get("EMAIL_FROM", "your@gmail.com")
EMAIL_TO      = os.environ.get("EMAIL_TO",   "your@gmail.com")
EMAIL_PASS    = os.environ.get("EMAIL_PASS",  "your-app-password")   # Gmail App Password
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587

# ── Manager Universe ──────────────────────────
# Each entry: (display_name, CIK number)
# CIK = SEC's identifier for each filer. Find at https://www.sec.gov/cgi-bin/browse-edgar
MANAGERS = [
    # ── Michael's original 25 ──
    ("State Street",         "0000093751"),
    ("Vanguard Group",       "0000102909"),
    ("Citadel Advisors",     "0001423689"),
    ("Geode Capital",        "0001239907"),
    ("Morgan Stanley",       "0000895421"),
    ("JP Morgan AM",         "0000019617"),
    ("Millennium Mgmt",      "0001273931"),
    ("BlackRock",            "0001364742"),
    ("Berkshire Hathaway",   "0001067983"),
    ("Fidelity (FMR)",       "0000315066"),
    ("Two Sigma",            "0001179392"),
    ("Renaissance Tech",     "0001037389"),
    ("UBS Asset Mgmt",       "0001030520"),
    ("Invesco",              "0000049679"),
    ("Goldman Sachs",        "0000886982"),
    ("AQR Capital",          "0001160691"),
    ("Point72",              "0001603466"),
    ("Franklin Templeton",   "0000038777"),
    ("Dimensional Fund",     "0000354204"),
    ("Bridgewater",          "0001350715"),
    ("Marshall Wace",        "0001446269"),
    ("Man Group",            "0001077780"),
    ("Wellington Mgmt",      "0000101828"),
    ("Northern Trust",       "0000073124"),
    ("T. Rowe Price",        "0001113169"),

    # ── YOUR CUSTOM ADDITIONS ─────────────────
    # Add your own managers below in the same format.
    # Find CIKs at: https://efts.sec.gov/LATEST/search-index?q=%22manager+name%22&dateRange=custom&startdt=2024-01-01&forms=13F-HR
    # Example additions:
    # ("Tiger Global",        "0001167483"),
    # ("Coatue Management",   "0001336920"),
    # ("D1 Capital",          "0001709323"),
]

# ─────────────────────────────────────────────
# SEC EDGAR HELPERS
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": "SEC-13F-Tracker adam@shiftaisolutions.net",  # SEC requires contact in UA
    "Accept-Encoding": "gzip, deflate",
}

BASE = "https://data.sec.gov"


def get_latest_13f(cik: str) -> dict | None:
    """
    Returns metadata dict for the most recent 13F-HR filing for a given CIK.
    Keys: accessionNumber, filingDate, primaryDocument
    """
    padded = cik.zfill(10)
    url = f"{BASE}/submissions/CIK{padded}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  ⚠ Failed submissions fetch for CIK {cik}: {e}")
        return None

    filings = data.get("filings", {}).get("recent", {})
    forms      = filings.get("form", [])
    dates      = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])
    documents  = filings.get("primaryDocument", [])

    for i, form in enumerate(forms):
        if form in ("13F-HR", "13F-HR/A"):
            return {
                "accessionNumber":  accessions[i],
                "filingDate":       dates[i],
                "primaryDocument":  documents[i],
                "cik":              padded,
            }
    return None


def fetch_13f_holdings(meta: dict) -> list[dict]:
    """
    Fetches and parses the XML holdings table from a 13F filing.
    Returns list of dicts: {name, cusip, value_usd, shares, put_call}
    """
    acc = meta["accessionNumber"].replace("-", "")
    cik = meta["cik"]

    # Try the primary document index to find the XML holdings file
    idx_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/0001193125-{acc[4:]}-index.htm"
    # More reliable: use EDGAR full-text index
    index_url = (
        f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
        f"&CIK={cik}&type=13F-HR&dateb=&owner=include&count=1&search_text="
    )

    # Directly construct filing folder URL
    folder_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/"

    try:
        r = requests.get(folder_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        # Find the infotable XML file
        xml_link = None
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "infotable" in href.lower() or href.endswith(".xml"):
                if "infotable" in href.lower():
                    xml_link = href
                    break
        if not xml_link:
            # Fall back to primary document
            xml_link = f"/{acc}/{meta['primaryDocument']}"
    except Exception as e:
        print(f"  ⚠ Folder fetch error: {e}")
        return []

    xml_url = f"https://www.sec.gov{xml_link}" if xml_link.startswith("/") else xml_link
    try:
        rx = requests.get(xml_url, headers=HEADERS, timeout=20)
        rx.raise_for_status()
        xsoup = BeautifulSoup(rx.text, "lxml-xml")
    except Exception as e:
        print(f"  ⚠ XML fetch error for {xml_url}: {e}")
        return []

    holdings = []
    for entry in xsoup.find_all("infoTable"):
        def txt(tag):
            node = entry.find(tag)
            return node.get_text(strip=True) if node else ""

        try:
            value = int(txt("value") or 0) * 1000   # SEC reports in $thousands
        except ValueError:
            value = 0

        holdings.append({
            "name":     txt("nameOfIssuer"),
            "cusip":    txt("cusip"),
            "value":    value,
            "shares":   txt("sshPrnamt"),
            "put_call": txt("putCall"),   # "Put", "Call", or ""
        })

    return holdings

# ─────────────────────────────────────────────
# PRICE LOOKUP — Buy Up To prices via yfinance
# ─────────────────────────────────────────────
_price_cache = {}

def get_buy_up_to(stock_name: str) -> str:
    """Fetch current market price via yfinance and return a buy-up-to price."""
    if stock_name in _price_cache:
        return _price_cache[stock_name]
    try:
        results = yf.Search(stock_name, max_results=1)
        quotes = results.quotes
        if not quotes:
            _price_cache[stock_name] = "N/A"
            return "N/A"
        sym = quotes[0].get("symbol", "")
        if not sym:
            _price_cache[stock_name] = "N/A"
            return "N/A"
        tkr = yf.Ticker(sym)
        price = getattr(tkr.fast_info, "last_price", None)
        if price and price > 0:
            result = f"${round(price * 1.05, 2):,.2f}"
        else:
            result = "N/A"
        _price_cache[stock_name] = result
        return result
    except Exception:
        _price_cache[stock_name] = "N/A"
        return "N/A"


# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────

def summarise_manager(name: str, holdings: list[dict]) -> dict:
    """Compute per-manager summary statistics."""
    if not holdings:
        return {}

    total = sum(h["value"] for h in holdings)
    sorted_h = sorted(holdings, key=lambda x: x["value"], reverse=True)
    top10_val = sum(h["value"] for h in sorted_h[:10])
    top10_pct = (top10_val / total * 100) if total else 0

    return {
        "name":        name,
        "total":       total,
        "top10_pct":   round(top10_pct, 1),
        "top5":        sorted_h[:5],
        "all_holdings": sorted_h,
        "count":       len(holdings),
    }


def consensus_stocks(all_managers: list[dict]) -> list[dict]:
    """Find stocks held across the most managers, with combined value."""
    stock_data = defaultdict(lambda: {"managers": [], "total_value": 0})

    for mgr in all_managers:
        seen = set()
        for h in mgr.get("all_holdings", []):
            key = h["name"].upper().strip()
            if key and key not in seen:
                stock_data[key]["managers"].append(mgr["name"])
                stock_data[key]["total_value"] += h["value"]
                seen.add(key)

    ranked = sorted(
        stock_data.items(),
        key=lambda x: len(x[1]["managers"]),
        reverse=True
    )
    return [{"stock": k, **v} for k, v in ranked[:15]]


def mega_positions(all_managers: list[dict]) -> list[dict]:
    """Return the 10 single largest disclosed positions across all managers."""
    positions = []
    for mgr in all_managers:
        for h in mgr.get("all_holdings", []):
            positions.append({
                "manager": mgr["name"],
                "stock":   h["name"],
                "value":   h["value"],
                "put_call": h.get("put_call", ""),
            })
    return sorted(positions, key=lambda x: x["value"], reverse=True)[:10]


# ─────────────────────────────────────────────
# EMAIL FORMATTING
# ─────────────────────────────────────────────

def fmt_usd(val: int) -> str:
    """Format a dollar value into readable $XB / $XM."""
    if val >= 1_000_000_000_000:
        return f"${val/1e12:.2f}T"
    elif val >= 1_000_000_000:
        return f"${val/1e9:.1f}B"
    elif val >= 1_000_000:
        return f"${val/1e6:.1f}M"
    else:
        return f"${val:,}"


def build_email_html(summaries: list[dict], consensus: list[dict], mega: list[dict], run_date: str) -> str:
    """Build the full HTML email body."""

    # Rankings table rows
    rank_rows = ""
    for i, s in enumerate(sorted(summaries, key=lambda x: x.get("total", 0), reverse=True), 1):
        rank_rows += f"""
        <tr>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;">{i}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;font-weight:500;">{s['name']}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;">{fmt_usd(s['total'])}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;">{s['top10_pct']}%</td>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;">{s['count']:,}</td>
        </tr>"""

    # Consensus stocks
    consensus_rows = ""
    for i, c in enumerate(consensus[:10], 1):
        mgr_count = len(c["managers"])
        consensus_rows += f"""
        <tr>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;">{i}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;font-weight:500;">{c['stock']}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;">{mgr_count} managers</td>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;">{fmt_usd(c['total_value'])}</td>
        </tr>"""

    # Mega positions
    mega_rows = ""
    for i, m in enumerate(mega, 1):
        flag = f" ({m['put_call']})" if m.get("put_call") else ""
        mega_rows += f"""
        <tr>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;">{i}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;">{m['manager']}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;font-weight:500;">{m['stock']}{flag}</td>
            <td style="padding:6px 10px;border-bottom:1px solid #2a2a2a;">{fmt_usd(m['value'])}</td>
        </tr>"""

    # Per-manager top 5 holdings
    manager_cards = ""
    for s in sorted(summaries, key=lambda x: x.get("total", 0), reverse=True):
        top5_rows = ""
        for h in s.get("top5", []):
            flag = f" [{h['put_call']}]" if h.get("put_call") else ""
            top5_rows += f"""
            <tr>
                <td style="padding:4px 8px;font-size:13px;">{h['name']}{flag}</td>
                <td style="padding:4px 8px;font-size:13px;text-align:right;">{fmt_usd(h['value'])}</td>
                <td style="padding:4px 8px;font-size:13px;text-align:right;">{get_buy_up_to(h['name'])}</td>
            </tr>"""

        manager_cards += f"""
        <div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:8px;padding:16px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <span style="font-weight:700;font-size:15px;color:#e8e8e8;">{s['name']}</span>
                <span style="color:#00d4aa;font-weight:600;">{fmt_usd(s['total'])}</span>
            </div>
            <table style="width:100%;border-collapse:collapse;color:#c0c0c0;">{top5_rows}</table>
        </div>"""

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0d0d0d;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#e8e8e8;">

<div style="max-width:720px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="border-bottom:2px solid #00d4aa;padding-bottom:16px;margin-bottom:24px;">
    <div style="font-size:11px;letter-spacing:3px;color:#00d4aa;text-transform:uppercase;margin-bottom:6px;">Institutional Intelligence</div>
    <h1 style="margin:0;font-size:26px;font-weight:800;color:#ffffff;">SEC 13F Weekly Digest</h1>
    <div style="color:#808080;font-size:13px;margin-top:6px;">Week of {run_date} &nbsp;·&nbsp; {len(summaries)} managers tracked</div>
  </div>

  <!-- Rankings -->
  <div style="margin-bottom:32px;">
    <h2 style="font-size:14px;letter-spacing:2px;text-transform:uppercase;color:#00d4aa;margin-bottom:12px;">Portfolio Rankings</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px;color:#c0c0c0;">
      <thead>
        <tr style="color:#808080;font-size:11px;text-transform:uppercase;letter-spacing:1px;">
          <th style="padding:6px 10px;text-align:left;">#</th>
          <th style="padding:6px 10px;text-align:left;">Manager</th>
          <th style="padding:6px 10px;text-align:left;">Total AUM</th>
          <th style="padding:6px 10px;text-align:left;">Top-10 Conc.</th>
          <th style="padding:6px 10px;text-align:left;">Positions</th>
        </tr>
      </thead>
      <tbody>{rank_rows}</tbody>
    </table>
  </div>

  <!-- Consensus -->
  <div style="margin-bottom:32px;">
    <h2 style="font-size:14px;letter-spacing:2px;text-transform:uppercase;color:#00d4aa;margin-bottom:12px;">Consensus Holdings — Most Widely Held</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px;color:#c0c0c0;">
      <thead>
        <tr style="color:#808080;font-size:11px;text-transform:uppercase;letter-spacing:1px;">
          <th style="padding:6px 10px;text-align:left;">#</th>
          <th style="padding:6px 10px;text-align:left;">Stock</th>
          <th style="padding:6px 10px;text-align:left;">Held By</th>
          <th style="padding:6px 10px;text-align:left;">Combined Value</th>
        </tr>
      </thead>
      <tbody>{consensus_rows}</tbody>
    </table>
  </div>

  <!-- Mega Positions -->
  <div style="margin-bottom:32px;">
    <h2 style="font-size:14px;letter-spacing:2px;text-transform:uppercase;color:#00d4aa;margin-bottom:12px;">Top 10 Single Largest Positions</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px;color:#c0c0c0;">
      <thead>
        <tr style="color:#808080;font-size:11px;text-transform:uppercase;letter-spacing:1px;">
          <th style="padding:6px 10px;text-align:left;">#</th>
          <th style="padding:6px 10px;text-align:left;">Manager</th>
          <th style="padding:6px 10px;text-align:left;">Position</th>
          <th style="padding:6px 10px;text-align:left;">Value</th>
          <th style="padding:6px 10px;text-align:right;">Buy Up To</th>
        </tr>
      </thead>
      <tbody>{mega_rows}</tbody>
    </table>
  </div>

  <!-- Manager Cards -->
  <div style="margin-bottom:32px;">
    <h2 style="font-size:14px;letter-spacing:2px;text-transform:uppercase;color:#00d4aa;margin-bottom:12px;">Manager Breakdown — Top 5 Holdings Each</h2>
    {manager_cards}
  </div>

  <!-- Footer -->
  <div style="border-top:1px solid #2a2a2a;padding-top:16px;font-size:11px;color:#505050;">
    Generated by SEC 13F Tracker · {run_date} · Data sourced from SEC EDGAR · Not financial advice.
  </div>

</div>
</body>
</html>"""
    return html


# ─────────────────────────────────────────────
# EMAIL SENDER
# ─────────────────────────────────────────────

def send_email(subject: str, html_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
    print(f"✅ Email sent to {EMAIL_TO}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    run_date = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*50}")
    print(f"  SEC 13F Tracker — {run_date}")
    print(f"{'='*50}\n")

    summaries = []

    for name, cik in MANAGERS:
        print(f"→ {name} (CIK: {cik})")
        meta = get_latest_13f(cik)
        if not meta:
            print(f"  ⚠ No 13F found. Skipping.")
            continue

        print(f"  Filing: {meta['filingDate']}  Accession: {meta['accessionNumber']}")
        holdings = fetch_13f_holdings(meta)
        print(f"  Holdings parsed: {len(holdings)}")

        if holdings:
            summary = summarise_manager(name, holdings)
            summary["filed"] = meta["filingDate"]
            summaries.append(summary)

        time.sleep(0.5)   # Be polite to SEC EDGAR rate limits

    if not summaries:
        print("No data retrieved. Check CIKs and network.")
        return

    print(f"\n✓ Processed {len(summaries)} managers")

    consensus = consensus_stocks(summaries)
    mega      = mega_positions(summaries)

    html = build_email_html(summaries, consensus, mega, run_date)

    subject = f"SEC 13F Weekly Digest — {run_date}"
    send_email(subject, html)


if __name__ == "__main__":
    main()
