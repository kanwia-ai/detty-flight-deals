# Phase 7: Email Delivery Scale - Research

**Researched:** 2026-02-11
**Domain:** Transactional email delivery, email authentication (SPF/DKIM/DMARC), Gmail/Yahoo compliance
**Confidence:** HIGH (official docs + codebase analysis verified)

## Summary

Phase 7 replaces Gmail SMTP (capped at 100/day) with Resend as the transactional email provider, enabling the project to scale beyond 100 subscribers while complying with Gmail/Yahoo 2024-2025 bulk sender requirements. The migration is simpler than initially expected because Resend supports SMTP as a drop-in replacement -- the existing `smtplib` code in `mvp0_sender.py` can be updated by simply changing the SMTP host, port, username, and password. The REST API should be used for new code (the `email_client.py` wrapper) because it provides better error reporting, tags for tracking, custom headers (including List-Unsubscribe), and webhook support.

The codebase has a single email send function (`send_to_subscriber()` in `mvp0_sender.py`) that is the bottleneck -- all 6 email-sending pathways funnel through it. This makes the migration clean: update one function, and all workflows benefit. However, 7 files import or call this function, and the `send_welcome_email.yml` workflow has inline SMTP code that also needs updating. DNS configuration (SPF, DKIM, DMARC) for the sending domain is required before any emails can be sent through Resend. One-click unsubscribe (RFC 8058) requires a publicly accessible POST endpoint, which is the most architecturally complex piece since the project currently runs entirely on GitHub Actions with no server.

**Primary recommendation:** Use Resend REST API via `resend` Python SDK v2.21 for the new `email_client.py` wrapper. Migrate all send paths through this wrapper. Use Cloudflare Workers (free tier) for the one-click unsubscribe POST endpoint. Configure DNS records for dettyflightdeals.com before any sending.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| resend | 2.21.0 | Email sending via REST API | Official Python SDK, 3K free/month, DKIM built-in, webhook support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| smtplib (stdlib) | N/A | Fallback Gmail SMTP sending | Only during migration period as fallback |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Resend REST API | Resend SMTP (drop-in) | SMTP works with existing smtplib code (zero code change), but no tags, no webhook integration, no delivery metadata in response. Use for fastest possible migration; switch to REST API for full feature set |
| Resend | SendGrid | SendGrid has more features but worse DX, more complex setup, 100/day free tier |
| Resend | Amazon SES | SES is cheapest at scale but complex setup, IAM, region-specific, no dashboard |
| Cloudflare Workers (unsubscribe endpoint) | Vercel Serverless | Vercel works too; Cloudflare has more generous free tier and edge proximity |

**Installation:**
```bash
pip install resend
```

Add to `requirements.txt`:
```
resend>=2.21.0
```

## Architecture Patterns

### Recommended Project Structure
```
detty-flight-deals/
├── email_client.py          # NEW: Resend SDK wrapper with retry, fallback, headers
├── mvp0_sender.py           # MODIFIED: send_to_subscriber() delegates to email_client
├── subscriber/
│   ├── router.py            # MODIFIED: imports send from email_client (not mvp0_sender)
│   ├── digest.py            # MODIFIED: imports send from email_client
│   ├── reminders.py         # MODIFIED: imports send from email_client
│   └── unsubscribe.py       # NEW: unsubscribe token generation + DB update logic
├── alert/
│   └── templates.py         # MODIFIED: add List-Unsubscribe header to all templates
├── .github/workflows/
│   └── *.yml                # MODIFIED: add RESEND_API_KEY secret, remove SMTP_* (eventually)
└── unsubscribe-worker/      # NEW: Cloudflare Worker for one-click unsubscribe POST endpoint
    ├── wrangler.toml
    └── src/index.ts          # Handles POST from email clients, calls Turso to deactivate
```

