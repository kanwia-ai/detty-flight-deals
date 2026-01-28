# Domain Pitfalls: Flight Deal Monitoring for African Diaspora

**Domain:** Flight deal monitoring, anomaly detection, email newsletter
**Researched:** 2026-01-27
**Overall confidence:** MEDIUM-HIGH (mix of verified API documentation and domain-specific community knowledge)

---

## Critical Pitfalls

Mistakes that cause rewrites, subscriber loss, or budget blowouts.

---

### Pitfall 1: Amadeus Self-Service API Is Missing Delta, American Airlines, BA, and All LCCs

**What goes wrong:** You build your entire price monitoring pipeline on Amadeus Self-Service, then discover it returns no results for Delta, American Airlines, British Airways, or any low-cost carrier. For US-to-Africa routes, Delta (via partner airlines), American (via British Airways/oneworld), and Ethiopian Airlines codeshares are often the best-priced options. You end up monitoring only a fraction of actual availability.

**Why it happens:** Amadeus Self-Service API explicitly excludes these carriers. Only the Enterprise tier (custom pricing, $$$) includes full GDS content. This is documented in the Amadeus FAQ but easy to miss during initial development.

**Warning signs:**
- Amadeus returns fewer results than Google Flights for the same route/date
- You never see Delta or AA options in API responses
- Price "deals" from Amadeus are consistently higher than what subscribers find on Google Flights

**Consequences:** Subscribers receive alerts that miss the actual cheapest fares. Trust erodes fast -- if someone gets a "WOW" alert for $700 JFK-LOS but sees $580 on Delta via Google Flights, they stop trusting your service. This is the single biggest credibility risk.

**Prevention:**
- **Keep fast-flights (Google Flights scraping) as the primary price source**, not a backup. Amadeus supplements; it does not replace.
- Use Amadeus for what it does well: Cheapest Date Search across a range (gives you the calendar view). Use Google Flights scraping for actual price verification.
- Build a cross-validation step: before alerting, verify Amadeus prices against at least one other source.
- Document which airlines are missing per route so you can explain gaps.

**Detection:** Compare Amadeus results vs. Google Flights results for the same route/date weekly. Track the "miss rate" -- how often Google Flights shows a cheaper price that Amadeus missed entirely.

**Phase impact:** Phase 1 (Amadeus Integration). Must be designed as a supplement to, not replacement for, existing fast-flights scraping.

**Cost of getting it wrong:** Subscriber churn from inaccurate alerts. Rebuilding trust takes 3-6 months of consistent accuracy.

**Confidence:** HIGH -- confirmed directly in Amadeus developer documentation and FAQ.

---

### Pitfall 2: API Cost Trap -- Amadeus Free Tier to Production Escalation

**What goes wrong:** You stay on the Amadeus test environment (2,000 free calls/month), which works perfectly for 6 priority routes. Then you try to expand to all 77 routes and discover you need production access. Production per-call charges range from EUR 0.001 to EUR 0.025 per call. At the high end, 77 routes x 12 checks/day x 30 days = 27,720 calls/month = up to $693/month on Amadeus alone -- far exceeding the $50-100 budget.

**Why it happens:** The test environment hard-caps at 2,000 calls with no overage billing. Production switches to pay-per-call with no cap. The per-call cost varies by API endpoint and is not always clear upfront. Flight Search endpoints are the most expensive in the Amadeus catalog.

**Warning signs:**
- Approaching 1,500 calls/month in test environment
- Plans to add more routes or increase polling frequency
- No cost projection spreadsheet before expanding

**Consequences:** Monthly costs spike beyond budget within the first month of expansion. You either eat the cost, reduce monitoring frequency, or scramble to switch providers.

**Prevention:**
- **Budget before expanding.** Calculate: (routes) x (checks/day) x (30 days) x (cost/call) for every expansion.
- Stay on test environment for priority routes (6 routes, every 2 hours = 6 x 12 x 30 = 2,160 calls -- already at the limit).
- Use Cheapest Date Search (1 call = all dates for a route) instead of Flight Offers Search (1 call per date).
- Consider SerpAPI as an alternative for scaling: Developer plan is $75/month for 5,000 searches, Production is $150/month for 15,000 searches. More predictable billing.
- Set up billing alerts before production migration.

