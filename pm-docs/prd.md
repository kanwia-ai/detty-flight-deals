# Detty Flight Deals - Product Requirements Document

**Date:** January 18, 2026
**Phase:** PRD
**Status:** Complete

---

## 1. Overview

### What Exists Today
- `deal_finder.py` - Searches 21 routes (3 US origins × 7 Africa destinations)
- `mistake_fare_monitor.py` - Watches RSS feeds for mistake fares
- Runs on GitHub Actions every 6 hours
- Emails one user (you) when deals are found
- Tracks seen deals to avoid duplicates

### Gap to Launch
The code works. What's missing:
1. **Sign-up mechanism** - Let people subscribe
2. **Landing page** - Explain value prop, capture emails
3. **Multi-user support** - Send alerts to multiple subscribers
4. **Expanded routes** - More destinations (tourist + diaspora cities)

---

## 2. Feature Map

### Pain Points → Features

| Pain Point | Feature | Priority |
|------------|---------|----------|
| "I can never catch deals in time" | Real-time email alerts | P0 |
| "No one covers African destinations" | Africa-focused route coverage | P0 |
| "I have to check 10 sites daily" | Automated monitoring (set and forget) | P0 |
| "I don't know if it's a good deal" | Price context in alerts | P1 |
| "Most deal sites are tourist destinations" | Diaspora city coverage (Lagos, Accra, Abuja, etc.) | P0 |
| "I want tourist destinations too" | Tourist city coverage (Cape Town, Nairobi, Marrakech) | P0 |
| "December is always expensive" | December deal optimizer | P2 (Sept launch) |
| "I missed the deal, it expired" | Faster monitoring (30 min for mistakes) | P1 |
| "I don't know when to book for December" | Booking window recommendations | P2 (Sept launch) |

---

## 3. RICE Scoring

**Scoring criteria:**
- **Reach:** How many users benefit? (1-10)
- **Impact:** How much value for those users? (0.25=minimal, 0.5=low, 1=medium, 2=high, 3=massive)
- **Confidence:** How sure are we? (0.5=low, 0.8=medium, 1=high)
- **Effort:** Person-weeks to build (lower = better)

| Feature | Reach | Impact | Confidence | Effort | RICE Score |
|---------|-------|--------|------------|--------|------------|
| **Landing page + email signup** | 10 | 3 | 1 | 1 | 30 |
| **Multi-user email delivery** | 10 | 3 | 1 | 1 | 30 |
| **Expanded destinations (15→30)** | 8 | 2 | 0.8 | 1 | 12.8 |
| **Price context in alerts** | 8 | 1 | 0.8 | 0.5 | 12.8 |
| **Mistake fare monitor (faster)** | 5 | 2 | 0.8 | 1 | 8 |
| **User-defined routes** | 6 | 2 | 0.8 | 3 | 3.2 |
| **December deal optimizer** | 4 | 2 | 0.5 | 2 | 2 |
| **SMS/push notifications** | 4 | 1 | 0.5 | 2 | 1 |
| **Price history charts** | 3 | 1 | 0.5 | 2 | 0.75 |

---

## 4. MVP Scope (January Launch)

### Launch Goal
**Ship a free product that people can sign up for within 2 weeks.**

### MVP Features (P0)

#### 1. Landing Page
**What:** Single page explaining value prop with email signup form

**Requirements:**
- Hero: "Never miss a cheap flight to Africa"
- Value props (3 bullets): Speed, Africa-focus, Set-and-forget
- Email signup form (Buttondown, ConvertKit, or simple form → Google Sheet)
- Social proof placeholder (update as you get testimonials)

**Acceptance criteria:**
- [ ] Page loads in <3s
- [ ] Email signup works
- [ ] Mobile responsive

**Effort:** 1-2 days

---

#### 2. Email Collection & Delivery
**What:** Collect subscriber emails, send deals to all subscribers

**Options:**

