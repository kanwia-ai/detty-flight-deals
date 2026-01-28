# Feature Landscape: Flight Deal Monitoring for African Diaspora

**Domain:** Freemium flight deal alert service (Africa-focused niche)
**Researched:** 2026-01-27
**Overall Confidence:** MEDIUM-HIGH (competitor features well-documented; deal detection internals are proprietary)

---

## Competitor Analysis Summary

### How Competitors Actually Find Deals

| Competitor | Detection Method | Scale | Africa Coverage | Confidence |
|---|---|---|---|---|
| **Going (Scott's Cheap Flights)** | 25+ human deal hunters using ITA Matrix, Google Flights, and GDS-adjacent tools. Not fully automated -- labor-intensive manual scanning with some automated monitoring. They "track millions of airfares every single day." | 900+ airports, millions of fares/day | 2-3 Africa deals/month (afterthought) | MEDIUM -- they don't disclose exact tech stack |
| **Secret Flying** | Custom-built proprietary software that scans "millions of flights daily." Runs 24/7. Focuses on three error types: self-dump fares (missing fuel surcharges), OTA glitches, and human pricing errors. | Global, millions of flights | Occasional Africa coverage | MEDIUM -- described as "incredibly powerful software" but details undisclosed |
| **Hopper** | ML/AI prediction engine processing 300 billion flight prices/month. 5+ years of historical data. 95% accuracy claim on price predictions up to 1 year out. Not a deal-finding service -- it's a "when to buy" predictor + OTA. | 120M+ downloads, global | Full global coverage but no Africa-specific focus | HIGH -- well documented via press and Harvard case study |
| **FareDrop (Daily Drop Pro)** | AI-powered algorithms scanning "millions of flights around the clock" across 140+ airlines. Passive monitoring with verified deal quality (confirm bookability before sending). | 140+ airlines, global | General international coverage | LOW -- "AI-powered" is vague marketing speak |
| **Matt's Flights** | Primarily manual: team of experts using Google Flights and other publicly available tools. Region-based alerts. Google Flights screenshots included in deal emails. | US-focused, international | Minimal | MEDIUM |
| **Thrifty Traveler** | Human team scanning 24/7. 200+ departure airports including small regionals. ~1,200 deals sent in 2025. Text alerts for time-sensitive mistake fares. Strong points/miles coverage. | 200+ airports, US + Canada | General international | MEDIUM |
| **Dollar Flight Club** | Team-based scanning of flight databases. 30 US airports. Curated deals including mistake fares. | 30 US airports | General international | LOW |

### Key Insight: Deal Detection Is Mostly Human + Tools

**The dirty secret of the flight deal industry:** Even Going, the largest player ($10.8M revenue, ~100 employees), relies heavily on humans using publicly available tools. True GDS/ATPCO raw data access costs $100K+/month -- prohibitive for deal services. The actual workflow is:

1. Humans scan ITA Matrix, Google Flights, and airline sites for anomalies
2. Some automated monitoring flags routes with unusual price drops
3. Human curators verify deals are real and bookable
4. Alerts go out to subscribers

**Implication for Detty:** You don't need GDS access to compete. Google Flights scraping (via `fast-flights`) + Amadeus API for priority routes + anomaly detection on price history data is a viable approach at your budget. The competitive edge comes from *focus* (Africa routes only) and *speed* (detect before the general-purpose services pick it up).

---

## Alert Frequency & Fatigue Management

| Competitor | Free Tier Frequency | Paid Tier Frequency | Fatigue Strategy |
|---|---|---|---|
| **Going** | 1-2 deals/week (continental US only) | 3-5/week (varies by airport); 1-4 points deals/week | "Won't clog your inbox" -- only send deals "worth interrupting your day" |
| **Thrifty Traveler** | 1-2 deals/week | 3-6/day with "All Cities" (~22/week total) | Text alerts for time-sensitive mistake fares; email for regular deals |
| **Matt's Flights** | 1 deal/week | 2-3 emails/week | Region-based filtering reduces noise |
| **Dollar Flight Club** | 13 domestic deals/week | Daily alerts including mistake fares | Price threshold filtering |
| **FareDrop** | Limited economy-only notifications | All deals + business class | Cannot guarantee frequency -- completely demand-driven |
| **Hopper** | Continuous (app-based) | N/A (OTA model) | Only notifies on "drastic" price changes; ignores small fluctuations |

### Key Insight: Frequency Is Not the Problem -- Relevance Is

Going's philosophy is instructive: they won't send a deal unless it's "worth interrupting your day." The services that get complaints about alert fatigue (Dollar Flight Club) are the ones that send high volume with variable quality.

**Implication for Detty:** With 77 Africa routes, you'll naturally have lower volume than general services. The risk is not fatigue -- it's silence. The tier-escalation model (only alert on tier transitions, not $5 wiggles) is the right approach. Consider a "weekly digest" for the free tier and "instant alerts" for premium.

---

## Free vs Paid Tier Comparison

| Feature | Going Free | Going Premium ($49/yr) | Going Elite ($199/yr) | Thrifty Traveler Free | Thrifty Traveler Premium ($99/yr) | Matt's Flights Free | Matt's Flights Premium ($60/yr) |
|---|---|---|---|---|---|---|---|
| Economy deals | Continental US only | International + domestic | International + domestic | 1-2/week | All (~22/week) | 1/week | 2-3/week |
| Mistake fares | No | Yes | Yes | No | Yes | No | Yes (5x more deals) |
| Business/First class | No | No | Yes | No | Yes (included!) | No | No |
| Airports | 5 | 10 | Unlimited | Limited | 200+ | Region-based | Multi-region |
| Destination watchlist | No | Yes | Yes | No | Yes | No | No |
| Points/Miles deals | No | Yes | Yes | No | Yes | No | No |
| Earlier access | No | 30 min earlier | 30 min earlier | No | Yes | No | Yes |
| Free trial | - | 14 days | 14 days | - | N/A | - | N/A |

### Key Insight: The Conversion Trigger Is Not Features -- It's Proof

Going's freemium funnel works because of one psychological lever: **free users see that great deals exist, but don't get the best ones.** The conversion triggers are:

1. **Expired deal FOMO**: "Last week, Premium members saved $800 on JFK-London. Here's what you missed."
2. **Earlier access**: Premium gets deals 30 minutes sooner -- and the best deals sell out within hours.
3. **Mistake fares**: The most exciting deals are premium-only. Free users hear about them after they're gone.
4. **Social proof/word of mouth**: 44% of Going subscribers came from word of mouth. The "I just saved $800" story is the ultimate conversion tool.

**Revenue data confirms this works:** Going hit $10.8M revenue in 2025 with ~2M members. If ~10% convert at $49/year, that's roughly 220K paying subscribers -- a strong conversion rate for freemium.

---

## Personalization Approaches

| Competitor | Personalization Method | Granularity |
|---|---|---|
| **Going** | Departure airports (5-unlimited) + destination watchlist + cabin class filter | Airport-level + destination-level |
| **Thrifty Traveler** | Departure airports (200+) + cabin class + "All Cities" toggle | Airport-level |
| **Matt's Flights** | Region-based (Northeast, Southeast, etc.) | Region-level |
| **Dollar Flight Club** | Departure airports (up to 4) + dream destinations (up to 10) | Airport-level + destination-level |
| **FareDrop** | Departure airports (up to 10) + destination preferences | Airport-level |
| **Google Flights** | Natural language + AI ("beach getaway in March") | Intent-level (2025 AI feature) |

### Key Insight: Region-Level Is Fine for MVP

Matt's Flights succeeds with region-level personalization. Going started with airport-level. The key is that personalization reduces noise -- it's not a value-add in itself, it's a noise-reducer.

**Implication for Detty:** Starting with origin regions (New England, Mid-Atlantic, South/Texas, Atlanta hub) + destination regions (West Africa, Central Africa, later East/Southern/North Africa) is the right granularity. Airport-level can come later.

---

## Table Stakes

Features users expect. Missing = product feels incomplete or untrustworthy.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| **Deal quality threshold (not every price drop)** | Users hate being notified of $10 fluctuations. Every competitor filters for meaningful deals only. | Low | None | Already built -- 3-tier system (Good/Great/WOW) |
| **Deduplication / cooldown** | Getting the same deal twice is the #1 complaint about flight alert services. | Low | None | Already built -- `seen_deals.json` with 14-day expiry |
| **Clear booking path ("How to Book")** | Users must be able to act on deals instantly. Every competitor links to Google Flights or airline sites. | Low | None | Already built -- Google Flights deep links |
| **Mobile-friendly email** | 70%+ of deal emails are opened on mobile. Broken formatting = missed deals. | Low | None | Already built -- responsive HTML email |
| **Unsubscribe mechanism** | Legal requirement (CAN-SPAM) and trust signal. | Low | None | Already built -- mailto: unsubscribe |
| **Deal expiration awareness** | Users need to know how long a deal might last. "Book within 24 hours" vs "Available for 2 weeks." | Low | Price monitoring frequency | Not built yet. Matt's Flights includes "how long deal will last" estimate in every email. Detty should add this. |
| **Multi-origin support** | Diaspora is spread across US. Showing deals from only one airport is useless. | Low | None | Already built -- 7 US origin airports |
| **Grouped alerts (not one email per deal)** | Getting 17 separate emails is terrible UX. Going and Thrifty batch deals into digest emails. | Low | None | Already built -- grouped by tier then destination |
| **Price comparison to normal** | Users need context. "$650 to Lagos" means nothing without knowing normal is $1,200. | Low | Baseline price data | Already built -- shows "From $650 ~~$1,200~~" |
| **Mistake fare monitoring** | Every serious deal service monitors for pricing errors. It's expected by deal-savvy users. | Medium | RSS feeds or own detection | Already built (RSS) -- own detection is the upgrade |
| **Free tier with real value** | Users won't pay without trying. Every competitor offers a free tier with genuinely useful (not just teaser) deals. | Low | Tier logic | Not built yet (currently all users get everything). Critical for freemium launch. |

---

## Differentiators

Features that set Detty apart. Not expected, but highly valued.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---|---|---|---|---|
| **Africa-first route coverage (77+ routes)** | No competitor monitors 77+ Africa routes continuously. Going does 2-3 Africa deals/month. Detty scans all 77 daily. This is THE wedge. | Low | Already built | **Core differentiator.** Protect and expand this. |
| **Own mistake fare detection (anomaly-based)** | Instead of waiting for Secret Flying RSS to publish, detect pricing anomalies directly from price data. Could beat deal blogs by hours. | High | Price history database, statistical model, higher monitoring frequency | Not built. Requires historical baseline data (currently logging to `price_history.jsonl`). Most impactful feature for competitive moat. |
| **Detty December early warning system** | Dedicated monitoring for Detty December routes starting 6-10 months before (March-June). "Book your December trip now while prices are normal." This is deeply cultural -- no general service understands this. | Medium | Seasonal pricing models, cultural calendar awareness | Not built. CNN and Nigerian press confirm prices double by August. A "Detty December Countdown" feature would resonate powerfully with the diaspora. |
| **Business/First class Africa deals** | Going charges $199/year (Elite) for business class deals. No one does business class for Africa specifically. Nigerian/Ghanaian diaspora professionals regularly fly business on routes like JFK-LOS. | Medium | Cabin class in search queries (fast-flights supports this), separate thresholds | Not built. Going Elite is $199/year vs Detty potential at $5-10/month -- price advantage plus Africa specialization. |
| **Tier-escalation alerts with price-normalized reset** | Only notify when price crosses into a new tier (Good -> Great -> WOW), not for minor fluctuations. Reset alert cycle when price returns to normal range. Smarter than any competitor's simple "price dropped" logic. | Medium | Price tracking state machine | Partially built -- current tier-based dedup. Needs "return to normal" reset logic. |
| **Expired deal teasers for free tier** | "Last week, Premium members saved $800 on JFK-Lagos. Here's what you missed." Proven FOMO-driven conversion trigger. Going does this implicitly; Detty can do it explicitly. | Low | Deal archival, free/premium tier separation | Not built. Low effort, high conversion impact. Strongest psychological lever for free-to-paid. |
| **Regional diaspora personalization** | Origin: "New England" / "DMV" / "Atlanta" / "Texas-Triangle." Destination: "West Africa" / "Central Africa." Uses cultural community groupings, not just airport codes. | Medium | Subscriber preference storage, route filtering | Not built. Matt's Flights validates that region-level works. Using diaspora community names (e.g., "DMV" not "IAD/DCA/BWI") adds cultural resonance. |
| **Pidgin tier names** | "Na Wa!" (WOW), "E Sweet!" (Great), "No Wahala" (Good), "OMO!" (Mistake fare). Cultural identity embedded in the product. No general service would ever do this. | Low | None -- just naming | Already partially done ("OMO!" for mistake fares). Expand to all tiers. This is brand identity, not just a feature. |
| **Booking confirmation feedback loop** | "I booked this deal" button in emails. Tracks "Deals Caught" (north star metric). Enables social proof ("247 people booked this deal"). | Low | Google Forms or simple API endpoint | Already built (Google Forms link). Needs tracking/counting for social proof. |
| **Multi-channel alerts (email + WhatsApp/SMS for urgency)** | Mistake fares last minutes to hours. Email is too slow. Secret Flying uses WhatsApp for error fares. Thrifty Traveler uses SMS for time-sensitive deals. | Medium | WhatsApp Business API or Twilio SMS integration | Not built. WhatsApp is culturally dominant in Nigerian/Ghanaian diaspora. This is both a differentiator AND culturally appropriate. |

---

## Anti-Features

Features to explicitly NOT build. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| **Web app for browsing deals** | Deals are time-sensitive push notifications, not browse-at-your-leisure content. Going built a web app but emails remain the core product. Building a web app before nailing email delivery is a distraction. | Stay email-first. If needed, a simple deal archive page (static HTML generated from deal history) is sufficient. |
| **Price prediction ("Should I buy now or wait?")** | Hopper's model requires processing 300 billion prices/month with 5+ years of history. Detty has weeks of data on niche routes. Any prediction would be unreliable and damage trust. | Instead, provide context: "This is 42% below the average price we've seen" and let users decide. Historical context, not prediction. |
| **OTA/booking integration** | Dollar Flight Club, Going, and Matt's Flights all link to Google Flights or airline sites. None of them are OTAs. Becoming a booking engine adds regulatory, liability, and technical complexity. Hopper's OTA model requires $850M in revenue to sustain. | Always link to Google Flights or airline direct. Simpler, more trustworthy, no payment processing. |
| **Points/Miles deal tracking** | Requires deep knowledge of loyalty program award charts, transfer partners, and availability windows. Thrifty Traveler has an entire team dedicated to this. It's a different product. | Defer entirely. If Africa award availability is requested, consider a partnership or phase 3+ feature. |
| **Granular airport-level personalization (phase 1)** | Adds subscriber preference complexity (storage, UI, filtering) without proportional value. Matt's Flights proves regions work. | Start with regions. Upgrade to airport-level only when subscriber count warrants it (200+ subscribers). |
| **Mobile app** | Going built one in 2024 after 9 years and $10M revenue. Email + web is sufficient for early stage. App development is expensive and distracting. | Responsive email + responsive landing page. Consider PWA only if push notifications become critical. |
| **UK/EU origins in v1** | Doubles the monitoring scope (14 origin airports instead of 7 = 154 routes). UK/EU diaspora is a real market but spreading too thin kills quality. | Focus on US-only. Track UK/EU interest via waitlist. Expand after US proves out. |
| **Automated payment/billing in v1** | Payment infrastructure (Stripe, subscription management, dunning) is complex. With 4 subscribers, it's premature. | Collect $5/month manually (Venmo/Zelle/CashApp) during beta. Build billing when crossing ~50 paying subscribers. |
| **Hotel/accommodation deals** | Different data sources, different pricing dynamics, different competitive landscape. Scope creep that dilutes the flight deal value prop. | Flights only. Period. If subscribers ask for hotels, partner with a hotel deal service. |

---

## Africa-Specific Opportunities

Features that competitors can't or don't do, creating a structural competitive advantage.

| Opportunity | Why Competitors Can't/Don't | Feasibility | Impact |
|---|---|---|---|
| **Detty December pricing intelligence** | No general service understands the cultural phenomenon of Detty December. CNN coverage confirms prices spike 2x by August. Detty can provide "Detty December Booking Window" alerts starting in March. | MEDIUM -- requires seasonal pricing model and cultural calendar integration | HIGH -- directly addresses the most expensive and emotional travel event for the diaspora |
| **West African airline monitoring** | Air Peace, Africa World Airlines, ASKY, ValueJet -- these carriers aren't in GDS/Amadeus Self-Service (which excludes some carriers). They're invisible to Going/Thrifty. Detty can scrape or monitor their sites directly. | HIGH -- requires custom scrapers for each airline | MEDIUM -- these airlines sometimes offer deals that never appear on Google Flights |
| **Visa timing coordination** | Many Africa destinations require visas with 2-8 week processing times. A deal alert is useless if you can't get a visa in time. No deal service considers visa requirements. | LOW -- static data, just add to deal context | MEDIUM -- practical value that shows deep understanding of the Africa travel workflow |
| **Cultural event calendar awareness** | Detty December, Year of Return (Ghana), Homecoming festivals, Eid, Easter -- these drive diaspora travel. Alert timing should anticipate demand spikes, not just react to prices. | LOW -- curated calendar data | HIGH -- transforms from generic deal finder to culturally intelligent travel companion |
| **Multi-city Africa itinerary deals** | "Fly into Lagos, out of Accra" -- common diaspora pattern (visit Nigeria then Ghana). Open-jaw and multi-city pricing can be cheaper but no deal service monitors for this. | HIGH -- requires combinatorial search across routes | MEDIUM -- high value for power travelers, but complex to implement |
| **Baggage allowance context** | Africa flights typically require extra luggage (gifts, supplies for family). Royal Air Maroc, Ethiopian, and Turkish are known for generous allowances. This context matters for deal comparison. | LOW -- static data, add to deal display | LOW-MEDIUM -- nice-to-have context, not a deal-breaker |
| **West African Pidgin / cultural voice** | "Na Wa!" instead of "WOW." "Chop life" in the copy. No mainstream service would ever adopt this voice because it alienates their general audience. For Detty, it's brand identity. | LOW -- just copywriting | HIGH -- creates emotional connection and shareability. Word of mouth is #1 acquisition channel for Going (44% of subscribers). Cultural voice amplifies this for diaspora. |
| **Diaspora hub intelligence** | US cities with largest Nigerian/Ghanaian/etc. communities (Houston, Atlanta, DMV, NYC). Tailor marketing and deal emphasis to where the diaspora actually lives, not just airport proximity. | LOW -- demographic research | MEDIUM -- improves targeting and community building |
| **Group booking deal detection** | Diaspora often travels in family groups (3-6 people). Price for 4 adults is different from 1 adult x4. No deal service considers group pricing. | MEDIUM -- multiplied API queries | LOW-MEDIUM -- edge case but high value when relevant |

---

## Feature Dependencies

```
[Price History Database] -----> [Anomaly-Based Mistake Fare Detection]
         |                                    |
         v                                    v
[Historical Baselines] -----> [Dynamic Deal Thresholds]
         |                           |
         v                           v
[Seasonal Pricing Model] --> [Detty December Early Warning]

[Subscriber Preference Storage] -----> [Free/Premium Tier Separation]
              |                                   |
              v                                   v
[Regional Personalization] -----> [Expired Deal Teasers]
                                         |
                                         v
                                  [Conversion Funnel]

[Higher Monitoring Frequency] -----> [Own Mistake Fare Detection]
         |                                    |
         v                                    v
[Amadeus API Integration] -----> [Beat Deal Blogs on Speed]
         |
         v
[Business Class Monitoring]

[Email Infrastructure Upgrade] -----> [Multi-channel Alerts (WhatsApp/SMS)]
         |                                         |
         v                                         v
[Scale Beyond 200 Subscribers] -----> [Premium Tier Delivery]
```

---

## Next Milestone Recommendation

Based on this research, the features for the next milestone should be ordered by this priority:

### Phase 1: Deal Discovery Upgrade (Foundation)
- Amadeus API integration for priority routes
- Higher-frequency monitoring (2-hour cycles for top routes)
- Price history database (move from JSONL to structured storage)
- **Rationale:** Everything else depends on better data. Can't do anomaly detection without history. Can't beat deal blogs without speed.

### Phase 2: Freemium Infrastructure
- Free/Premium tier separation
- Expired deal teasers for free tier
- Deal expiration estimates in emails
- **Rationale:** Revenue enables everything else. This is the conversion machine.

### Phase 3: Anomaly Detection + Speed
- Statistical anomaly detection on price history
- Own mistake fare detection (beat RSS by hours)
- Tier-escalation with price-normalized reset
- **Rationale:** This is the competitive moat. Once built, Detty finds Africa deals before anyone else.

### Phase 4: Africa-Specific Intelligence
- Detty December early warning system
- Business/First class monitoring
- Cultural event calendar integration
- Multi-channel alerts (WhatsApp for urgent deals)
- **Rationale:** These features make Detty irreplaceable for the Africa diaspora. No general service can replicate this.

### Phase 5: Personalization + Scale
- Regional origin/destination preferences
- Subscriber management upgrade (beyond Google Sheets)
- Email delivery infrastructure (beyond Gmail SMTP)
- **Rationale:** Only needed when subscriber base outgrows current infrastructure (~200+ subscribers).

---

## Sources

### Competitor Research
- [Going.com Membership Guide](https://www.going.com/guides/membership-guide) -- MEDIUM confidence (official source)
- [Going.com Elite Membership](https://www.going.com/elite) -- MEDIUM confidence (official source)
- [Going Revenue Data via Latka](https://getlatka.com/companies/app.going.com) -- LOW confidence (third-party estimate)
- [Going Growth Strategy via Indie Hackers](https://www.indiehackers.com/interview/scotts-cheap-flights-from-small-side-project-to-booming-business-de62ca54b1) -- MEDIUM confidence (founder interview)
- [Secret Flying Wikipedia](https://en.wikipedia.org/wiki/Secret_Flying) -- MEDIUM confidence
- [Hopper Price Predictions](https://help.hopper.com/en_us/about-our-price-predictions-Hy7cLt_Fv) -- HIGH confidence (official)
- [Hopper Revenue/Statistics](https://www.businessofapps.com/data/hopper-statistics/) -- MEDIUM confidence
- [FareDrop/Daily Drop Pro Review](https://www.reclaimsaturday.com/post/an-in-depth-review-of-faredrop-the-ultimate-ai-tool-for-maximizing-travel-savings) -- LOW confidence (single review)
- [Matt's Flights Review](https://www.pilotplans.com/blog/matts-flights-review) -- MEDIUM confidence (independent review)
- [Thrifty Traveler 2025 Wrapped](https://thriftytraveler.com/deals/flights/year-in-flight-deals/) -- HIGH confidence (official)
- [Dollar Flight Club vs Thrifty Traveler](https://thepointsparty.com/articles/thrifty-traveler-vs-dollar-flight-club) -- LOW confidence

### Technical / Data Sources
- [Amadeus Self-Service Pricing](https://developers.amadeus.com/pricing) -- HIGH confidence (official)
- [Amadeus Flight Cheapest Date Search API](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-cheapest-date-search) -- HIGH confidence (official)
- [Amadeus Rate Limits](https://developers.amadeus.com/self-service/apis-docs/guides/developer-guides/api-rate-limits/) -- HIGH confidence (official)
- [GDS/ATPCO Cost Discussion (Hacker News)](https://news.ycombinator.com/item?id=12736433) -- LOW confidence (community discussion, but specific numbers are plausible)
- [fast-flights on PyPI](https://pypi.org/project/fast-flights/) -- HIGH confidence (official package)

### Africa-Specific Context
- [Detty December 2025 Flight Price Surge (Naija247News)](https://naija247news.com/detty-december-2025-flight-prices-skyrocket-nigerians-abroad-struggle-to-return-home/) -- MEDIUM confidence
- [Detty December CNN Coverage](https://edition.cnn.com/2025/12/19/travel/detty-december-nigeria-party-problems) -- HIGH confidence (major news source)
- [Why Intra-African Flights Are Expensive](https://emergingmarkets.today/intra-african-flight-costs/) -- MEDIUM confidence
- [Nigeria Airfares Higher Than Peers (BusinessDay)](https://businessday.ng/aviation/article/explainer-why-airfares-from-nigeria-are-higher-than-african-peers/) -- MEDIUM confidence
- [Lagos-Accra Route Competition (Aviation Metric)](https://aviationmetric.com/lagos-accra-route-market-cannibalisation/) -- MEDIUM confidence
- [Best US-West Africa Flights 2025 (ASAPtickets)](https://blog.asaptickets.com/best-flights-from-the-u-s-to-west-africa-routes-airlines-deals/) -- LOW confidence

### Conversion & Psychology
- [FOMO Marketing Strategies](https://www.cozmoslabs.com/fomo-marketing-strategies/) -- LOW confidence (general marketing)
- [Free to Paid Conversion Strategy (UserPilot)](https://userpilot.com/blog/free-to-paid-conversion-strategy/) -- MEDIUM confidence
- [Flight Deal Services Comparative Analysis (MightyTravels)](https://www.mightytravels.com/2024/09/flight-deal-alert-services-a-comparative-analysis-of-features-and-value/) -- MEDIUM confidence