**Detection:** Track API call counts daily. Alert at 80% of monthly quota.

**Phase impact:** Phase 1 (Amadeus Integration) and future expansion phases.

**Cost of getting it wrong:** $200-700/month in unexpected API costs, potentially forcing the project to scale back or shut down.

**Confidence:** HIGH -- pricing confirmed on Amadeus developer documentation and SerpApi pricing page.

---

### Pitfall 3: Gmail SMTP Sending Hits Hard Limits at Scale

**What goes wrong:** Gmail free accounts are limited to 500 emails/day via the web interface but only 100 emails when using SMTP programmatically (which is what the code uses). At 200 subscribers, you cannot send even one email blast per day via SMTP from a free Gmail account. You hit the limit at subscriber #100 and the remaining 100+ subscribers get nothing.

**Why it happens:** The current system uses `smtplib.SMTP_SSL("smtp.gmail.com", 465)` with a Gmail app password. This is subject to Gmail's strict SMTP limits, which are more restrictive than the web interface limits. Additionally, since November 2025, Gmail actively rejects non-compliant bulk email (missing SPF/DKIM/DMARC, spam rate above 0.3%, no one-click unsubscribe).

**Warning signs:**
- Send failures appearing in logs after ~100 emails in a single run
- Gmail account temporarily locked ("You have reached a limit for sending mail")
- Emails landing in Promotions tab or spam folder
- Subscriber complaints about not receiving emails

**Consequences:** Half your subscribers never receive deals. Gmail may suspend the sending account. Emails that do arrive may land in spam, damaging sender reputation permanently.

**Prevention:**
- **Switch to a transactional email service before reaching 50 subscribers.** Options:
  - SendGrid (free tier: 100 emails/day, paid: $19.95/month for 50K emails)
  - Mailgun ($0.80 per 1,000 emails after 1,000 free)
  - Amazon SES ($0.10 per 1,000 emails -- cheapest for volume)
  - Resend (3,000 free emails/month, then $20/month for 50K)
- Implement SPF, DKIM, and DMARC for the sending domain (e.g., dettyflightdeals.com).
- Add one-click unsubscribe header (required by Gmail as of November 2025).
- Maintain spam complaint rate below 0.1% (0.3% maximum).
- Use a custom domain for sending, not @gmail.com.

**Detection:** Log successful vs. failed sends per batch. Alert if failure rate exceeds 5%.

**Phase impact:** Must be addressed BEFORE scaling to 50+ subscribers. This is a Phase 0 prerequisite for growth.

**Cost of getting it wrong:** Complete inability to reach subscribers, permanent damage to sender reputation, potential Gmail account suspension.

**Confidence:** HIGH -- Gmail sending limits confirmed in Google's official documentation. November 2025 enforcement confirmed by multiple sources including Proofpoint and PowerDMARC.

---

### Pitfall 4: Google Flights Scraping Breaks Without Warning

**What goes wrong:** fast-flights (the Python library used for 63 of 77 routes) stops returning results because Google changed their frontend HTML structure, tightened anti-scraping measures, or started requiring client-side JavaScript rendering that the scraper cannot handle.

**Why it happens:** fast-flights works by constructing Base64-encoded Protobuf URL parameters and parsing HTML responses using selectolax. It does not run a full browser. Google regularly updates their frontend, and any structural change to the flight results HTML breaks the parser. The library maintainer (AWeirdDev) may not update promptly. Additionally, Google's anti-scraping defenses in 2025-2026 are "multi-layered and adaptive" -- IP reputation, CAPTCHA, behavioral analytics, and browser fingerprinting.

**Warning signs:**
- Sudden spike in `None` results across all routes (not just one)
- Error messages mentioning HTML parsing failures
- fast-flights library not updated in 30+ days while issues are reported
- Google returning CAPTCHA pages instead of flight data

**Consequences:** 63 of 77 routes go dark. Subscribers receive no deals for days or weeks until the scraper is fixed or replaced.

