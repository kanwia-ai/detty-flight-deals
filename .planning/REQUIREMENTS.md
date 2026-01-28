# Requirements: Detty Flight Deals

**Defined:** 2026-01-27
**Core Value:** Find genuinely great flight deals to Africa before anyone else — and make them actionable.

## v1 Requirements

Requirements for beta launch (~200 subscribers, 3-month beta, then freemium at $5/month).

### Deal Discovery

- [x] **DISC-01**: System monitors 6 priority routes every 2 hours via Amadeus API (cheapest-date search)
- [x] **DISC-02**: System cross-validates Amadeus prices against Google Flights before alerting (no single-source alerts)
- [x] **DISC-03**: System scans full date ranges (not just sample weeks) for priority routes via Amadeus Cheapest Date Search
- [x] **DISC-04**: System detects anomalously cheap fares using rolling z-score against historical baselines (z < -2.5)
- [x] **DISC-05**: System discovers own mistake fares via level shift detection (not just RSS feeds)
- [x] **DISC-06**: System falls back to static percentage thresholds when <30 historical observations exist for a route
- [x] **DISC-07**: System applies seasonal threshold adjustments (Dec-Jan +50%, Jun-Aug +25%) to avoid false positives during peak travel

### Alert Intelligence

- [ ] **ALRT-01**: System alerts only on tier transitions (Good→Great→WOW), not same-tier price wiggles
- [ ] **ALRT-02**: System enforces cooldown after alerts (48h Good, 24h Great, 12h WOW) to prevent fatigue
- [ ] **ALRT-03**: Tier escalation (e.g., Great→WOW) overrides cooldown and alerts immediately
- [ ] **ALRT-04**: System resets alert cycle when price returns to normal range for 3 consecutive checks
- [ ] **ALRT-05**: Alert state machine persists per-route state (current tier, cooldown expiry, reset counter) in database

### Data Infrastructure

- [x] **DATA-01**: All price observations stored in Turso (libSQL) database with append-only history
- [x] **DATA-02**: Price cache materialized view replaces seen_deals.json for deduplication
- [x] **DATA-03**: Alert state table tracks FSM state per route (tier, cooldown, reset counter)
- [x] **DATA-04**: Migration from JSON files to Turso uses dual-write for 1-week validation period
- [x] **DATA-05**: System degrades gracefully — falls back to JSON if Turso is unreachable

### Subscriber Management

- [ ] **SUBS-01**: Subscribers stored in database (replaces Google Sheets), supporting tier and preference fields
- [ ] **SUBS-02**: Each subscriber has a tier (free/premium) and optional regional preferences (origin_region, dest_region)
- [ ] **SUBS-03**: Free tier subscribers receive daily digest of Good + Great economy deals (all routes)
- [ ] **SUBS-04**: Premium tier subscribers receive instant WOW alerts, mistake fares, and business/first class deals
- [ ] **SUBS-05**: System supports 200+ subscribers without delivery failures

### Freemium Model

- [ ] **FRML-01**: Expired deal teasers sent to free users — "Yesterday, Premium members saved $X on [route]"
- [ ] **FRML-02**: Premium subscribers can set regional origin preferences (New England, Mid-Atlantic, South/Texas, Atlanta)
- [ ] **FRML-03**: Premium subscribers can set regional destination preferences (West, East, North, Southern Africa)
- [ ] **FRML-04**: 1-week free trial of premium for new subscribers

### Business/First Class

- [ ] **BUSN-01**: System monitors business/first class fares on priority routes via Amadeus cabin class parameter
- [ ] **BUSN-02**: Business class thresholds are separate from economy (40-50% below baseline vs. 30%)
- [ ] **BUSN-03**: Business/first class deals routed only to premium subscribers

### Email Delivery

- [ ] **MAIL-01**: Email delivery via transactional email service (Resend/SendGrid), not Gmail SMTP
- [ ] **MAIL-02**: SPF/DKIM/DMARC configured for sending domain
- [ ] **MAIL-03**: One-click unsubscribe via List-Unsubscribe header (Gmail/Yahoo compliance)
- [ ] **MAIL-04**: Email delivery rate >95%, spam complaint rate <0.1%

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Route Expansion

- **EXPN-01**: East Africa destinations (Nairobi, Addis Ababa, Dar es Salaam, Kampala, Kigali)
- **EXPN-02**: Southern Africa destinations (Johannesburg, Cape Town, Harare, Lusaka)
- **EXPN-03**: North Africa destinations (Cairo, Casablanca, Marrakech, Tunis)
- **EXPN-04**: UK/EU origin cities

### Platform

- **PLAT-01**: Web app for browsing active deals
- **PLAT-02**: Mobile-optimized deal browsing
- **PLAT-03**: WhatsApp alert channel as alternative to email

### Monetization

- **MNTZ-01**: Automated payment/billing (Stripe integration)
- **MNTZ-02**: Annual subscription option at discount
- **MNTZ-03**: Airport-level destination selection (granular personalization)

### Intelligence

- **INTL-01**: Price prediction using 12+ months historical data
- **INTL-02**: Detty December early warning system (optimal booking window alerts Mar-Jun)
- **INTL-03**: Credit card points/miles deal tracking

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Web app for browsing deals | Email-first; web is v2 |
| Mobile app | Email + responsive landing is sufficient until $10M+ revenue |
| Credit card points/miles | Different product; classes/cabins more important first |
| Hotels or trip planning | Flights only — stay focused |
| OTA/booking integration | Complexity, liability, affiliate conflicts |
| Price prediction ML | Requires 5+ years data Detty doesn't have |
| Always-on server/containers | Serverless on GitHub Actions; no operational burden |
| Full GDS/ATPCO access | $100K+/month; not viable at current scale |
| Automated Stripe billing | Manual $5/month via Venmo during beta |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DISC-01 | Phase 1 | Complete |
| DISC-02 | Phase 1 | Complete |
| DISC-03 | Phase 1 | Complete |
| DATA-01 | Phase 2 | Complete |
| DATA-02 | Phase 2 | Complete |
| DATA-03 | Phase 2 | Complete |
| DATA-04 | Phase 2 | Complete |
| DATA-05 | Phase 2 | Complete |
| DISC-04 | Phase 3 | Complete |
| DISC-05 | Phase 3 | Complete |
| DISC-06 | Phase 3 | Complete |
| DISC-07 | Phase 3 | Complete |
| ALRT-01 | Phase 4 | Pending |
| ALRT-02 | Phase 4 | Pending |
| ALRT-03 | Phase 4 | Pending |
| ALRT-04 | Phase 4 | Pending |
| ALRT-05 | Phase 4 | Pending |
| SUBS-01 | Phase 5 | Pending |
| SUBS-02 | Phase 5 | Pending |
| SUBS-03 | Phase 5 | Pending |
| SUBS-04 | Phase 5 | Pending |
| SUBS-05 | Phase 5 | Pending |
| FRML-01 | Phase 5 | Pending |
| FRML-02 | Phase 5 | Pending |
| FRML-03 | Phase 5 | Pending |
| FRML-04 | Phase 5 | Pending |
| BUSN-01 | Phase 6 | Pending |
| BUSN-02 | Phase 6 | Pending |
| BUSN-03 | Phase 6 | Pending |
| MAIL-01 | Phase 7 | Pending |
| MAIL-02 | Phase 7 | Pending |
| MAIL-03 | Phase 7 | Pending |
| MAIL-04 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-27*
*Last updated: 2026-01-28 after Phase 3 completion*
