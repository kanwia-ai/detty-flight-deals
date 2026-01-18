# Detty Flight Deals - Product Strategy

**Date:** January 18, 2026
**Phase:** Strategy
**Status:** Complete

---

## 1. Target Personas

### Primary Persona: "The December Diaspora"

**Name:** Adaeze ("Ada")
**Demographics:**
- 32 years old, Product Manager in NYC
- Nigerian-American, family in Lagos
- Household income: $150K
- Travels to Nigeria 1-2x/year

**Behavior:**
- MUST travel home for December (weddings, family, Detty December)
- Books 3-6 months in advance to get decent prices
- Monitors Google Flights manually, sets alerts for specific dates
- In 3 WhatsApp groups where people share deals
- Has gotten burned paying $1,800 when her cousin got $900 a week earlier

**Pain Points:**
1. "I know deals exist, but I can never catch them in time"
2. "The good prices are always for dates I can't travel"
3. "I don't know if I'm getting a good deal or not - no benchmark"
4. "December is always expensive, but HOW expensive varies wildly"

**Jobs to be Done:**
- Help me travel home for December without overpaying
- Tell me WHEN to book for the best price
- Alert me immediately if a deal appears for my routes

**Quote:** *"I'm not trying to be cheap - I just don't want to feel stupid paying double what my friend paid."*

---

### Secondary Persona: "The Opportunistic Explorer"

**Name:** Kwame
**Demographics:**
- 28 years old, Software Engineer in Atlanta
- Ghanaian-American, extended family across West Africa
- Single, flexible schedule, remote work
- Travels 3-4x/year for leisure + family

**Behavior:**
- Flexible on dates AND destinations
- "If Lagos is $600, I'll go. If Accra is $500, I'll go there instead."
- Follows Secret Flying, The Points Guy on Twitter
- Has booked mistake fares before
- Willing to book within 24-48 hours if deal is good

**Pain Points:**
1. "I have to check 10 different sites every day"
2. "By the time I see a deal on Twitter, it's gone"
3. "Most deal sites don't cover African destinations"
4. "I miss deals to places I would've gone if I'd known"

**Jobs to be Done:**
- Show me any amazing deal to Africa - I'll figure out the rest
- Be faster than Twitter
- Don't waste my time with mediocre "deals"

**Quote:** *"I've never paid more than $700 to fly to West Africa. I just wait for the right deal."*

---

### Anti-Persona: "The Luxury Traveler"

**Who we're NOT building for:**
- Business class buyers not price-sensitive
- One-time travelers with no ongoing need
- People who need full-service travel planning (hotels, visas, itineraries)

---

## 2. Positioning Statement

Using April Dunford's positioning framework:

### Competitive Alternatives
What would customers do if Detty Flight Deals didn't exist?

1. Set Google Flights alerts for specific date pairs (limited, reactive)
2. Subscribe to Going/Scott's (Africa is afterthought, tourist destinations)
3. Follow Secret Flying/Twitter accounts (manual monitoring, lag time)
4. Rely on WhatsApp group word-of-mouth (inconsistent, often too late)
5. Just pay whatever price they find (expensive, frustrating)

### Unique Attributes
What do we do that alternatives can't/don't?

1. **Africa-first coverage** - Every major diaspora destination, not just tourist spots
2. **Flexible date monitoring** - "Watch Lagos for 6 months" not "Watch Lagos on Dec 20-Jan 3"
3. **Speed** - 30-minute checks for mistake fares, not daily newsletters
4. **Diaspora price benchmarks** - "This is 40% below normal for Lagos in December"
5. **Both modes** - Serve opportunists AND peak-time optimizers

### Value (with proof)
What value do these attributes enable?

| Attribute | Value | Proof Point |
|-----------|-------|-------------|
| Africa-first | Relevant deals, not noise | 21 routes vs. 2-3 Africa deals/month from Going |
| Flexible monitoring | Never miss a deal for your routes | Scans every week for 6 months ahead |
| Speed | Catch mistake fares before they expire | 30-min monitoring vs. daily digest |
| Price benchmarks | Confidence in booking decisions | Historical data shows this is a good deal |
| Both modes | One tool for all diaspora travel | Switch between "show me anything" and "I need December" |

### Target Market Characteristics
Who cares a lot about what we do?

**Must have:**
- African diaspora in US (initially)
- Travels to Africa 1+ times per year
- Price-conscious but values convenience
- Has smartphone and email

**Nice to have:**
- Date flexibility
- Multiple destinations of interest
- Active in diaspora community (amplifies word of mouth)

### Market Category
How do we frame what we are?

**Options considered:**