| Option | Pros | Cons | Effort |
|--------|------|------|--------|
| **Google Sheet + Script** | Free, simple | Manual, fragile | 1 day |
| **Buttondown** | Free tier (100 subs), built-in delivery | Limited customization | 0.5 days |
| **ConvertKit** | Free tier (1000 subs), landing pages | Overkill for MVP | 0.5 days |
| **Loops** | Modern, developer-friendly | Paid after 1000 | 0.5 days |

**Recommendation:** Buttondown or ConvertKit
- Free tier is sufficient for MVP
- Built-in email delivery
- Easy signup forms
- Can export list later if needed

**Acceptance criteria:**
- [ ] Users can sign up via landing page
- [ ] Deal alerts go to all subscribers
- [ ] Unsubscribe link works

**Effort:** 0.5-1 day

---

#### 3. Tier 1 Route Coverage (West Africa + Cameroon + DRC)
**What:** Launch with comprehensive West Africa + Cameroon + DRC coverage

**Current (7 destinations):**
Lagos, Accra, Dakar, Abuja, Douala, Yaounde, Kinshasa

**Tier 1 Launch (11 destinations):**

| Country | Cities | Airport Codes |
|---------|--------|---------------|
| Nigeria | Lagos, Abuja | LOS, ABV |
| Ghana | Accra | ACC |
| Senegal | Dakar | DSS |
| Sierra Leone | Freetown | FNA |
| Ivory Coast | Abidjan | ABJ |
| Togo | Lomé | LFW |
| Benin | Cotonou | COO |
| Cameroon | Douala, Yaoundé | DLA, NSI |
| DRC | Kinshasa | FIH |

**Origins (7 cities):**
| Code | City | Metro |
|------|------|-------|
| JFK | New York JFK | New York |
| EWR | Newark | New York |
| IAD | Washington Dulles | Washington DC |
| ATL | Atlanta | Atlanta |
| DFW | Dallas | Dallas |
| IAH | Houston | Houston |
| BOS | Boston | Boston |

**Total:** 7 origins × 11 destinations = **77 routes**

**Future Tiers:**
- Tier 2 (Month 2): East Africa - Nairobi, Addis Ababa, Dar es Salaam, Kampala, Kigali
- Tier 3 (Month 3): Southern Africa - Johannesburg, Cape Town, Harare, Lusaka, Victoria Falls
- Tier 4 (Month 4): North Africa - Cairo, Casablanca, Marrakech, Tunis, Algiers
- Long-term: Every commercial airport in Africa

**Acceptance criteria:**
- [ ] 11 Tier 1 destinations covered
- [ ] Price thresholds set for each route (see pricing-tiers.md)
- [ ] 7 US origins (JFK, EWR, IAD, ATL, DFW, IAH, BOS)
- [ ] 77 total routes monitored

**Effort:** 0.5 days (config changes + threshold research)

---

#### 4. Better Alert Emails
**What:** Make deal emails compelling and actionable

**Current:** Plain text with basic info

**Improved:**
```
🔥 DEAL: JFK → Lagos $589 round-trip

This is 35% below normal ($900 average)
Best dates: Mar 15 - Mar 25, 2026

[Book Now on Google Flights]

Why this is good:
• Lowest price we've seen in 3 months
• 10-day trip, perfect length
• Direct on Delta available

—
You're getting this because you signed up for Detty Flight Deals.
[Unsubscribe] | [View all current deals]
```

**Acceptance criteria:**
- [ ] Price context (% below normal, comparison)
- [ ] Clear CTA (Book Now button/link)
- [ ] Mobile-friendly formatting
- [ ] Unsubscribe link

**Effort:** 0.5 days

---

### MVP Summary

| Feature | Effort | Status |
|---------|--------|--------|
| Landing page | 1-2 days | TODO |
| Email signup (Buttondown/ConvertKit) | 0.5 days | TODO |
| Tier 1 routes (77 routes) | 0.5 days | TODO |
| Better alert emails | 0.5 days | TODO |
| **Total** | **3-4 days** | |

---

## 5. Post-MVP Features (Feb-Aug 2026)

### P1 Features (Before Paid Launch)

