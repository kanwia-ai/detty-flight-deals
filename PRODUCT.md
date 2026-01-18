# Detty Flight Deals

## The Problem

Flying to Africa from the US is expensive and unpredictable. Round-trip flights to West and Central Africa typically run $1,200-$2,000+, but deals exist - you just have to catch them.

The current options suck:
- **Scott's Cheap Flights / Going**: Great service, but Africa is an afterthought. Most deals are to Europe, Asia, Latin America. When Africa deals do appear, they're often to tourist destinations (Cape Town, Marrakech) not where the diaspora actually needs to go.
- **Google Flights alerts**: Only notify on specific date pairs. Useless when you're flexible and just want "the cheapest time to go to Lagos in the next 6 months."
- **Manual searching**: Time-consuming. By the time you check, the deal is gone.
- **Deal blogs/Twitter**: Require constant monitoring. Easy to miss.

**The gap**: No tool is optimized for the African diaspora traveler who wants to visit family, attend events, or just go home - and is flexible on dates but not on destination.

---

## The Insight

The African diaspora travel pattern is different:

1. **Destination-locked, date-flexible**: "I need to get to Lagos. I don't care when, I care about price."
2. **Longer trips**: Not a 5-day vacation. Usually 10-14+ days to make the long flight worth it.
3. **Specific cities**: Not "anywhere in Africa" - specific cities where family lives (Lagos, Accra, Dakar, Abuja, Douala, Kinshasa, etc.)
4. **Price-sensitive but not cheap**: Willing to pay fair prices, but $1,800 for economy is not fair.
5. **Trust networks**: Deals spread through WhatsApp groups, Twitter, word of mouth. "My cousin got Lagos for $600 last month."

**The opportunity**: Build the tool the diaspora actually needs - one that watches YOUR cities, across ALL dates, and tells you when to book.

---

## What Detty Flight Deals Is

A personal flight radar for Africa.

You tell it:
- Where you fly from (your home airports)
- Where you need to go (your destinations in Africa)
- What you're willing to pay (your price thresholds)

It watches. It waits. When a deal hits, it emails you.

**"Detty"** = Nigerian slang for "lit" / "exciting" / "the moment." Detty December is the annual homecoming when the diaspora floods Lagos for holidays. This tool helps you get there.

---

## Current MVP (What Exists Now)

### Deal Finder
- Searches 21 routes (3 US origins × 7 Africa destinations)
- Checks every week for the next 6 months
- Emails when prices drop below thresholds
- Deduplicates so you only get notified of NEW deals
- Runs every 6 hours on GitHub Actions

### Mistake Fare Monitor
- Watches RSS feeds from deal sites (Secret Flying, The Flight Deal, Fly4Free)
- Filters for Africa destinations
- Only alerts when prices are 25%+ below normal (true mistake fares)
- Runs every 30 minutes

### Current Coverage
| Destination | Threshold | Mistake Fare |
|-------------|-----------|--------------|
| Lagos | $700 | <$525 |
| Accra | $750 | <$562 |
| Dakar | $550 | <$412 |
| Abuja | $800 | <$600 |
| Douala | $900 | <$675 |
| Yaounde | $900 | <$675 |
| Kinshasa | $900 | <$675 |

---

## The Full Vision

### Phase 1: Personal Tool (Current)
- Works for one user (me)
- Hardcoded routes and thresholds
- Email notifications
- GitHub Actions backend

### Phase 2: Multi-User Platform
- User accounts with custom watchlists
- "Watch Lagos from anywhere under $700"
- Multiple notification channels (email, SMS, WhatsApp, push)
- Historical price data ("Lagos averages $850 in March, $650 in September")
- "Best time to book" recommendations

### Phase 3: Community & Intelligence
- Crowdsourced deal verification ("I just booked this!")
- Community deal sharing (like a focused FlyerTalk)
- Airline/route analytics ("Ethiopian has been running LAX-Lagos promos")
- Price prediction ("Prices to Accra typically drop 3 weeks before travel")
- Integration with travel agents who specialize in Africa

