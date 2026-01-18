# Detty Flight Deals

Your personal flight radar for Africa. Finds cheap flights from the US to West & Central Africa. Emails you when deals hit.

## Coverage

**77 routes** monitored (7 origins × 11 destinations)

### US Origins
- JFK (New York)
- EWR (Newark)
- IAD (Washington DC)
- ATL (Atlanta)
- DFW (Dallas)
- IAH (Houston)
- BOS (Boston)

### Africa Destinations (Tier 1)
| City | Country | Code |
|------|---------|------|
| Lagos | Nigeria | LOS |
| Abuja | Nigeria | ABV |
| Accra | Ghana | ACC |
| Dakar | Senegal | DSS |
| Freetown | Sierra Leone | FNA |
| Abidjan | Ivory Coast | ABJ |
| Lomé | Togo | LFW |
| Cotonou | Benin | COO |
| Douala | Cameroon | DLA |
| Yaoundé | Cameroon | NSI |
| Kinshasa | DRC | FIH |

## Deal Tiers

Deals are classified by how much below normal market price:

| Tier | Discount | Example (Lagos) |
|------|----------|-----------------|
| **Good** | 20-30% below | $900-1,200 |
| **Great** | 35-50% below | $700-900 |
| **WOW** | 50%+ below | <$700 |

## How It Works

1. **Deal Finder** runs every 6 hours
   - Searches all 77 routes across the next 6 months
   - Finds the lowest price for each route
   - Classifies deals by tier (Good/Great/WOW)
   - Emails you new deals only (dedupes)

2. **Mistake Fare Monitor** runs every 30 minutes
   - Scans RSS feeds from Secret Flying, The Flight Deal, Fly4Free
   - Filters for Africa destinations
   - Alerts on prices 25%+ below WOW tier (true mistake fares)

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

## Customize

Edit `deal_finder.py`:

- `ORIGINS` - Add/remove US departure cities
- `DESTINATIONS` - Add/remove Africa destinations with price tiers
- `TRIP_LENGTH_DAYS` - Default 10 days
- `WEEKS_TO_SEARCH` - Default 26 (6 months)

## Cost

**$0/month** on GitHub Actions free tier (2000 min/month).

Current usage estimate: ~1,300-1,500 min/month for 77 routes.

## Files

```
detty-flight-deals/
├── deal_finder.py           # Main deal search engine
├── mistake_fare_monitor.py  # RSS feed scanner
├── seen_deals.json          # Deal tracking state
├── requirements.txt         # Python dependencies
├── .github/workflows/
│   ├── find_deals.yml       # Runs every 6 hours
│   └── mistake_fares.yml    # Runs every 30 minutes
└── pm-docs/
    ├── prd.md               # Product requirements
    ├── strategy.md          # Go-to-market strategy
    ├── research.md          # Market research
    └── pricing-tiers.md     # Deal tier thresholds
```

## Roadmap

- [x] 77 routes (Tier 1: West & Central Africa)
- [x] Deal tier classification (Good/Great/WOW)
- [ ] Landing page + email signup
- [ ] Multi-user support via Buttondown
- [ ] Tier 2: East Africa (Nairobi, Addis, Dar, Kampala, Kigali)
- [ ] Tier 3: Southern Africa (Joburg, Cape Town, Harare, Lusaka)
- [ ] Tier 4: North Africa (Cairo, Casablanca, Marrakech, Tunis)
- [ ] Premium tier ($49/year) - September 2026

## If Google blocks you

Signs: Empty results, CAPTCHAs in logs.

Fixes:
1. Reduce frequency (edit cron in `.github/workflows/find_deals.yml`)
2. Add delays between searches (edit `time.sleep()` in deal_finder.py)
3. Run in TEST_MODE to verify with fewer routes