**Prevention:**
- **Never depend solely on scraping.** Use Amadeus as a parallel data source for priority routes.
- Monitor scraping success rate per run. If < 50% of routes return prices, trigger an admin alert (not subscriber alert).
- Use `fetch_mode="fallback"` in fast-flights (uses Playwright serverless functions when HTML parsing fails).
- Have a pre-evaluated backup: SerpAPI Google Flights API ($75/month for 5,000 searches) as a drop-in replacement that handles anti-scraping.
- Pin fast-flights version and test new versions before deploying.
- Keep the scraping codebase modular so you can swap data sources without rewriting deal classification logic.

**Detection:** Track `prices_found` count per route per run. If total prices found drops below 30% of expected routes for 2+ consecutive runs, trigger admin alert.

**Phase impact:** Ongoing operational risk. The mitigation (Amadeus integration) is Phase 1.

**Cost of getting it wrong:** Complete service outage for days. Subscriber trust destroyed. Scramble to find alternative data source under pressure.

**Confidence:** MEDIUM-HIGH -- fast-flights reliability concerns are documented in the library itself ("Flight scraping can sometimes be unreliable") and confirmed by the 2025-2026 anti-scraping landscape.

---

### Pitfall 5: False Deal Alerts Destroy Subscriber Trust

**What goes wrong:** Subscribers receive "WOW DEAL" alerts for prices that are not actually bookable, are codeshare-inflated, exclude taxes/fees, or have disappeared by the time they click the link. This is the #1 reason people unsubscribe from flight deal services.

