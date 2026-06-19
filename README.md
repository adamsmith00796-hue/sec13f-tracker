# SEC 13F Weekly Digest Tracker

Automated weekly email digest of institutional 13F filings, pulled directly from SEC EDGAR.
Tracks 25+ of the world's largest fund managers and emails you a formatted breakdown every Friday.

---

## What You Get Each Week

- **Rankings table** — all managers ranked by total disclosed portfolio size
- **Consensus holdings** — stocks held by the most managers + combined value
- **Mega-positions** — 10 single largest disclosed positions across all managers
- **Manager cards** — top 5 holdings for every manager tracked

---

## Quick Setup (15 minutes)

### Step 1 — Get the code onto GitHub

1. Go to [github.com](https://github.com) and create a free account if you don't have one
2. Click **New repository** → name it `sec13f-tracker` → set to **Private** → click Create
3. Upload all files from this folder to that repo (drag and drop works)

### Step 2 — Set up Gmail for sending emails

1. Go to your Google Account → **Security** → enable **2-Step Verification**
2. Then go to **App Passwords** (search for it in Google Account settings)
3. Create a new App Password named "SEC Tracker"
4. Copy the 16-character password it gives you — you'll need it in Step 3

### Step 3 — Add your secrets to GitHub

In your GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret**

Add these three secrets:

| Secret Name  | Value                                  |
|--------------|----------------------------------------|
| `EMAIL_FROM` | your Gmail address (e.g. you@gmail.com) |
| `EMAIL_TO`   | where to send the digest (can be same) |
| `EMAIL_PASS` | the 16-character App Password from Step 2 |

### Step 4 — Done!

The tracker will now run automatically every **Friday at 6am AEST**.

To test it immediately: go to your repo → **Actions** tab → click **SEC 13F Weekly Digest** → **Run workflow**.

---

## Adding Your Own Managers

Open `tracker.py` and scroll to the `MANAGERS` list near the top.
Add entries in this format:

```python
("Tiger Global", "0001167483"),
```

To find a manager's CIK number:
1. Go to [efts.sec.gov](https://efts.sec.gov/LATEST/search-index?forms=13F-HR)
2. Search the manager name
3. The CIK is the number in the URL or filing header

---

## How It Works (Plain English)

1. Every Friday, GitHub's free servers wake up and run the Python script
2. The script contacts the SEC's public database (EDGAR) and pulls the latest 13F filing for each manager
3. It parses the holdings XML files, computes rankings and consensus stocks
4. It builds a formatted HTML email and sends it to your inbox via Gmail

No servers, no subscriptions, no cost. GitHub Actions gives you 2,000 free minutes/month — this job uses about 5 minutes per run.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Email not arriving | Check spam folder; verify App Password in GitHub Secrets |
| "No 13F found" for a manager | CIK may be wrong — look it up on EDGAR directly |
| Action not running | Go to Actions tab and check the workflow logs for errors |
| Holdings count is 0 | SEC EDGAR occasionally rate-limits heavy requests — retry next day |

---

## Important Notes

- 13F filings are **quarterly**, not weekly. The digest will show the same data most weeks until a new filing drops.
- 13F data is **45 days delayed** — filings are due 45 days after quarter end.
- BlackRock files a consolidated 13F under a different structure — their data may appear stale.
- This is **not financial advice**.

---

## Files in This Repo

```
sec13f-tracker/
├── tracker.py                        # Main script — all the logic
├── requirements.txt                  # Python dependencies
├── README.md                         # This file
└── .github/
    └── workflows/
        └── weekly.yml                # GitHub Actions automation schedule
```