### Pattern 1: Centralized Email Client with Fallback
**What:** Single `email_client.py` that wraps Resend SDK, with fallback to Gmail SMTP during migration.
**When to use:** All email sending in the project.
**Example:**
```python
# email_client.py
import os
import resend
from typing import Optional

resend.api_key = os.environ.get("RESEND_API_KEY", "")

SEND_DOMAIN = os.environ.get("SEND_DOMAIN", "dettyflightdeals.com")
FROM_EMAIL = f"Detty Flight Deals <deals@{SEND_DOMAIN}>"

def send_email(
    to: str,
    subject: str,
    html_body: str,
    plain_body: str,
    reply_to: str = None,
    headers: dict = None,
    tags: list = None,
) -> dict:
    """
    Send email via Resend REST API.
    Falls back to Gmail SMTP if RESEND_API_KEY not set.

    Returns dict with {"id": "...", "provider": "resend"} on success.
    """
    if not resend.api_key:
        return _send_via_gmail_smtp(to, subject, html_body, plain_body)

    params: resend.Emails.SendParams = {
        "from": FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "html": html_body,
        "text": plain_body,
    }

    if reply_to:
        params["reply_to"] = reply_to
    if headers:
        params["headers"] = headers
    if tags:
        params["tags"] = tags

    result = resend.Emails.send(params)
    return {"id": result.get("id"), "provider": "resend"}
```

### Pattern 2: List-Unsubscribe Headers (RFC 8058)
**What:** Add both `List-Unsubscribe` and `List-Unsubscribe-Post` headers to every email.
**When to use:** Every outgoing email to comply with Gmail/Yahoo requirements.
**Example:**
```python
# Generate per-subscriber unsubscribe URL with signed token
import hashlib
import hmac

UNSUBSCRIBE_SECRET = os.environ.get("UNSUBSCRIBE_SECRET", "")
UNSUBSCRIBE_BASE_URL = os.environ.get("UNSUBSCRIBE_BASE_URL", "https://unsubscribe.dettyflightdeals.com")

def generate_unsubscribe_token(email: str) -> str:
    """Generate HMAC token for unsubscribe URL (prevents forgery)."""
    return hmac.new(
        UNSUBSCRIBE_SECRET.encode(),
        email.encode(),
        hashlib.sha256
    ).hexdigest()[:32]

def get_unsubscribe_headers(email: str) -> dict:
    """Build RFC 8058 compliant unsubscribe headers."""
    token = generate_unsubscribe_token(email)
    unsub_url = f"{UNSUBSCRIBE_BASE_URL}/unsubscribe?email={email}&token={token}"
    return {
        "List-Unsubscribe": f"<{unsub_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
```

### Pattern 3: Webhook-Driven Bounce/Complaint Handling
**What:** Resend webhooks POST to an endpoint that updates subscriber status on bounces/complaints.
**When to use:** Automated list hygiene to maintain <4% bounce rate and <0.08% complaint rate.
**Note:** This can share the same Cloudflare Worker as the unsubscribe endpoint, or use a separate one.

