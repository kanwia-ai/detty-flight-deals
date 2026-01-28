# Phase 4: Alert State Machine - Context

**Gathered:** 2026-01-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminate alert fatigue by implementing a tier-escalation finite state machine. Users only get notified on meaningful tier changes, not minor price fluctuations. The FSM persists state per route and enforces cooldowns to prevent spam.

</domain>

<decisions>
## Implementation Decisions

### Tier Structure
- **Two tiers only:** Great (free) and WOW (premium)
- No "Good" tier — if it's just "good," Google Alerts can find it
- **Mistake fares** = special flag, always routes to premium regardless of tier
- **Premium tier includes:** WOW deals + Mistake fares + Business/First class + Points deals (Phase 6)
- Tier logic integration with Phase 3 output: Claude's discretion on mapping anomaly detection to tiers

### Tier Visibility in Emails
- Tier labels appear in email subjects with emoji
- Emoji tiers: Claude picks clean, distinctive emoji per tier (e.g., Great, WOW, Mistake)

### Cooldown Approach
- **Once per deal window** — alert once when deal appears, no re-alerts for same deal at same tier
- **Escalation overrides:** Great→WOW triggers new email immediately (new information)
- **Reset logic:** Claude's discretion — adapts to monitoring frequency (2-hour priority vs daily standard)
- Deal ends when price normalizes for consecutive checks, then cycle resets
- If deal returns after ending, it's treated as a new deal

### Escalation Handling
- Escalation (Great→WOW) triggers a **new email**, not silent update
- Subject format: "Price DROP: JFK→Lagos now $580 (was $720)"
- Show **both** contexts: drop from last alert AND savings vs normal price
- Example: "$580 (↓$140 from yesterday, normally $920)"

### De-escalation
- **Silent — no alert** on de-escalation or deal disappearance
- Only notify on good news; if deal ends, just stop alerting

### Mistake Fare Handling
- Higher urgency messaging for mistake fares
- Format: "⚠️ MISTAKE FARE — Book NOW, may disappear in hours"
- Mistake fares are premium-only content

### Claude's Discretion
- Exact emoji choices for tier labels
- Tier threshold logic (mapping z-score/anomaly output to Great vs WOW)
- Reset timing (consecutive check count based on monitoring frequency)
- Email template styling details

</decisions>

<specifics>
## Specific Ideas

### Competitor Research Insights (Going.com, Thrifty Traveler)
- Going.com: "They will not send you a deal unless they think it's actually worth buying" — quality over quantity
- Thrifty Traveler: 1-3 emails/day for large airports (Detty = much lower volume for Africa routes)
- Deal expiration: Most deals valid 24-48 hours, need urgency indicators

### Email Style Preferences (from competitor analysis)
- Clean, minimal design (Going-style, not Thrifty's blog-post density)
- Deal info FIRST, hero image secondary/optional
- Prominent: Route, Price (with strikethrough normal), Tier emoji, Urgency
- Brief context line for customer education ("Lagos usually $900+ in January")
- No ads, no clutter
- Group by tier or destination in digests (future phase)

### Africa Route Context
- 77 routes total, lower deal volume than US/Europe domestic
- Users travel 1-2x/year to Africa
- Each alert should feel valuable
- Expect 2-5 alerts/week during good periods, zero during dry spells

</specifics>

<deferred>
## Deferred Ideas

- **FOMO section for free users** — "Real deals Premium members saw" with locked content (Phase 5: Freemium Infrastructure)
- **Deal context with AI research** — Contextualize deals with historical data ("This route averages $920, today's $580 is in the bottom 5%") — future enhancement
- **Booking confirmation tracking** — "I booked this deal" feedback loop for conversion analytics — future phase
- **Referral program** — Forward deals to earn rewards — post-MVP
- **Deal digest grouping** — Batch multiple deals into organized email — consider for Phase 5

</deferred>

---

*Phase: 04-alert-state-machine*
*Context gathered: 2026-01-28*
