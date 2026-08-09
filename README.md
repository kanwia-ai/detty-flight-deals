# Detty Flight Deals

Personal flight radar for Africa — for Kyra and a few friends, not a startup.
Finds cheap US → West/Central Africa round-trips and emails when deals hit.

**Revived 2026-07-03** after a 3-week silent outage (unpinned `fast-flights`
broke on v3.0 — see the pin comment in `requirements.txt`). The freemium/SaaS
buildout (tiers, trials, SMS, anomaly detection, Turso) was never deployed and
now lives on the `archive/freemium-buildout` branch.

## Coverage

**44 routes** monitored (4 origins × 11 destinations), plus a dedicated
**Detty December sweep** (all origins × LOS/ACC, holiday-window dates,
scanned all year with peak-season thresholds).

### US Origins
JFK · EWR · IAD · ATL
(add DFW/IAH/BOS back in `deal_finder.py` if a friend there joins)

### Africa Destinations
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

A price is judged against what its route + season bucket ("std" vs Detty
window, Dec 10 – Jan 10) has actually traded at over the trailing 90 days of
our own scans (`baselines.py` over `price_history.jsonl`):

- **WOW** — at/below the 5th percentile AND within 5% of the 90-day minimum.
  "Basically the best price we've seen." Emails everyone immediately.
- **Digest** — cheapest 10%. Saved for the Saturday weekly roundup; never
  interrupts.
- Anything above p10 is not a deal and is only logged.

The static bands in `DESTINATIONS` are bootstrap fallbacks for buckets with
under 100 observations. A route re-alerts only when the price *beats* the
last alerted price by 8%+ (5%+ for digest listings), so a fare that just sits
there doesn't get re-announced every two weeks.

## How It Works

1. **Find Deals** (full scan daily 10:00 UTC; Detty-corridor sweep at
   04/16/22 UTC) — `fast-flights` scrapes Google Flights for every route
   across the next 6 months (every other week, departure weekday rotating
   daily), plus the Detty December sweep (LOS/ACC/ABV). WOW fares email
   immediately; Saturday's full run also sends the weekly digest. Alert
   memory lives in `seen_deals.json`.
2. **Mistake Fare Monitor** (hourly) — scans Secret Flying / The Flight Deal /
   Fly4Free RSS for Africa mistake fares.
3. **SerpAPI safety net** (`serpapi_fallback.py`, needs `SERPAPI_KEY` secret) —
   cross-checks WOW deals before they're sent, and takes over the LOS/ACC
   corridors (~6 calls/day) if fast-flights returns nothing for 3 straight
   days. Hard-capped at 200 calls/month (free tier is 250).
4. **Failure sentinel** — 3 consecutive red runs emails Kyra. The pipeline
   can no longer die silently.

## Secrets (GitHub Actions)

| Secret | Purpose |
|--------|---------|
| `SMTP_EMAIL` / `SMTP_PASSWORD` | Gmail app password for sending |
| `NOTIFY_EMAIL` | Kyra's inbox (ops alerts + fallback recipient) |
| `GOOGLE_SHEET_ID` / `GOOGLE_SHEETS_CREDS` | Subscriber list |
| `SERPAPI_KEY` | Optional but recommended — WOW validation + fallback |

## Adding a friend

Add a row to the subscriber Google Sheet, then run the
"Send Welcome Email" workflow (workflow_dispatch).

## Cost

**$0/month.** fast-flights is free; SerpAPI stays inside its free tier by
design; GitHub Actions usage (~10 min/day Find Deals + hourly 1-min monitor)
sits inside the free/Pro minutes for this private repo.

## Files

```
detty-flight-deals/
├── deal_finder.py            # Main deal search engine + Detty sweep
├── serpapi_fallback.py       # WOW validation + emergency corridor scan
├── mistake_fare_monitor.py   # RSS feed scanner
├── mvp0_sender.py            # Google Sheets subscribers + Gmail SMTP
├── scripts/failure_sentinel.py  # emails Kyra after 3 red runs
├── seen_deals.json           # Deal dedup state (committed by the cron)
├── price_history.jsonl       # Every observed price (committed by the cron)
├── fastflights_health.json   # Consecutive empty-scan days
├── serpapi_quota.json        # SerpAPI monthly usage
└── .github/workflows/        # find_deals (daily), mistake_fares (hourly), email tests
```

## Maintenance

- **Quarterly (15 min):** eyeball `price_history.jsonl` percentiles per route
  and re-tune the `DESTINATIONS` bands. Put it on the calendar.
- **If fast-flights breaks again:** the sentinel will email. Check the
  [fast-flights repo](https://github.com/AWeirdDev/flights) for a working
  version to pin; the SerpAPI takeover covers LOS/ACC in the meantime.
- **Amadeus is not an option** — its self-service API portal was decommissioned
  July 17, 2026 (see `docs/plans/2026-01-19-amadeus-continuous-monitoring-design.md`).