### Anti-Patterns to Avoid
- **Sending from gmail.com address through Resend:** You must own the sending domain. Cannot send as @gmail.com through Resend. Need dettyflightdeals.com or similar.
- **Hardcoding SMTP credentials:** Use environment variables for all secrets (RESEND_API_KEY, UNSUBSCRIBE_SECRET).
- **Opening a new SMTP connection per email:** Resend REST API handles connection pooling. Don't replicate the smtplib pattern of connect-send-close per email.
- **Skipping List-Unsubscribe-Post header:** Gmail/Yahoo require BOTH `List-Unsubscribe` (the URL) AND `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (signals one-click support). Missing the POST header means non-compliance.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Email sending + retry | Custom SMTP connection manager | `resend.Emails.send()` | Handles retries, rate limiting, connection pooling internally |
| DKIM signing | Manual DKIM key generation | Resend domain verification | Resend generates and manages DKIM keys automatically when you add DNS records |
| Bounce processing | Custom bounce email parser | Resend `email.bounced` webhook | Parsing bounce emails is notoriously complex; Resend normalizes it |
| Complaint tracking | Manual feedback loop registration | Resend `email.complained` webhook | ISP feedback loops require registration; Resend handles this |
| Unsubscribe token signing | Custom JWT or encryption | HMAC-SHA256 with shared secret | Simple, stateless, no token storage needed. The secret is the only state |

**Key insight:** Resend handles the three hardest parts of email delivery -- DKIM signing, bounce classification, and ISP feedback loops. The project should never attempt to build these.

## Common Pitfalls

### Pitfall 1: Sending Before DNS Verification
**What goes wrong:** Emails silently fail or land in spam because domain isn't verified in Resend.
**Why it happens:** DNS propagation takes up to 72 hours. Developer starts sending before records propagate.
**How to avoid:** Verify domain status is "verified" in Resend dashboard before switching any workflow to Resend. Use `resend.Domains.get()` API to check programmatically.
**Warning signs:** Resend API returns 403 or domain-not-verified errors.

### Pitfall 2: Resend Free Tier Daily Cap (100/day)
**What goes wrong:** The free tier has a 100 emails/day limit -- the SAME cap as Gmail SMTP. Doesn't immediately solve the scaling problem.
**Why it happens:** Free tier is for testing/small projects. The project needs 100+ subscribers.
**How to avoid:** Plan to upgrade to Resend Pro ($20/month, 50K emails/month, no daily limit) once subscriber count exceeds ~80. The free tier works for initial migration testing. Budget $20/month into operational costs.
**Warning signs:** Resend dashboard shows emails being queued or paused.

### Pitfall 3: Missing DMARC Record
**What goes wrong:** SPF and DKIM pass, but DMARC fails because no DMARC record exists. Gmail may still deliver but marks as suspicious.
**Why it happens:** DMARC is listed as "optional" by Resend, but Gmail/Yahoo require it for bulk senders (5000+ messages/day).
**How to avoid:** Always add DMARC record, even for small senders. Start with `p=none` (monitoring), move to `p=quarantine` after 2 weeks of clean reports.
**Warning signs:** DMARC aggregate reports show failures.

### Pitfall 4: Unsubscribe Endpoint Downtime
**What goes wrong:** Gmail shows "Unsubscribe" button, user clicks it, POST fails because endpoint is down. Gmail may downgrade sender reputation.
**Why it happens:** The unsubscribe endpoint is a critical dependency. If it's on a free tier with cold starts or goes down, unsubscribes fail.
**How to avoid:** Use Cloudflare Workers (always-on, no cold starts on free tier, globally distributed). Test endpoint uptime monitoring.
**Warning signs:** Users complain they can't unsubscribe; spam complaint rate rises.

### Pitfall 5: Resend Rate Limit (2 req/sec)
**What goes wrong:** Sending to 200+ subscribers sequentially hits the 2 requests/second rate limit, causing 429 errors.
**Why it happens:** Default Resend rate limit is 2 requests/second for all accounts.
**How to avoid:** Add 0.5s delay between sends (same as existing `time.sleep(0.5)` pattern). For batch sends, use Resend's batch API or implement exponential backoff on 429. Current codebase already has 0.5s delays -- keep them.
**Warning signs:** API returns 429 Too Many Requests.

### Pitfall 6: Forgetting to Update Inline SMTP in send_welcome_email.yml
**What goes wrong:** Welcome emails still go through Gmail SMTP because the workflow has inline Python SMTP code (not using mvp0_sender).
**Why it happens:** `send_welcome_email.yml` has raw smtplib code embedded in the YAML, not importing from any module.
**How to avoid:** Refactor this workflow to call `mvp0_sender.send_welcome_email()` or the new `email_client.py`, not inline SMTP.
**Warning signs:** Welcome emails stop working after SMTP credentials are removed.

### Pitfall 7: Bounce Rate Exceeding 4%
**What goes wrong:** Resend temporarily pauses sending if bounce rate exceeds 4%.
**Why it happens:** Stale email addresses from Google Sheets subscriber list, no bounce handling.
**How to avoid:** Process `email.bounced` webhooks to automatically deactivate bouncing subscribers. Clean the subscriber list during migration.
**Warning signs:** Resend dashboard shows elevated bounce rate; sending paused.

## Code Examples

### Sending Email via Resend REST API (Python)
```python
# Source: https://resend.com/docs/send-with-python + custom headers from https://resend.com/docs/dashboard/emails/custom-headers
import os
import resend

resend.api_key = os.environ["RESEND_API_KEY"]