### Phase 4: Full Travel Stack
- Hotel deals in destination cities
- Travel logistics (visas, COVID requirements, airport info)
- "Detty December" package planning
- Group booking coordination for family trips
- Travel insurance partnerships

---

## Key Product Principles

### 1. Diaspora-First
Not "Africa travel for tourists." This is for people going HOME. The destinations, the trip lengths, the price expectations - all calibrated for diaspora patterns.

### 2. Flexible Dates, Fixed Destinations
Invert the typical flight search. Don't ask "where can I go on these dates?" Ask "when should I go to THIS place?"

### 3. Signal, Not Noise
Only notify when it matters. A $50 price drop isn't a deal. 25% below normal is a deal. A price you've seen 3 times this week isn't news.

### 4. Speed Matters
Mistake fares last minutes to hours. The tool needs to catch them fast and notify immediately. "I saw it but couldn't book in time" is failure.

### 5. Trust Through Transparency
Show the data. "This is the lowest price to Lagos in 6 months." "Prices have been trending down since October." Let users make informed decisions.

---

## Why This Matters

The African diaspora sends ~$100B in remittances annually. A huge portion of that community wants to visit home but is priced out or overpays.

A $400 savings on a flight is:
- A month of rent in many US cities
- A significant gift to family back home
- The difference between going and not going

This isn't about travel hacking for fun. It's about making it affordable to maintain connections across continents.

---

## Competitive Landscape

| Tool | Strength | Weakness for Diaspora |
|------|----------|----------------------|
| Google Flights | Comprehensive | Date-pair locked, no proactive alerts for flexible searches |
| Scott's/Going | Great deal curation | Africa is afterthought, tourist destinations |
| Hopper | Price prediction | US-centric, limited Africa coverage |
| Skyscanner | Good search | No personalized monitoring |
| Secret Flying | Mistake fares | Manual monitoring, global not Africa-focused |
| Momondo | Price comparison | No alerts, no flexibility |

**Gap**: No tool combines (1) Africa focus, (2) date flexibility, (3) proactive monitoring, (4) diaspora-relevant destinations.

---

## Technical Foundation

### Current Stack
- Python scripts on GitHub Actions (free tier)
- `fast-flights` library (Google Flights scraping)
- `feedparser` for RSS monitoring
- Gmail SMTP for notifications
- JSON file for state (seen deals)

### Scaling Considerations
- GitHub Actions: Free but limited (2,000 min/month). Fine for personal use.
- fast-flights: Scraping is fragile. Google could break it anytime.
- Real scaling needs: proper flight data APIs (Amadeus, Skyscanner, Tequila by Kiwi)
- Database for historical prices and user preferences
- Queue system for real-time mistake fare processing

### Data Sources to Explore
- Amadeus API (official airline data)
- Tequila by Kiwi (aggregator API)
- ITA Matrix (power user tool, hard to automate)
- Direct airline APIs (Ethiopian, Kenya Airways, Royal Air Maroc)
- Deal site APIs/scraping (Secret Flying, etc.)

---

## Open Questions

1. **Monetization**: Subscription? Affiliate links? Free with premium tier?
2. **Scope**: Just flights? Or full travel stack?
3. **Community**: Solo tool or social/shared experience?
4. **Coverage**: West/Central Africa only? Or expand to East Africa, Southern Africa?
5. **Origins**: US only? Or include UK, Canada, Europe (large diaspora populations)?

---

## Success Metrics (Future)

- Deals caught before they expire
- Average savings per user
- Time from deal appearing to user notification
- Booking conversion rate
- User retention (do they keep using it?)
- NPS (would they recommend to family/friends?)

---

## The Name

**Detty** - from Nigerian Pidgin, meaning exciting, lit, the vibe.

**"Detty December"** is the annual phenomenon where diaspora Nigerians flood Lagos for the holidays - concerts, parties, weddings, family reunions. It's become a cultural moment.

Detty Flight Deals = helping you get to the detty moments without paying detty prices.

---

## Summary

Detty Flight Deals is a flight monitoring tool built specifically for the African diaspora. It watches your routes, waits for deals, and alerts you when it's time to book.

The MVP proves the concept works. The vision is a full platform that makes Africa travel affordable and accessible for the millions who want to go home.
