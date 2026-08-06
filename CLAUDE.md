# SEC 13F Weekly Digest Tracker

Automated weekly email digest of institutional 13F filings from SEC EDGAR. Pulls filings for 25+ fund managers, computes analytics, and emails formatted digest every Friday at 6am AEST.

---

## Project Overview

- **Main file:** `tracker.py` — fetches 13F filings, parses XML, computes rankings, sends email
- **Automation:** GitHub Actions (`weekly.yml`) runs on Friday schedule
- **Email:** Gmail SMTP via App Password (or SendGrid)
- **Data source:** SEC EDGAR API (public, rate-limited)
- **Compute:** ~5 minutes per run on GitHub Actions free tier

---

## Setup & Configuration

### Environment Variables (GitHub Secrets)

```
EMAIL_FROM    = Gmail address sending the digest
EMAIL_TO      = Recipient email address
EMAIL_PASS    = Gmail App Password (16-char, not regular password)
SMTP_HOST     = smtp.gmail.com
SMTP_PORT     = 587
```

### Manager Universe

Edit `MANAGERS` list in `tracker.py` to add/remove fund managers. Format:
```python
("Display Name", "CIK_NUMBER")
```

Find CIK numbers at: https://www.sec.gov/cgi-bin/browse-edgar

---

## Build & Development

### Dependencies

```bash
pip install -r requirements.txt
# Core: requests, beautifulsoup4, lxml
# Optional: yfinance (for market data)
```

### Running Locally

```bash
# Test a single run
python tracker.py

# Set env vars for email testing
export EMAIL_FROM="your@gmail.com"
export EMAIL_TO="recipient@gmail.com"
export EMAIL_PASS="your-app-password"
python tracker.py
```

### Testing in GitHub Actions

1. Go to repository → **Actions** tab
2. Click **SEC 13F Weekly Digest** workflow
3. Click **Run workflow** button

---

## Architecture & Key Flows

### Main Script Flow

1. **Fetch 13F filings** — Query SEC EDGAR API for latest filing per manager
2. **Parse XML** — Extract holdings data (ticker, value, shares) from filing XML
3. **Compute analytics:**
   - Rankings by total portfolio value
   - Consensus holdings (stocks held by most managers)
   - Mega-positions (largest single positions across all managers)
   - Top 5 holdings per manager
4. **Build HTML email** — Format digest as styled table/cards
5. **Send via Gmail SMTP** — Use App Password to authenticate

### Known Quirks & Limitations

- **13F filings are quarterly, not weekly** — digest repeats same data until next filing
- **45-day lag** — filings are due 45 days after quarter end
- **BlackRock special case** — files consolidated structure, data may appear stale
- **SEC rate-limiting** — heavy requests sometimes timeout; retries on next run
- **XML parsing fragile** — SEC filing format occasionally changes structure

---

## Development Guidelines

### Code Style

- Use descriptive function names
- Keep functions focused (single responsibility)
- Add comments for non-obvious logic (workarounds, SEC quirks, edge cases)
- Use type hints where helpful for readability

### Testing Approach

- Test locally with small manager subset before running full suite
- Email testing: set `EMAIL_TO` to personal email, check inbox/spam
- GitHub Actions testing: trigger workflow manually from Actions tab
- Log output to verify each step (fetch, parse, analytics, send)

### Common Tasks

**Add a new manager:**
1. Get CIK from SEC EDGAR
2. Add tuple to `MANAGERS` list in `tracker.py`
3. Test with `python tracker.py`

**Change email schedule:**
1. Edit `.github/workflows/weekly.yml`
2. Modify `schedule.cron` (5-field format, UTC time)
3. Commit and push

**Fix a parsing error:**
1. Download the problematic 13F XML from EDGAR directly
2. Add handling for new tag/structure in parsing logic
3. Test with that specific filing

---

## Context Continuation Notes

When context is full during development:
- Commit progress to `claude/context-full-build-options-oj8tvn` branch regularly
- Use this CLAUDE.md as source of truth for setup/config
- Refer to line numbers in `tracker.py` for specific code sections
- Keep build commands and test procedures in this file for quick reference

---

## Useful Links

- **SEC EDGAR API:** https://www.sec.gov/cgi-bin/browse-edgar
- **13F Filing Format:** https://www.sec.gov/cgi-bin/viewer?action=view&cik=&accession_number=&xbrl_type=v
- **Gmail App Passwords:** https://support.google.com/accounts/answer/185833
- **GitHub Actions Docs:** https://docs.github.com/actions
- **Cron Schedule Syntax:** https://crontab.guru

---

## Project Status

- **Current branch:** `claude/context-full-build-options-oj8tvn`
- **Last activity:** [context continuation work]
- **Known open issues:** [track here]