params: resend.Emails.SendParams = {
    "from": "Detty Flight Deals <deals@dettyflightdeals.com>",
    "to": ["subscriber@example.com"],
    "subject": "[* Great] Lagos from $650",
    "html": "<strong>Deal found!</strong>",
    "text": "Deal found!",
    "reply_to": "dettyflightdeals@gmail.com",
    "headers": {
        "List-Unsubscribe": "<https://unsubscribe.dettyflightdeals.com/unsubscribe?email=subscriber@example.com&token=abc123>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    },
    "tags": [
        {"name": "deal_tier", "value": "great"},
        {"name": "destination", "value": "LOS"},
    ],
}

email = resend.Emails.send(params)
print(f"Sent: {email['id']}")
```

### Resend SMTP Drop-In Replacement (Minimal Change Path)
```python
# Source: https://resend.com/docs/send-with-smtp
# Current code in mvp0_sender.py uses:
#   smtp.gmail.com:465 with SMTP_EMAIL/SMTP_PASSWORD
#
# Drop-in replacement (just change host/port/credentials):
import smtplib

RESEND_SMTP_HOST = "smtp.resend.com"
RESEND_SMTP_PORT = 465
RESEND_SMTP_USER = "resend"
RESEND_SMTP_PASS = os.environ.get("RESEND_API_KEY")

with smtplib.SMTP_SSL(RESEND_SMTP_HOST, RESEND_SMTP_PORT) as server:
    server.login(RESEND_SMTP_USER, RESEND_SMTP_PASS)
    server.sendmail(from_addr, to_addr, msg.as_string())
```

### DNS Records for dettyflightdeals.com
```
# Source: https://resend.com/docs/dashboard/domains/introduction + https://dmarcdkim.com/setup/how-to-setup-resend-spf-dkim-and-dmarc-records

# Resend generates these when you add your domain. Copy exact values from dashboard.
# These are representative examples:

# SPF (TXT record)
# Name: send (for send.dettyflightdeals.com) or @ for root
# Value: v=spf1 include:amazonses.com ~all
# Note: Resend uses Amazon SES infrastructure; SPF record authorizes their IPs

# DKIM (CNAME records -- typically 3 records)
# Name: resend._domainkey (or as shown in dashboard)
# Value: (provided by Resend dashboard)

# DMARC (TXT record)
# Name: _dmarc
# Value: v=DMARC1; p=none; rua=mailto:dmarc-reports@dettyflightdeals.com
# Start with p=none (monitoring), then move to p=quarantine after 2 weeks
```

### Cloudflare Worker Unsubscribe Endpoint
```typescript
// Source: Pattern based on RFC 8058 requirements
// https://datatracker.ietf.org/doc/html/rfc8058

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // RFC 8058: One-click unsubscribe via POST
    if (request.method === "POST" && url.pathname === "/unsubscribe") {
      const email = url.searchParams.get("email");
      const token = url.searchParams.get("token");

      // Verify HMAC token
      const expectedToken = await generateToken(email, env.UNSUBSCRIBE_SECRET);
      if (token !== expectedToken) {
        return new Response("Invalid token", { status: 403 });
      }

      // Deactivate subscriber in Turso
      const response = await fetch(env.TURSO_URL, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.TURSO_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          statements: [{
            q: "UPDATE subscribers SET active = 0, unsubscribed_at = datetime('now') WHERE email = ?",
            params: [email],
          }],
        }),
      });

      return new Response("Unsubscribed successfully", { status: 200 });
    }

    // GET: Show confirmation page (for users clicking link manually)
    if (request.method === "GET" && url.pathname === "/unsubscribe") {
      return new Response(UNSUBSCRIBE_HTML, {
        headers: { "Content-Type": "text/html" },
      });
    }

    return new Response("Not found", { status: 404 });
  },
};
```

## Codebase Analysis: Current Email Touchpoints

### The Single Bottleneck: `send_to_subscriber()`

All email sending flows through one function in `mvp0_sender.py` (line 217):

```python
def send_to_subscriber(email: str, subject: str, html_body: str, plain_body: str) -> bool:
    """Send email to a single subscriber via Gmail SMTP."""
