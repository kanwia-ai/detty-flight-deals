# Detty Flight Deals

Finds cheap flights to Africa. Emails you when deals appear.

Runs every 6 hours on GitHub Actions. Free.

## Setup (10 minutes)

### 1. Create GitHub repo

```bash
cd detty-flight-deals
git init
git add .
git commit -m "Initial commit"
gh repo create detty-flight-deals --private --push
```

### 2. Create Gmail App Password

You need an "App Password" (not your regular password):

1. Go to https://myaccount.google.com/apppasswords
2. Select "Mail" and "Other (Custom name)"
3. Name it "Detty Deals"
4. Copy the 16-character password

### 3. Add secrets to GitHub

Go to your repo → Settings → Secrets and variables → Actions → New repository secret

Add these 3 secrets:

| Secret Name | Value |
|-------------|-------|
| `SMTP_EMAIL` | your.email@gmail.com |
| `SMTP_PASSWORD` | (the 16-char app password) |
| `NOTIFY_EMAIL` | your.email@gmail.com |

### 4. Enable GitHub Actions

Go to repo → Actions → Enable workflows

### 5. Run it manually (to test)

Go to Actions → "Find Deals" → "Run workflow" → "Run workflow"

Watch the logs. If it works, you'll get an email with any deals found.

## How it works

- Checks 13 routes to Africa (Lagos, Accra, Nairobi, etc.)
- Compares prices to baseline (typical price for each route)
- If price is 25%+ below baseline → it's a deal
- Emails you the deals

## Customize

Edit `deal_finder.py`:

- `ROUTES` - Add/remove routes to monitor
- `BASELINES` - Adjust typical prices (update as you learn)
- `SAVINGS_THRESHOLD` - Default 25%. Lower = more alerts.

## Cost

$0. GitHub Actions free tier = 2000 minutes/month. This uses ~100 min/month.

## If Google blocks you

Signs: Empty results, CAPTCHAs in logs.

Fixes:
1. Reduce frequency (edit cron in `.github/workflows/find_deals.yml`)
2. Add residential proxy (~$15/mo)
3. Switch to SerpAPI ($50/mo, no scraping needed)

For validation, just reduce frequency first. Usually fine.