**Why it happens:** Multiple root causes:
1. **Ghost fares / cached prices:** Google Flights shows a price from its cache; by the time the subscriber clicks, the fare is gone or $200+ higher. Cached pricing data is usually to blame -- OTAs and search engines communicate with airlines with a delay, so the site might not have the most updated data. Users have reported discrepancies as high as $670 between displayed and actual prices.
2. **Taxes not included:** Some API responses return base fare only. Africa routes frequently have high fuel surcharges and government taxes (Nigeria's various aviation taxes alone can add $50-100).
3. **Codeshare fare dumps:** When multiple airlines appear on the same ticket, fuel surcharges can be accidentally "dumped," creating artificially low fares that may not be honored.
4. **Positioning flight costs ignored:** A deal from IAD might not be useful to someone in Houston -- but the alert doesn't account for the cost of getting to the departure airport.
5. **Price volatility on low-competition routes:** Africa routes with 1-2 carriers can have prices that change dramatically within hours.

**Warning signs:**
- Subscriber feedback: "The price was different when I clicked"
- High click-through rate but low "I booked this deal" feedback
- Deals that are only from a single data source (no cross-validation)
- Prices that seem too good (> 50% below normal) on non-mistake-fare routes

**Consequences:** Subscribers lose trust, unsubscribe, and tell friends the service is unreliable. Recovery from a reputation for false alerts is extremely difficult.

**Prevention:**
- **Cross-validate prices** between Amadeus and Google Flights before alerting. If only one source shows the deal, flag it as unverified.
- Always display total price including taxes. Amadeus `flight-offers-price` endpoint can verify if a fare is actually bookable and return all-in pricing.
- Add "Price verified as of [timestamp]" to alerts, and note that prices change fast.
- Set a minimum confidence threshold: only alert if the deal has been seen in 2+ consecutive checks (not just a single cache hit).
- For mistake fares, set expectations: "This may not be honored. Book at your own risk."
- Consider a "price verification" step using Amadeus Flight Offers Price API before sending high-tier (WOW/Great) alerts.

**Detection:** Track "price accuracy rate" -- what percentage of alerted deals were still available at the listed price 1 hour after alerting. Target: 80%+.

**Phase impact:** Phase 2 (Price Tracking) and Phase 3 (Monitor Script). Cross-validation logic must be built in from the start.

**Cost of getting it wrong:** 30-50% subscriber churn within the first month of inaccurate alerts. Service reputation becomes "that thing that sends fake deals."

**Confidence:** HIGH -- ghost fares and price discrepancy issues are well-documented by Going.com, Secret Flying, and Mighty Travels. The $670 discrepancy figure comes from documented Google Flights booking issues.

---

## Moderate Pitfalls

Mistakes that cause delays, wasted budget, or technical debt.

---

### Pitfall 6: Alert Fatigue Kills Subscriber Engagement

**What goes wrong:** You send too many alerts and subscribers tune out. Or you send too few and subscribers forget you exist. The current system's tier-based deduplication (only alert when price enters a new tier) is a good start, but it can still generate multiple alerts per day during volatile pricing periods.

**Why it happens:** Flight prices fluctuate constantly. 77 routes x 11 destinations = many potential triggers. If even 10% of routes qualify as "Good" on a given day, that is 7-8 deals in one email. Over a week, subscribers might receive 5-7 emails with similar destinations. Email fatigue is well-documented: "When customers feel overwhelmed by constant messaging, they'll stop engaging, mark emails as spam, or unsubscribe altogether."

**Warning signs:**
- Open rates dropping below 30% (industry average for newsletters is ~48% weekly)
- Unsubscribe rate above 0.5% per email (healthy is below 0.17%)
- Spam complaint rate approaching 0.1% (Gmail starts penalizing at 0.3%)
- Subscriber feedback: "Too many emails" or "These deals aren't relevant to me"

**Prevention:**
- **Batch deals into a single daily digest** rather than sending per-discovery. Exception: WOW/mistake fares get instant alerts.
- Cap at 3 emails per week maximum for free tier subscribers.
- Group deals by destination in each email (already implemented -- good).
- Let subscribers choose their home airport and preferred destinations (reduces irrelevant alerts).
- Track engagement per subscriber. If open rate drops below 20% for 3 consecutive emails, reduce frequency or trigger a re-engagement campaign.
- Never send "Good" deals alone -- only bundle them into emails that also contain "Great" or "WOW" deals. This maintains the perception that every email is worth opening.

**Detection:** Monitor open rates, click rates, unsubscribe rates per email. Build a simple dashboard.

**Phase impact:** Phase when implementing subscriber preferences and freemium tiers.

**Cost of getting it wrong:** Gradual subscriber loss of 5-10% per month. Gmail reputation damage from low engagement.

**Confidence:** MEDIUM-HIGH -- email engagement benchmarks are well-documented. Flight deal-specific patterns based on services like Dollar Flight Club and Going.com.

---

### Pitfall 7: Anomaly Detection Without Sufficient Historical Data

**What goes wrong:** You build a price anomaly detection system that fires alerts based on deviations from "baseline" prices -- but with only a few weeks of data, the baselines are wildly inaccurate. A price that looks like a "WOW deal" in February might just be normal low-season pricing. Or a summer price that seems "Normal" is actually a great deal for July.

**Why it happens:** Reliable anomaly detection requires historical baselines that capture full seasonal cycles. The general rule is at least 2 full cycles of any seasonal pattern. For flight pricing:
- Day-of-week patterns: minimum 2-4 weeks
- Monthly patterns: minimum 2-3 months
- Seasonal patterns (Dec peak, summer peak, shoulder): minimum 12-24 months
- Africa-specific patterns (Detty December, Ramadan, AFCON): minimum 2 years

The project currently has a `price_history.jsonl` file that started collecting data recently. This is insufficient for any meaningful statistical baseline.

**Warning signs:**
- Static thresholds (the current approach: $700 = "Great" for Lagos) performing better than dynamic baselines
- Anomaly detection flagging normal seasonal shifts as "deals"
- False positives clustered around season transitions (Jan/Feb, Jun, Sep)

**Prevention:**
- **Keep the current static threshold approach for at least 6 months** while collecting historical data. Static thresholds based on market research are more reliable than poorly-trained dynamic models.
- Continue logging all price data to `price_history.jsonl` (already implemented).
- After 6 months of data, begin building route-specific baselines. After 12 months, add seasonal adjustments.
- Use a hybrid approach: static thresholds as the primary classifier, dynamic baselines as a secondary signal that can flag new patterns.
- For "Detty December" (late Nov - early Jan) and summer (Jun-Aug), manually adjust thresholds higher since normal prices are elevated.

**Detection:** Compare static threshold accuracy vs. dynamic baseline accuracy monthly (once you have both). If static wins consistently, don't switch.

**Phase impact:** Phase 5 (Validation) and beyond. Do not attempt dynamic anomaly detection until you have 6+ months of continuous price data.

**Cost of getting it wrong:** 3-6 months of building a system that performs worse than hardcoded thresholds. Wasted engineering time.

**Confidence:** MEDIUM -- general anomaly detection data requirements are well-documented (AWS, Datadog), but flight-price-specific requirements extrapolated from general principles.

---

### Pitfall 8: Africa-Specific Route Challenges

**What goes wrong:** Several Africa-specific factors cause the monitoring system to produce inaccurate results or miss important context:

**8a. Monopoly/Duopoly Pricing:**
Most US-to-West-Africa routes have only 1-2 carriers (e.g., Ethiopian Airlines hub via ADD, or a single direct carrier). With limited competition, "deals" are rare and pricing is more stable. Your system may go weeks without finding any deal on certain routes, leading subscribers to think it's broken.

**8b. Currency Volatility:**
The Nigerian Naira depreciated ~30% against USD in 2024-2025 due to central bank policy changes. Naira-to-Dollar exchange rate is 69% correlated to airfare charges. This means your USD-denominated thresholds may need adjustment: what was a $900 "Good" deal to Lagos a year ago might now be $1,050 as airlines pass currency costs through.

**8c. Detty December Pricing Explosion:**
"Detty December" (mid-December to early January) sees 2-3x normal pricing on Nigeria and Ghana routes. Flights from the UK to Nigeria have exceeded $1,500+ round-trip. Lagos welcomed 1.2 million visitors in late December 2024, nearly 90% returning diaspora. Your "Normal" price thresholds become meaningless during this period -- alerting a $1,200 JFK-LOS fare as "Normal" in December ignores that most flights cost $2,000+.

**8d. Fuel Surcharge and Tax Complexity:**
Nigerian aviation taxes are substantial and have increased. Airlines flying out of Nigeria pay substantially more due to currency-related costs passed to passengers. Your price parsing must account for total fare including all taxes.

**8e. Seasonal Patterns Differ from US/EU:**
West Africa's dry season (Nov-Apr) overlaps with US winter, but the pricing drivers are different (Detty December, Ramadan, AFCON tournament). These cultural/religious events cause demand spikes that standard seasonal models miss.

**Prevention:**
- **Implement seasonal threshold adjustments:** Increase "Good" thresholds by 30-50% for December-January (Detty December) and by 15-25% for June-August (summer peak). Decrease for shoulder months (Feb-Mar, Sep-Oct).
- Add a route health dashboard: if a route has not produced a deal in 30+ days, flag it as a "tough route" rather than assuming the system is broken.
- Monitor Naira/USD exchange rate quarterly and adjust Nigeria route thresholds accordingly. A 10% Naira depreciation should trigger a threshold review.
- Track Detty December booking trends: start alerting subscribers in July-August about early booking windows for December travel.
- Account for Ramadan timing (shifts 10 days earlier each year) affecting Dakar, Abidjan, and other routes with Muslim-majority destinations.

**Detection:** Track deal frequency per route per month. Routes that never produce deals may have thresholds set too aggressively.

**Phase impact:** Phase 5 (Validation) for threshold tuning. Seasonal adjustments should be implemented before the first December.

**Cost of getting it wrong:** Missing the biggest demand period (Detty December) entirely, or sending irrelevant "Normal" alerts during peak season when subscribers most need guidance.

**Confidence:** MEDIUM-HIGH -- Africa aviation challenges confirmed by IATA, BusinessDay Nigeria, and CNN reporting. Naira depreciation impact confirmed by World Bank data.

---

### Pitfall 9: Freemium Conversion Stalls

**What goes wrong:** You launch a free tier and a paid tier, but almost nobody converts. Industry benchmarks for freemium-to-paid conversion are 2-5% for self-serve products. At 200 subscribers, that is 4-10 paying subscribers. If your premium tier is $5/month, that is $20-50/month -- not enough to cover API costs.

**Why it happens:** The value gap between free and paid tiers is either too small (free gives too much) or too large (paid doesn't seem worth it). For flight deals specifically, the free tier must be compelling enough to grow the subscriber base, but the paid tier must offer clearly superior value.

Common freemium mistakes in newsletters:
- **Giving away too much:** If the free tier sends all Good/Great/WOW deals to all routes, what is left for premium?
- **Gating the wrong thing:** Gating by destination (free = Lagos only, paid = all routes) frustrates users whose friends travel to Accra. Gating by alert speed (free = daily digest, paid = instant alerts) works better.
- **No "aha moment" for free users:** If free users never see a deal they actually book, they have no reason to believe premium would be better.
- **Pricing too high for the audience:** African diaspora travelers may be price-sensitive (they are, after all, looking for deals). $10/month may be too much; $3-5/month or $25-40/year is likely the sweet spot.

**Prevention:**
- **Free tier:** Daily digest of Good deals for all routes. Enough to demonstrate value and build trust.
- **Premium tier:** Instant alerts for Great/WOW deals, mistake fare alerts, personalized airport preferences, price history insights. Target $4-5/month or $39/year.
- Delay freemium until you have 200+ engaged free subscribers. Premature monetization kills growth.
- Track the "booked this deal" feedback -- users who have actually booked are 10x more likely to convert.
- Supplement subscription revenue with affiliate links (Kayak, Google Flights, airline booking links with referral codes).

**Detection:** Track free-to-paid conversion rate, time-to-conversion, and churn rate for paid subscribers. If conversion is below 2%, the value gap is wrong.

**Phase impact:** Future milestone. Do not implement freemium until subscriber base is 200+ and engagement metrics are healthy.

**Cost of getting it wrong:** Months of development on a freemium system that generates $20-50/month. Opportunity cost of features that would grow the free subscriber base instead.

**Confidence:** MEDIUM -- freemium conversion benchmarks are well-documented (Lenny's Newsletter, CrazyEgg), but flight-deal-specific conversion rates are extrapolated.

---

### Pitfall 10: GitHub Actions Limitations at Scale

**What goes wrong:** The current architecture runs everything on GitHub Actions. Multiple workflows compound:
- `find_deals.yml` (daily, ~77 routes x 26 weeks = 2,002 searches, takes 30-60+ minutes)
- `mistake_fares.yml` (every 30 minutes, quick RSS check)
- `priority_monitor.yml` (every 2 hours, 6 Amadeus API calls)
- Email sending within the same workflow

At 200+ subscribers, the email sending step alone could take 100+ seconds (0.5s delay between sends). Combined with scraping time, individual runs approach GitHub Actions' timeout limits.

**Why it happens:**
- Free plan: 2,000 minutes/month for private repos. The deal finder alone could use 900-1,800 minutes/month.
- Scheduled workflows auto-disable after 60 days of repo inactivity (unlikely but worth noting).
- GitHub Actions workflows run on shared infrastructure -- sometimes slow, occasionally fail silently.
- No persistent storage between runs (state files must be committed back to the repo, creating merge conflicts if runs overlap).

**Warning signs:**
- Workflow runs approaching 30+ minute execution time
- Minutes usage above 70% of monthly quota
- Git push conflicts in state files (price_cache.json, seen_deals.json)
- Cron schedules drifting (GitHub does not guarantee exact cron timing)

**Prevention:**
- **For email sending:** Move to a proper email service (SendGrid, Resend) that handles delivery in the background. Do not block the GitHub Actions workflow waiting for 200 emails to send.
- **For state management:** Consider using GitHub Actions cache or an external store (a simple SQLite file on a cheap VPS, or even a Google Sheet as a "database") instead of committing JSON files back to the repo.
- **For scaling beyond free tier:** If the project grows, migrate compute to a $5-10/month VPS (DigitalOcean, Railway, Fly.io) with cron jobs. This removes GitHub Actions minute limits, gives persistent storage, and allows overlapping runs without git conflicts.
- Add workflow duration monitoring. Alert if any run exceeds 80% of timeout.

**Detection:** Check GitHub Actions usage dashboard monthly. Track workflow duration trends.

**Phase impact:** Becomes critical when subscriber count exceeds 100 or when adding more routes/frequency.

**Cost of getting it wrong:** Silent failures where deals are found but emails never send. State file corruption from concurrent runs. Exceeding GitHub Actions minutes and being blocked until the next billing cycle.

**Confidence:** HIGH -- GitHub Actions limits are documented in official GitHub docs. The 2026 pricing changes confirmed but free quotas are unchanged.

---

## Minor Pitfalls

Mistakes that cause annoyance but are fixable with moderate effort.

---

### Pitfall 11: Price History Data Integrity Issues

**What goes wrong:** The `price_history.jsonl` file grows unbounded, contains duplicate entries from overlapping runs, or has gaps from failed scraping sessions. When you eventually try to use this data for anomaly detection baselines, the data quality is too poor to be useful.

**Prevention:**
- Add deduplication: check if the same route+date+price was already logged within the last 6 hours before appending.
- Add data validation: reject entries with impossible prices ($0, $10,000+).
- Periodically export and backup the JSONL file (it is gitignored and could be lost if the Actions runner changes).
- Consider migrating to a simple database (SQLite) once the file exceeds 10MB.

**Phase impact:** Phase 5 (Validation). Data quality issues surface when you first try to analyze the history.

---

### Pitfall 12: Timezone and Date Handling Bugs

**What goes wrong:** The system runs on GitHub Actions (UTC timezone) but searches for flights departing from US cities (Eastern/Central/Mountain/Pacific time). Midnight UTC is 7 PM Eastern. A search run at midnight UTC for "today's date" might miss same-day departures or create off-by-one date errors. Additionally, Amadeus API returns dates in UTC while fast-flights dates are interpreted as departure airport local time.

**Prevention:**
- Always use explicit timezone handling in date calculations.
- Use `departure_date` based on the origin airport's timezone, not the server's timezone.
- Add timezone-aware timestamps to price history logs.

**Phase impact:** Phase 3 (Monitor Script). Easy to fix but annoying to debug.

---

### Pitfall 13: Unsubscribe Compliance Risk

**What goes wrong:** The current unsubscribe mechanism is a mailto: link that requires the subscriber to manually compose an email. This does not meet Gmail's November 2025 requirement for one-click unsubscribe (List-Unsubscribe header with HTTPS URL). Non-compliant emails may be rejected by Gmail.

**Prevention:**
- Add `List-Unsubscribe` and `List-Unsubscribe-Post` headers to all outbound emails.
- Implement a simple unsubscribe endpoint (could be a Google Form that triggers removal from the subscriber sheet).
- Process unsubscribe requests within 2 business days (Gmail requirement).
- When switching to a transactional email service, use their built-in unsubscribe handling.

**Phase impact:** Must be addressed before scaling past 50 subscribers to maintain Gmail deliverability.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation | Severity |
|---|---|---|---|
| **Amadeus Integration** | Content gaps (missing Delta, AA, BA, LCCs) | Keep fast-flights as primary; Amadeus as supplement | Critical |
| **Amadeus Integration** | API cost escalation on expansion | Budget per-call costs before scaling beyond 6 routes | Critical |
| **Price Tracking** | False alerts from ghost fares / cached prices | Cross-validate between sources before alerting | Critical |
| **Price Tracking** | Insufficient historical data for dynamic baselines | Use static thresholds for 6+ months while collecting data | Moderate |
| **Monitor Script** | fast-flights scraping breaks without warning | Use fetch_mode="fallback"; have SerpAPI as backup plan | Critical |
| **Email Delivery** | Gmail SMTP limit at 100 emails via SMTP | Switch to transactional email service before 50 subscribers | Critical |
| **Email Delivery** | Gmail compliance (SPF/DKIM/DMARC, one-click unsub) | Implement before November 2025 enforcement | Critical |
| **Subscriber Growth** | Alert fatigue from over-emailing | Cap at 3 emails/week; batch into digests | Moderate |
| **Subscriber Growth** | Detty December missed opportunity | Implement seasonal thresholds before first December | Moderate |
| **Freemium Launch** | Low conversion (< 2%) wastes development time | Wait for 200+ subscribers before building freemium | Moderate |
| **Scaling** | GitHub Actions minutes/timeout limits | Plan VPS migration path at 100+ subscribers | Moderate |
| **Scaling** | State file git conflicts from concurrent runs | Use external storage or database for state | Minor |

---

## Top 5 Actions (Prioritized by Risk x Likelihood)

1. **Switch email delivery away from Gmail SMTP now.** This is a ticking time bomb at any subscriber count above 50. Amazon SES at $0.10/1K emails is the cheapest; Resend at 3,000 free/month is the easiest.

2. **Keep fast-flights as primary data source; position Amadeus as supplementary.** The Amadeus content gap (missing Delta, AA, BA, all LCCs) makes it unsuitable as a primary source for US-Africa routes.

3. **Build cross-validation before alerting.** Never send a deal alert based on a single data source. If Amadeus shows a deal, verify on Google Flights. If Google Flights shows a deal, verify on Amadeus or a second scrape. This is the single most important quality gate.

4. **Implement seasonal threshold adjustments before December 2026.** Detty December and summer peak pricing will make static thresholds produce misleading results during the most important travel periods.

5. **Budget API costs before any expansion beyond 6 priority routes.** The gap between "free tier" and "production pricing" is dramatic. Model costs at 10x, 50x, and 100x current usage before committing.

---

## Sources

### HIGH Confidence (Official Documentation)
- [Amadeus Pricing](https://developers.amadeus.com/pricing) -- per-call rates, free tier limits
- [Amadeus Developer FAQ](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/faq/) -- missing airlines (Delta, AA, BA, LCCs)
- [Gmail Sending Limits](https://support.google.com/mail/answer/22839?hl=en) -- 500/day web, 100/day SMTP
- [GitHub Actions Billing](https://docs.github.com/en/actions/concepts/billing-and-usage) -- 2,000 free minutes/month
- [SerpApi Pricing](https://serpapi.com/pricing) -- $75-275/month plans

### MEDIUM Confidence (Verified by Multiple Sources)
- [Gmail Enforcement November 2025](https://www.proofpoint.com/us/blog/email-and-cloud-threats/clock-ticking-stricter-email-authentication-enforcements-google-start) -- SPF/DKIM/DMARC/one-click unsubscribe requirements
- [Anti-Scraping 2026](https://mobileproxy.space/en/pages/antiscraping-in-2026-how-defenses-workand-how-to-collect-data-the-right-way.html) -- multi-layered adaptive defenses
- [Google Flights Price Discrepancies](https://www.mightytravels.com/2024/11/google-flights-price-discrepancies-7-common-booking-issues-and-their-technical-causes/) -- ghost fares, cached prices, $670 discrepancy
- [Ghost Fares Definition](https://www.going.com/glossary/ghost-fares) -- OTA caching causes unbookable prices
- [Detty December Pricing](https://naija247news.com/detty-december-2025-flight-prices-skyrocket-nigerians-abroad-struggle-to-return-home/) -- 2-3x normal pricing
- [Africa Aviation Challenges (IATA)](https://airlines.iata.org/2025/10/14/making-african-aviation-economically-viable) -- high costs, limited competition
- [Nigeria Airfare vs. Exchange Rate](https://businessday.ng/aviation/article/explainer-why-airfares-from-nigeria-are-higher-than-african-peers/) -- 69% correlation between NGN/USD and airfares
- [Freemium Conversion Benchmarks](https://www.lennysnewsletter.com/p/what-is-a-good-free-to-paid-conversion) -- 2-5% good, 6-8% great
- [Email Fatigue (Shopify)](https://www.shopify.com/blog/email-fatigue) -- engagement drops from over-sending
- [Email Unsubscribe Rates 2025](https://www.amraandelma.com/email-unsubscribe-rate-statistics/) -- healthy < 0.17%

### LOW Confidence (Single Source / Needs Validation)
- fast-flights reliability -- based on library README and MCP server documentation disclaimers
- Flight-specific anomaly detection data requirements -- extrapolated from AWS/Datadog general anomaly detection guidelines
- Freemium pricing sweet spot for African diaspora audience -- extrapolated from general newsletter conversion data