#### User-Defined Routes
Let users pick their origins and destinations instead of getting all alerts.

**Implementation:**
- Simple preference form after signup
- Store preferences in database (Supabase free tier)
- Filter alerts based on user prefs

**Effort:** 1-2 weeks

---

#### Faster Mistake Fare Alerts
Current: Every 6 hours
Target: Every 30 minutes for mistake fares

**Implementation:**
- Separate GitHub Action for mistake fare RSS feeds
- Run every 30 min (still within free tier)
- Immediate email when mistake fare detected

**Effort:** 1-2 days

---

#### Price History & Benchmarks
Show users whether a price is actually good.

**Implementation:**
- Store all prices found (Supabase/Postgres)
- Calculate rolling averages
- Show "X% below average" in alerts

**Effort:** 1 week

---

### P2 Features (September Paid Launch)

#### Premium Tier
- Unlimited routes (free = 3 routes)
- Real-time alerts (free = daily digest)
- Mistake fare alerts (premium only)
- December Deal Optimizer

**Effort:** 2-3 weeks (payment integration, access control)

---

#### December Deal Optimizer
"When should I book for December travel?"

**Features:**
- Historical December pricing data
- "Book now" vs "Wait" recommendations
- Price drop alerts for specific December dates

**Effort:** 2 weeks

---

## 6. Now / Next / Later Roadmap

### NOW (January 2026) - Free Launch MVP
| Feature | Owner | Status |
|---------|-------|--------|
| Landing page | You | TODO |
| Email signup (Buttondown) | You | TODO |
| Tier 1 routes (77 routes: 7 origins × 11 destinations) | You | TODO |
| Improve alert email format | You | TODO |
| **Launch publicly** | You | Target: Jan 25 |

### NEXT (Feb-Aug 2026) - Growth & Iteration
| Feature | Priority | Effort |
|---------|----------|--------|
| **Tier 2: East Africa** (Nairobi, Addis, Dar, Kampala, Kigali) | P0 | 0.5 days |
| **Tier 3: Southern Africa** (Joburg, Cape Town, Harare, Lusaka) | P0 | 0.5 days |
| **Tier 4: North Africa** (Cairo, Casablanca, Marrakech, Tunis) | P0 | 0.5 days |
| User-defined route preferences | P1 | 1-2 weeks |
| Faster mistake fare alerts (30 min) | P1 | 1-2 days |
| Price history & benchmarks | P1 | 1 week |
| Analytics (open rates, clicks) | P1 | 1-2 days |
| More US origins (LAX, ORD, DFW) | P1 | 0.5 days |
| UK origins (LHR, LGW) | P1 | 1 day |

### LATER (Sep 2026+) - Monetization
| Feature | Priority | Effort |
|---------|----------|--------|
| Premium tier ($49/year) | P0 | 2-3 weeks |
| Payment integration (Stripe) | P0 | 1 week |
| December Deal Optimizer | P1 | 2 weeks |
| SMS/push notifications | P2 | 2 weeks |
| Mobile app | P3 | 2-3 months |

### FUTURE (2027+) - Platform Expansion
| Feature | Notes |
|---------|-------|
| Rewards/points travel alerts | Award availability for Africa routes |
| UK/Canada expansion | Large diaspora populations |
| Community deal sharing | Crowdsourced verification |
| Hotel deals | Detty December packages |
| Travel agent partnerships | Concierge booking service |

---

## 7. Technical Architecture (MVP)

### Current Stack
```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Free)                     │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ deal_finder.py  │    │ mistake_fare.py │                │
│  │  (every 6 hrs)  │    │  (every 30 min) │                │
│  └────────┬────────┘    └────────┬────────┘                │
│           │                      │                          │
│           └──────────┬───────────┘                          │
│                      ▼                                      │
│            ┌─────────────────┐                              │
│            │   Gmail SMTP    │                              │
│            │  (send alerts)  │                              │
│            └────────┬────────┘                              │
│                     │                                       │
└─────────────────────┼───────────────────────────────────────┘
                      ▼
              ┌─────────────────┐
              │   Your inbox    │
              └─────────────────┘
```

