---
phase: 05-freemium-infrastructure
created: 2026-02-10
status: discussed
---

# Phase 5: Freemium Infrastructure — Context & Decisions

## Phase Goal

Build the subscriber tier system so free users get a weekly digest of Great deals for their region, while premium subscribers ($15/quarter) get instant WOW/mistake fare alerts across all origins, SMS for mistake fares, and historical price context.

## Decisions

### 1. Free Tier Digest

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frequency | Weekly roundup | One email per week, not per deal |
| Content | Great deals only | WOW/mistake fares are premium content |
| Route scope | Region-filtered, 1 metro per subscriber | Pick at signup, can change once per month |
| Format | Claude decides during planning | No strong preference on layout |

### 2. FOMO / Conversion Teasers

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Delivery | Embedded in the weekly digest | Not a separate email |
| Content | 2-3 WOW/mistake fares highlighted at random | "Here are a few WOW deals that came up this week" |
| Tone | Urgency-driven | "You MISSED $580 Lagos — gone in 6 hours. Premium members got it instantly." |
| Purpose | Drive free-to-premium conversion | Show what they're missing without being annoying |

### 3. Regional Preferences

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Region model | Metro groups | NYC (JFK+EWR), DC (IAD), Atlanta (ATL), Houston (IAH), Chicago (ORD), LA (LAX) |
| Free tier | 1 metro, selected at signup | Can change once per month |
| Premium tier | Unlimited metros | No cap on origin selection |
| Storage | Subscriber record in DB | Region preferences stored per subscriber |

**Metro group mapping:**

| Metro | Airports |
|-------|----------|
| NYC | JFK, EWR |
| DC | IAD |
| Atlanta | ATL |
| Houston | IAH |
| Chicago | ORD |
| LA | LAX |

### 4. Premium Value Prop

| Feature | Free | Premium |
|---------|------|---------|
| Great deal alerts | Weekly digest | Instant |
| WOW/mistake fare alerts | Teaser in digest (redacted) | Instant email |
| SMS for mistake fares | No | Yes |
| Historical price context | No | Yes ("45% below 90-day avg") |
| Booking links | Yes | Yes |
| Origin metros | 1 metro | Unlimited |
| Region changes | Once per month | Anytime |

### 5. Payments & Billing

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Price | $15/quarter ($5/month effective) | Simple, low friction |
| Payment method | Manual Venmo/Zelle | MVP — no payment integration needed |
| Billing cycle | Quarterly | User pays every 3 months |
| Reminders | Automated email reminders before renewal | Remind subscribers when quarterly payment is due |
| Premium toggle | Manual by operator | Operator marks subscriber as premium after receiving payment |

## Existing Infrastructure

- **Subscribers**: Currently in Google Sheets (from Phase 1)
- **Email**: Gmail SMTP (100/day limit, Phase 7 migrates to Resend)
- **Database**: Turso (price history, alert state)
- **Alert FSM**: Phase 4 — already gates alerts by tier (Great vs WOW)

## Key Constraints

- Gmail SMTP 100/day limit means free weekly digest must be efficient (batch all free users in one run)
- Subscriber data needs to move from Google Sheets to Turso (or at minimum, tier + region preferences in Turso)
- SMS delivery needs a provider (Twilio free tier or similar)
- Payment reminders need a simple scheduler (cron or GitHub Actions)

## Requirements Covered

- SUBS-01 through SUBS-05: Subscriber management and tier system
- FRML-01 through FRML-04: Freemium content gating and conversion

## Open Questions for Research Phase

- Best approach for SMS delivery (Twilio vs alternatives)
- How to structure subscriber data migration from Google Sheets to DB
- Weekly digest scheduling (GitHub Actions cron vs separate service)
- Payment reminder automation approach