```

**Files that import/call it (7 total):**
1. `/Users/kyraatekwana/Projects/detty-flight-deals/deal_finder.py` -- `from mvp0_sender import send_to_subscriber` (line 21)
2. `/Users/kyraatekwana/Projects/detty-flight-deals/subscriber/router.py` -- `from mvp0_sender import send_to_subscriber` (line 181, inside method)
3. `/Users/kyraatekwana/Projects/detty-flight-deals/subscriber/digest.py` -- `from mvp0_sender import send_to_subscriber` (line 198, inside function)
4. `/Users/kyraatekwana/Projects/detty-flight-deals/subscriber/reminders.py` -- `from mvp0_sender import send_to_subscriber` (line 222)
5. `/Users/kyraatekwana/Projects/detty-flight-deals/mvp0_sender.py` -- defines it + uses it in `send_welcome_email()` and `send_deals_to_all()`
6. `/Users/kyraatekwana/Projects/detty-flight-deals/send_test_emails.py` -- `from mvp0_sender import send_to_subscriber` (line 18)
7. `/Users/kyraatekwana/Projects/detty-flight-deals/mistake_fare_monitor.py` -- `from mvp0_sender import send_to_subscriber` (line 21)

### Other Email Paths (Legacy/Alternate)

- `deal_finder.py:send_via_buttondown()` (line 884) -- Buttondown API, appears unused/legacy
- `deal_finder.py:send_via_smtp()` (line 917) -- Direct SMTP fallback, only used in `send_email()`
- `deal_finder.py:send_email()` (line 981) -- Legacy entry point, falls back through GSheet -> SMTP
- `mistake_fare_monitor.py:send_via_buttondown()` (line 385) -- Duplicate of above
- `mistake_fare_monitor.py:send_via_smtp()` (line 414) -- Duplicate of above

### Inline SMTP Code (Not Using Shared Functions)

- `.github/workflows/send_welcome_email.yml` (lines 32-113) -- Has raw smtplib code embedded directly in YAML. Does NOT import from mvp0_sender. Must be refactored separately.

### GitHub Actions Workflows That Send Email (6 total)

| Workflow | File | Email Method | Secrets Used |
|----------|------|-------------|-------------|
| Find Deals | `find_deals.yml` | `deal_finder.py` -> `AlertRouter` -> `send_to_subscriber()` | SMTP_EMAIL, SMTP_PASSWORD |
| Priority Monitor | `priority_monitor.yml` | `amadeus_monitor.py` -> `send_email()` | SMTP_EMAIL, SMTP_PASSWORD |
| Premium Cabin | `premium_cabin_monitor.yml` | `premium_cabin_monitor.py` -> `AlertRouter` | SMTP_EMAIL, SMTP_PASSWORD |
| Weekly Digest | `weekly_digest.yml` | `subscriber.digest` -> `send_to_subscriber()` | SMTP_EMAIL, SMTP_PASSWORD |
| Mistake Fares | `mistake_fares.yml` | `mistake_fare_monitor.py` -> `send_to_subscriber()` | SMTP_EMAIL, SMTP_PASSWORD |
| Welcome Email | `send_welcome_email.yml` | **Inline smtplib** (not shared function) | SMTP_EMAIL, SMTP_PASSWORD |

All 6 workflows need `RESEND_API_KEY` added as a secret. SMTP_EMAIL/SMTP_PASSWORD can be retained during migration for fallback.

### Current Unsubscribe Implementation

All email templates use `mailto:` unsubscribe links:
```html
<a href="mailto:kyra.atekwana@gmail.com?subject=Unsubscribe%20from%20Detty%20Flight%20Deals&body=Please%20unsubscribe%20me.">Unsubscribe</a>
```

This is NOT compliant with Gmail/Yahoo requirements. Must be replaced with:
1. `List-Unsubscribe` header with HTTPS URL
2. `List-Unsubscribe-Post: List-Unsubscribe=One-Click` header
3. Visible unsubscribe link in email body pointing to the same endpoint

Files with mailto unsubscribe links that need updating:
- `deal_finder.py` (line 872)
- `mvp0_sender.py` (lines 185, 350)
- `alert/templates.py` (lines 513, 862)
- `subscriber/reminders.py` (line 142)
- `.github/workflows/send_welcome_email.yml` (line 91)

### Gmail Daily Limit References

The 90/day safety cap is referenced in:
- `subscriber/router.py` line 128: `if self._email_send_count >= 90`
- `subscriber/digest.py` line 41: `GMAIL_DAILY_LIMIT = 90`

These need to be updated after migration (Resend Pro has no daily limit; free tier has 100/day).

## Migration Strategy: Zero-Downtime Gmail SMTP to Resend

### Phase A: Preparation (Before Any Code Changes)
1. Purchase domain (dettyflightdeals.com or similar)
2. Create Resend account, add domain, get DNS records
3. Configure DNS records (SPF, DKIM, DMARC with p=none)
4. Wait for verification (up to 72 hours)
5. Get RESEND_API_KEY from Resend dashboard
6. Add `RESEND_API_KEY` secret to GitHub Actions

### Phase B: Dual-Provider Implementation
1. Create `email_client.py` with Resend SDK wrapper
2. Add fallback: if RESEND_API_KEY missing, use Gmail SMTP (existing behavior)
3. Update `mvp0_sender.py:send_to_subscriber()` to delegate to `email_client.py`
4. Add List-Unsubscribe headers to all outgoing emails
5. Deploy Cloudflare Worker for unsubscribe endpoint
6. Update all email templates to use HTTPS unsubscribe link (replacing mailto:)

### Phase C: Validation
1. Send test emails through Resend (check delivery, DKIM, SPF)
2. Check headers in received email (List-Unsubscribe visible in Gmail)
3. Test one-click unsubscribe flow end-to-end
4. Monitor Resend dashboard for bounce/complaint rates
5. Keep Gmail SMTP fallback active for 1-2 weeks

### Phase D: Cutover
1. Remove Gmail SMTP fallback from `email_client.py`
2. Update GMAIL_DAILY_LIMIT constants (no longer applicable)
3. Remove SMTP_EMAIL/SMTP_PASSWORD from workflows (keep as backup)
4. Set up Resend webhooks for bounce/complaint handling

### Key Principle: Fallback First
During migration, every email send should try Resend first, fall back to Gmail SMTP on failure. This means zero downtime -- if Resend is down or misconfigured, emails still go out via Gmail.

## Unsubscribe Endpoint Architecture Options

The one-click unsubscribe endpoint must be a publicly accessible HTTPS URL that accepts POST requests. Current project has no server (all GitHub Actions). Options:

### Option 1: Cloudflare Workers (RECOMMENDED)
- **Cost:** Free tier (100K requests/day)
- **Cold starts:** None (always warm, globally distributed)
- **Stack:** TypeScript/JavaScript worker
- **Pros:** No cold starts, free, globally distributed, easy to deploy
- **Cons:** Different language from project (TypeScript vs Python), separate deploy pipeline
- **Domain:** `unsubscribe.dettyflightdeals.com` via Cloudflare DNS

### Option 2: Vercel Serverless Function
- **Cost:** Free tier (100GB bandwidth)
- **Cold starts:** Possible (but fast)
- **Stack:** Python or Node.js
- **Pros:** Can use Python, simple deployment
- **Cons:** Potential cold starts on free tier, less generous free tier than Cloudflare

### Option 3: AWS Lambda + API Gateway
- **Cost:** Free tier (1M requests/month)
- **Stack:** Python
- **Pros:** Python, same language as project
- **Cons:** Complex setup (API Gateway, IAM, Lambda), overkill for single endpoint

### Option 4: Turso HTTP API Directly (NO SERVER)
- **Cost:** $0 (uses existing Turso)
- **Stack:** None -- the unsubscribe URL points to a static page with client-side JS that calls Turso HTTP API
- **Pros:** No additional infrastructure
- **Cons:** Exposes Turso API structure, requires CORS setup, less secure, doesn't satisfy RFC 8058 (needs server-side POST handling)
- **Verdict:** Not viable for RFC 8058 compliance

### Recommendation: Cloudflare Workers
Cloudflare Workers is the best fit because: (1) free tier is generous, (2) no cold starts means Gmail/Yahoo one-click POST always succeeds, (3) the domain will likely use Cloudflare DNS anyway for Resend's DNS records, (4) deployment is a single `wrangler deploy` command.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Gmail SMTP (100/day cap) | Transactional email API (Resend, SendGrid, SES) | Always true at scale | Removes hard sending limit, adds delivery analytics |
| No email authentication | SPF + DKIM + DMARC required | Feb 2024 (Gmail/Yahoo enforcement) | Non-authenticated emails rejected or sent to spam |
| Mailto: unsubscribe | RFC 8058 one-click unsubscribe (HTTPS POST) | Feb 2024 (Gmail/Yahoo requirement) | Must have List-Unsubscribe + List-Unsubscribe-Post headers |
| Manual bounce handling | Webhook-driven automated list hygiene | Industry standard | Auto-deactivate bouncing addresses to protect sender reputation |
| p=none DMARC | p=quarantine or p=reject | Nov 2025 (Gmail tightened enforcement) | Non-compliant emails face temporary or permanent rejection |

**Deprecated/outdated:**
- Buttondown API integration (in `deal_finder.py`): appears unused, can be removed during cleanup
- Gmail SMTP for multi-subscriber sending: hard-capped at 100/day, not suitable for growth

## Open Questions

1. **Domain Availability**
   - What we know: dettyflightdeals.com was referenced in email templates and share links
   - What's unclear: Whether the domain is already purchased/registered
   - Recommendation: Check domain ownership before starting Phase B. If not owned, purchase it first. This blocks all DNS work.

2. **Resend Free vs Pro Tier Timing**
   - What we know: Free tier is 100/day (same as Gmail). Pro is $20/month with 50K/month and no daily limit.
   - What's unclear: Current subscriber count. If already near 100, free tier doesn't help.
   - Recommendation: Start on free tier for testing. Upgrade to Pro when subscriber count exceeds 80 or when ready for production cutover.

3. **Webhook Endpoint for Bounces/Complaints**
   - What we know: Resend can POST webhook events (email.bounced, email.complained) to a URL.
   - What's unclear: Whether to add this to the same Cloudflare Worker as unsubscribe, or keep separate.
   - Recommendation: Use the same Cloudflare Worker with different routes (/unsubscribe, /webhook/resend). Simpler to maintain one Worker.

4. **DMARC Reporting Email**
   - What we know: DMARC rua= parameter needs an email address for aggregate reports.
   - What's unclear: Whether to use dettyflightdeals@gmail.com or set up a dedicated address.
   - Recommendation: Use `dmarc@dettyflightdeals.com` if the domain has email receiving set up, otherwise `dettyflightdeals@gmail.com` works fine for reports.

5. **Sending Subdomain vs Root Domain**
   - What we know: Resend recommends subdomains (e.g., `send.dettyflightdeals.com`) to isolate sending reputation.
   - What's unclear: Whether to use root domain or subdomain.
   - Recommendation: Use root domain `dettyflightdeals.com` for simplicity. Subdomain isolation is more important for companies sending marketing + transactional from same domain. This project only sends transactional alerts.

## Sources

### Primary (HIGH confidence)
- Resend Python SDK v2.21.0 -- https://github.com/resend/resend-python (version, installation, send params)
- Resend official docs: Send with Python -- https://resend.com/docs/send-with-python (API usage)
- Resend official docs: Custom Headers -- https://resend.com/docs/dashboard/emails/custom-headers (List-Unsubscribe format)
- Resend official docs: SMTP -- https://resend.com/docs/send-with-smtp (SMTP host/port/credentials)
- Resend official docs: Domain management -- https://resend.com/docs/dashboard/domains/introduction (DNS verification)
- Resend official docs: Account quotas -- https://resend.com/docs/knowledge-base/account-quotas-and-limits (rate limits, bounce/spam thresholds)
- Resend unsubscribe example -- https://github.com/resend/resend-examples/tree/main/with-unsubscribe-url-header
- RFC 8058 -- https://datatracker.ietf.org/doc/html/rfc8058 (one-click unsubscribe specification)
- Codebase analysis -- direct file reads of all 7 email-sending files and 6 workflows

### Secondary (MEDIUM confidence)
- Gmail sender guidelines -- https://support.google.com/a/answer/81126 (bulk sender requirements, enforcement timeline)
- Resend email authentication guide -- https://resend.com/blog/email-authentication-a-developers-guide (SPF/DKIM/DMARC patterns)
- Resend DNS setup guide -- https://dmarcdkim.com/setup/how-to-setup-resend-spf-dkim-and-dmarc-records (DNS record examples)
- Gmail/Yahoo 2025 requirements -- https://securityboulevard.com/2025/11/google-and-yahoo-updated-email-authentication-requirements-for-2025/
- PowerDMARC 2026 guide -- https://powerdmarc.com/google-and-yahoo-email-authentication-requirements/

### Tertiary (LOW confidence)
- Resend pricing details -- https://flexprice.io/blog/detailed-resend-pricing-guide (third-party pricing analysis)
- Cloudflare Workers capabilities -- https://workers.cloudflare.com/ (general platform info, not email-specific)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Resend SDK verified with official docs, version confirmed (2.21.0), SMTP drop-in verified
- Architecture: HIGH -- Codebase fully analyzed, all 7 import points and 6 workflows mapped, migration path clear
- DNS/Authentication: MEDIUM -- Resend auto-generates records (exact values come from dashboard), DMARC patterns verified with official docs
- Pitfalls: HIGH -- Rate limits, bounce thresholds, daily caps all from official Resend docs
- Unsubscribe endpoint: MEDIUM -- RFC 8058 is well-documented, Cloudflare Workers is established, but exact Turso HTTP integration in Worker is untested

**Research date:** 2026-02-11
**Valid until:** 2026-03-13 (30 days -- Resend SDK is stable, Gmail/Yahoo requirements are settled)