### MVP Stack (Multi-user)
```
┌─────────────────────────────────────────────────────────────┐
│                        Landing Page                          │
│                    (Vercel/Netlify - Free)                  │
│                            │                                │
│                            ▼                                │
│                  ┌─────────────────┐                        │
│                  │   Buttondown    │                        │
│                  │  (email list)   │                        │
│                  └─────────────────┘                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Free)                     │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ deal_finder.py  │    │ mistake_fare.py │                │
│  └────────┬────────┘    └────────┬────────┘                │
│           │                      │                          │
│           └──────────┬───────────┘                          │
│                      ▼                                      │
│         ┌────────────────────────┐                          │
│         │  Buttondown API        │                          │
│         │  (broadcast to list)   │                          │
│         └────────────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### Cost Estimate (MVP)
| Service | Free Tier | Paid Threshold |
|---------|-----------|----------------|
| GitHub Actions | 2000 min/mo | >2000 min |
| Buttondown | 100 subscribers | >100 subs ($9/mo) |
| Vercel | Unlimited | N/A |
| **Total** | **$0/month** | Until 100+ subs |

---

## 8. Success Metrics (MVP)

### Week 1 (Launch)
| Metric | Target |
|--------|--------|
| Landing page live | ✓ |
| First 50 signups | ✓ |
| First deal alert sent | ✓ |

### Month 1
| Metric | Target |
|--------|--------|
| Total signups | 200 |
| Email open rate | 40%+ |
| Click-through rate | 15%+ |
| Unsubscribe rate | <5% |

### Month 3
| Metric | Target |
|--------|--------|
| Total signups | 500 |
| Deals sent | 50+ |
| Referral signups | 20% |
| NPS (survey) | 50+ |

---

## 9. Launch Checklist

### Pre-Launch (This Week)
- [ ] Choose email provider (Buttondown recommended)
- [ ] Set up email list
- [ ] Build landing page (can be single HTML file)
- [ ] Expand route config to Tier 1 (77 routes: 7 origins × 11 destinations)
- [ ] Research price thresholds for new routes
- [ ] Update email template with better formatting
- [ ] Update deal_finder.py to use Buttondown API
- [ ] Test end-to-end flow

### Launch Day
- [ ] Deploy landing page
- [ ] Post to Nigerian/Ghanaian Twitter
- [ ] Share in 2-3 diaspora WhatsApp groups
- [ ] Post to r/Nigeria, r/Ghana
- [ ] Personal network outreach (10 people)

### Post-Launch (Week 1)
- [ ] Monitor signups
- [ ] Respond to feedback
- [ ] Fix any bugs in alert delivery
- [ ] Send first deal (even if manually triggered)
- [ ] Collect testimonials from first users

---

## 10. Open Questions / Decisions Needed

| Question | Options | Recommendation |
|----------|---------|----------------|
| Email provider? | Buttondown, ConvertKit, Loops | Buttondown (simplest) |
| Landing page hosting? | Vercel, Netlify, GitHub Pages | Vercel (easy deploys) |
| Domain name? | dettyflightdeals.com, getdetty.com, detty.deals | dettyflightdeals.com |
| Launch announcement? | Twitter thread, Reddit post, both | Both + WhatsApp |

---

## Summary

**MVP scope:** Landing page + email signup + Tier 1 routes (77 routes) + better alerts

**Tier 1 coverage:**
- **Destinations (11):** Lagos, Accra, Abuja, Dakar, Freetown, Abidjan, Lomé, Cotonou, Douala, Yaoundé, Kinshasa
- **Origins (7):** JFK, EWR, IAD, ATL, DFW, IAH, BOS
- **Total routes:** 77

**Effort:** 3-4 days of work

**Launch target:** January 25, 2026

**Cost:** $0 until 100+ subscribers

**Path to paid:** Build to 2,000 free users by September, launch premium tier before Detty December 2026

**Long-term vision:** Every commercial airport in Africa