| Category | Pros | Cons |
|----------|------|------|
| "Flight deal service" | Familiar | Commodity, compared to Going |
| "Africa travel platform" | Aspirational | Too broad, overpromises |
| "Diaspora travel tool" | Specific, differentiated | May limit perceived scope |
| "Personal flight radar for Africa" | Unique, memorable | Needs explanation |

**Recommended:** **"Personal flight radar for Africa"**

This frames us as:
- Personal (customized to YOUR routes)
- Flight radar (always watching, alerts you)
- For Africa (clear geographic focus)

---

### Positioning Statement

> **For African diaspora travelers in the US** who want to visit home without overpaying, **Detty Flight Deals** is a **personal flight radar** that **watches your routes and alerts you when deals hit**. Unlike Going or Google Flights alerts, **we focus exclusively on Africa, monitor flexible date ranges, and catch deals in real-time** - so you never miss a flight home.

---

## 3. North Star Metric

### Choosing the North Star

Using Lenny's framework, the North Star should:
1. Reflect value delivered to customers
2. Be a leading indicator of revenue
3. Be actionable by the team

**Options considered:**

| Metric | Pros | Cons |
|--------|------|------|
| Deals sent | Easy to measure | Doesn't reflect quality or user value |
| Deals opened | Shows engagement | Doesn't mean user got value |
| Deals booked | Perfect value signal | Hard to track (booking happens elsewhere) |
| $ saved by users | Ultimate value | Very hard to measure accurately |
| Active watchers | Shows retained value | Vanity metric if they never get deals |

### Recommended North Star

**"Deals Caught"** = Number of deals that users acted on within the deal window

**Definition:** User received alert → User clicked through → Deal was still available

**Why this works:**
- Measures speed (we caught it in time)
- Measures relevance (user wanted it enough to click)
- Measures quality (deal was real, not expired)
- Proxy for bookings without needing to track actual purchases

### Supporting Input Metrics

| Metric | What it measures | Target |
|--------|------------------|--------|
| **Alert-to-click rate** | Relevance of deals sent | >20% |
| **Time to alert** | Speed of our system | <30 min from deal appearing |
| **Deal availability at click** | Catching deals before expiry | >80% |
| **Routes monitored per user** | Engagement/setup completion | 3+ |
| **Weekly active users** | Retention | 40%+ of subscribers |

### Health Metrics (Guardrails)

| Metric | Guardrail | Why |
|--------|-----------|-----|
| Alert frequency | 2-5 per week max | Too many = noise, unsubscribes |
| False positive rate | <10% | Bad deals erode trust |
| Unsubscribe rate | <3% monthly | Retention signal |

---

## 4. Strategic Priorities

### Year 1 Focus

**Do:**
1. Nail the core alert experience for US → Africa routes (diaspora + tourist destinations)
2. Build trust through accuracy and speed
3. Grow through diaspora community word-of-mouth
4. Validate willingness to pay

**Don't (Anti-goals):**
1. Don't expand to hotels, visas, or full travel planning
2. Don't build social/community features yet
3. Don't expand to UK/Canada origins until US is solid
4. Don't build a mobile app (email/web is enough for v1)
5. Don't build rewards/points features yet (long-term roadmap)

### Strategic Bets

| Bet | Hypothesis | Validation |
|-----|------------|------------|
| **Speed wins** | Being 30 min faster than competitors creates loyal users | Track deals caught that were gone within 2 hours |
| **Diaspora WOM is powerful** | Community-driven growth > paid acquisition | Measure referral rate, NPS |
| **December is wedge** | Peak season optimization is highest-value feature | Premium tier conversion for December alerts |

---

## 5. Monetization Strategy

### Recommended Model: Freemium

**Free Tier:**
- 1 route monitored
- Daily digest emails
- Standard deals only

**Premium Tier ($49/year):**
- Unlimited routes
- Real-time alerts (within 30 min)
- Mistake fare alerts
- Price history & benchmarks
- "December Deal Optimizer" (when to book for peak season)

### Why Freemium?

1. **Low friction acquisition** - Let people try before paying
2. **Word-of-mouth amplifier** - Free users still share deals
3. **Proven model** - Going does $3.8M ARR at similar price point
4. **Natural upgrade trigger** - Miss one deal, and $49/year feels cheap

### Revenue Projections (Conservative)

| Milestone | Free Users | Premium | ARR |
|-----------|------------|---------|-----|
| Month 6 | 1,000 | 100 | $4,900 |
| Year 1 | 5,000 | 500 | $24,500 |
| Year 2 | 20,000 | 2,500 | $122,500 |

---

## 6. Go-to-Market Strategy

### Launch Channels

| Channel | Why | Effort |
|---------|-----|--------|
| **Nigerian/Ghanaian Twitter** | Highly engaged diaspora community | Low |
| **Diaspora WhatsApp groups** | Where deals already spread | Medium |
| **Reddit (r/Nigeria, r/Ghana)** | Tech-savvy diaspora | Low |
| **Podcasts (Afrobeats, diaspora themes)** | Targeted, trust-building | Medium |
| **Detty December angle** | Timely hook, clear value prop | Low |

### Launch Timing

**Phase 1 - FREE LAUNCH: January 2026 (NOW)**
- Launch free tier immediately to build user base
- Goal: 2,000+ users by September
- Validate product-market fit, iterate on alerts

**Phase 2 - PAID LAUNCH: September 2026**
- Introduce premium tier ($49/year)
- "Get the best December deals" messaging
- Convert free users before peak booking window

### Messaging by Persona

**Ada (December Diaspora):**
> "Never overpay for December flights home again. Detty Flight Deals watches Lagos, Accra, and 20+ African cities so you know exactly when to book."

**Kwame (Opportunist):**
> "I caught a $580 roundtrip to Accra last month. How? Detty Flight Deals pinged me 20 minutes after it went live. Join the radar."

---

## 7. Success Criteria

### Phase 1: Free Launch (Jan-Mar 2026)

| Metric | Target |
|--------|--------|
| Users signed up | 500 |
| Routes being monitored | 1,500 |
| Deals sent | 200 |
| Alert-to-click rate | 15%+ |

### Phase 2: Growth & Iteration (Apr-Aug 2026)

| Metric | Target |
|--------|--------|
| Users signed up | 2,000 |
| Deals caught | 500 |
| NPS | 50+ |
| Email open rate | 40%+ |

### Phase 3: Paid Launch (Sep 2026)

| Metric | Target |
|--------|--------|
| Premium conversions | 200 (10% of free) |
| MRR | $800 |
| Conversion rate | 10%+ |

### Phase 4: Scale (Dec 2026+)

| Metric | Target |
|--------|--------|
| Total users | 10,000 |
| Premium subscribers | 1,000 |
| ARR | $49,000 |
| Deals caught per user/month | 0.5 |

---

## 8. Long-Term Vision (18+ Months)

### Rewards Travel Expansion

The African diaspora often has points/miles but struggles to use them for Africa routes:
- Complex award routing (no direct award availability)
- Multiple airline alliances serve Africa
- Partner availability is opaque

**Future features:**
- Award flight alerts (X points to Lagos on United/Ethiopian)
- Points valuation for Africa routes
- "Best use of your Chase/Amex points for Africa"
- Transfer partner optimization

### Geographic Expansion

**Destination Tiers (by region):**

| Tier | Regions | Cities | Timeline |
|------|---------|--------|----------|
| **Tier 1** | West Africa + Cameroon + DRC | Lagos, Accra, Abuja, Dakar, Freetown, Abidjan, Lomé, Cotonou, Douala, Yaoundé, Kinshasa (11 cities) | Launch |
| **Tier 2** | East Africa | Nairobi, Addis Ababa, Dar es Salaam, Kampala, Kigali | Month 2 |
| **Tier 3** | Southern Africa | Johannesburg, Cape Town, Harare, Lusaka, Victoria Falls | Month 3 |
| **Tier 4** | North Africa | Cairo, Casablanca, Marrakech, Tunis, Algiers | Month 4 |

**US Origins (MVP):**
| Code | City | Metro |
|------|------|-------|
| JFK | New York JFK | New York |
| EWR | Newark | New York |
| IAD | Washington Dulles | Washington DC |
| ATL | Atlanta | Atlanta |
| DFW | Dallas | Dallas |
| IAH | Houston | Houston |
| BOS | Boston | Boston |

**Total Tier 1 Routes:** 77 (7 origins × 11 destinations)

**Long-term vision:** Every commercial airport in Africa with US-originating service.

**Origin Expansion:**
- UK origins (large Nigerian diaspora)
- Canada origins (growing African community)

### Platform Evolution
- Mobile app with push notifications
- Community deal verification
- Travel agent partnerships
- Group booking coordination

---

## 9. Open Questions for PRD Phase

1. **MVP scope:** How many routes for v1? Which origins/destinations?
2. **Alert channels:** Email only? Or SMS/push from day 1?
3. **Price thresholds:** User-defined or system-recommended?
4. **Deal sources:** fast-flights scraping? RSS feeds? Both?
5. **December feature:** How much to invest in peak-season optimization?

---

## Summary

**We're building:** A personal flight radar for the African diaspora

**For:** US-based Africans who travel home 1+ times per year

**Core value prop:** Watch your routes, alert you instantly, never miss a deal home

**North Star:** Deals Caught (alerts that led to clicks while deal was live)

**Monetization:** Freemium ($49/year premium)

**Anti-goals:** No hotels, no mobile app yet, no UK expansion yet, no rewards features yet

**Long-term vision:** Expand to rewards/points travel for Africa routes (underserved market)
