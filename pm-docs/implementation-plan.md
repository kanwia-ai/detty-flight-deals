# Detty Flight Deals - MVP Implementation Plan

**Date:** January 18, 2026
**Target Launch:** January 25, 2026
**Estimated Effort:** 3-4 days

---

## Tech Stack Recommendation

### Keep (Working Well)
| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Backend** | Python 3.11 | Already working, simple, proven |
| **Flight Data** | `fast-flights` | Free, works, 6-month track record |
| **RSS Parsing** | `feedparser` | Lightweight, stable |
| **Automation** | GitHub Actions | Free tier sufficient, already configured |
| **State** | JSON file in repo | Simple, works for MVP scale |

### Add (New for MVP)
| Component | Technology | Rationale |
|-----------|------------|-----------|
| **Email List** | Buttondown | Free tier (100 subs), simple API, built-in unsubscribe |
| **Landing Page** | Static HTML + Vercel | Zero cost, fast deploys, form embeds |
| **Email Signup** | Buttondown embed form | Native integration, no custom code |

### Why Buttondown?
- **Free tier**: 100 subscribers (sufficient for launch)
- **Simple API**: Single endpoint to broadcast to entire list
- **Built-in features**: Unsubscribe handling, open rate tracking
- **Easy upgrade**: $9/mo when you exceed 100 subs
- **Developer-friendly**: Well-documented API, webhook support

### Why NOT Other Options
| Option | Why Skip |
|--------|----------|
| ConvertKit | Overkill for MVP, more complex |
| Loops | Paid after 1000, we won't hit that quickly |
| Google Sheets | Fragile, manual, poor deliverability |
| Custom database | Over-engineering for MVP |

---

## Implementation Tasks

### Phase 1: Backend Expansion (0.5 days)

#### Task 1.1: Expand Routes Configuration
**File:** `deal_finder.py`

**Changes:**
1. Add 4 new US origins:
   ```python
   ORIGINS = ["JFK", "EWR", "IAD", "ATL", "DFW", "IAH", "BOS"]
   ```

2. Add 4 new Africa destinations with pricing-tiers.md thresholds:
   ```python
   DESTINATIONS = {
       # Existing
       "LOS": {"name": "Lagos", "region": "West Africa", "good": 1200, "great": 900, "wow": 700},
       "ABV": {"name": "Abuja", "region": "West Africa", "good": 1200, "great": 900, "wow": 700},
       "ACC": {"name": "Accra", "region": "West Africa", "good": 1100, "great": 850, "wow": 650},
       "DSS": {"name": "Dakar", "region": "West Africa", "good": 1000, "great": 750, "wow": 550},
       "DLA": {"name": "Douala", "region": "Central Africa", "good": 1000, "great": 800, "wow": 600},
       "NSI": {"name": "Yaoundé", "region": "Central Africa", "good": 1000, "great": 800, "wow": 600},
       "FIH": {"name": "Kinshasa", "region": "Central Africa", "good": 1500, "great": 1100, "wow": 850},
       # New
       "FNA": {"name": "Freetown", "region": "West Africa", "good": 1100, "great": 900, "wow": 700},
       "ABJ": {"name": "Abidjan", "region": "West Africa", "good": 1300, "great": 1000, "wow": 800},
       "LFW": {"name": "Lomé", "region": "West Africa", "good": 1300, "great": 1000, "wow": 750},
       "COO": {"name": "Cotonou", "region": "West Africa", "good": 1200, "great": 900, "wow": 700},
   }
   ```

3. Total: 7 origins × 11 destinations = **77 routes**

**Test:**
- Run in TEST_MODE with 1 week search window
- Verify all 77 routes are searched
- Verify price thresholds trigger correctly

---

#### Task 1.2: Implement Deal Tier Logic
**File:** `deal_finder.py`

**New function:**
```python
def classify_deal_tier(price, destination):
    """Classify a deal into tiers: WOW, Great, Good, or Normal"""
    thresholds = DESTINATIONS[destination]
    if price < thresholds["wow"]:
        return "WOW"
    elif price < thresholds["great"]:
        return "Great"
    elif price < thresholds["good"]:
        return "Good"
    else:
        return "Normal"
```

**Update deal collection:**
- Add `tier` field to each deal
- Filter out "Normal" deals (don't alert)
- Sort deals by tier priority (WOW > Great > Good)

---

#### Task 1.3: Update Mistake Fare Monitor
**File:** `mistake_fare_monitor.py`

**Changes:**
1. Add new destinations to THRESHOLDS:
   ```python
   THRESHOLDS = {
       # Existing cities
       "lagos": 700, "accra": 650, "dakar": 550, "abuja": 700,
       "douala": 600, "yaounde": 600, "kinshasa": 850,
       # New cities
       "freetown": 700, "abidjan": 800, "lome": 750, "cotonou": 700,
       # Countries
       "nigeria": 700, "ghana": 650, "senegal": 550, "cameroon": 600,
       "congo": 850, "drc": 850, "sierra leone": 700, "ivory coast": 800,
       "togo": 750, "benin": 700,
   }
   ```

2. Use "wow" thresholds × 0.75 for mistake fare detection

---

### Phase 2: Buttondown Integration (0.5 days)

#### Task 2.1: Set Up Buttondown Account
**Manual steps:**
1. Create account at buttondown.email
2. Create email list "Detty Flight Deals"
3. Configure sender settings
4. Get API key
5. Add `BUTTONDOWN_API_KEY` to GitHub repo secrets

#### Task 2.2: Integrate Buttondown API
**File:** `deal_finder.py`

**New function:**
```python
def send_via_buttondown(subject, body_html, body_text):
    """Send email to all Buttondown subscribers"""
    api_key = os.environ.get("BUTTONDOWN_API_KEY")
    if not api_key:
        print("No Buttondown API key, falling back to direct email")
        return send_email(subject, body_text)

    response = requests.post(
        "https://api.buttondown.email/v1/emails",
        headers={"Authorization": f"Token {api_key}"},
        json={
            "subject": subject,
            "body": body_html,
            "status": "sent"  # Immediately send to all subscribers
        }
    )

    if response.status_code == 201:
        print(f"Email sent via Buttondown to all subscribers")
        return True
    else:
        print(f"Buttondown error: {response.text}")
        return False
```

**Update requirements.txt:**
```
fast-flights>=1.0.0
feedparser>=6.0.0
requests>=2.28.0
```

**GitHub Actions update:**
- Add `BUTTONDOWN_API_KEY` secret
- Keep SMTP as fallback

---

### Phase 3: Email Template Improvement (0.5 days)

#### Task 3.1: Create HTML Email Template
**New file:** `email_templates.py`

**Deal alert email:**
```html
<div style="font-family: -apple-system, sans-serif; max-width: 600px;">
  <h1 style="color: #1a1a1a;">🔥 {deal_count} Deal(s) to Africa!</h1>

  {for each deal}
  <div style="border: 2px solid #22c55e; border-radius: 8px; padding: 16px; margin: 16px 0;">
    <div style="font-size: 12px; color: #666; text-transform: uppercase;">
      {tier} DEAL
    </div>
    <h2 style="margin: 8px 0; color: #1a1a1a;">
      {origin} → {destination_name} ${price}
    </h2>
    <p style="color: #666; margin: 8px 0;">
      {percentage}% below normal (avg ${normal_price})
    </p>
    <p style="margin: 8px 0;">
      📅 Best dates: {dates}<br>
      💰 Price range found: ${min_price} - ${max_price}
    </p>
    <a href="{google_flights_url}" style="display: inline-block; background: #22c55e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">
      Book Now →
    </a>
  </div>
  {end for}

  <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
  <p style="color: #666; font-size: 12px;">
    You're receiving this because you signed up for Detty Flight Deals.<br>
    <a href="{unsubscribe_url}">Unsubscribe</a>
  </p>
</div>
```

**Tier-specific styling:**
- WOW: Red/orange border, "🚨 WOW DEAL" badge
- Great: Green border, "✨ GREAT DEAL" badge
- Good: Blue border, "💰 GOOD DEAL" badge

---

### Phase 4: Landing Page (1-2 days)

#### Task 4.1: Create Landing Page
**New files:** `landing-page/index.html`, `landing-page/style.css`

**Structure:**
```
landing-page/
├── index.html
├── style.css
├── og-image.png  (social share image)
└── favicon.ico
```

**Page sections:**
1. **Hero**: "Never miss a cheap flight to Africa"
   - Subhead: "Get deal alerts for Lagos, Accra, and 9 more cities"
   - Email signup form (Buttondown embed)

2. **Value props** (3 columns):
   - "🎯 Africa-focused" - Not tourist destinations, diaspora cities
   - "⚡ Real-time alerts" - Deals last hours, we catch them in minutes
   - "📧 Set and forget" - We watch, you book when it's time

3. **Coverage map/list**:
   - 11 destinations (Tier 1)
   - 7 US origins
   - "77 routes monitored daily"

4. **Sample deal** (social proof):
   - Screenshot of an actual alert
   - "JFK → Lagos $589" example

5. **Footer**:
   - "Free forever for good deals"
   - "Premium coming September 2026"

#### Task 4.2: Deploy to Vercel
**Steps:**
1. Create `vercel.json` for static site config
2. Connect GitHub repo to Vercel
3. Set up custom domain (dettyflightdeals.com)
4. Configure Buttondown embed form

---

### Phase 5: Testing & Launch (0.5 days)

#### Task 5.1: End-to-End Testing
1. Sign up via landing page
2. Verify subscriber added to Buttondown
3. Trigger manual deal finder run
4. Verify email received with new format
5. Test unsubscribe link
6. Test mistake fare monitor

#### Task 5.2: Launch Checklist
- [ ] Buttondown account created
- [ ] API key added to GitHub secrets
- [ ] Landing page deployed to Vercel
- [ ] Custom domain configured
- [ ] deal_finder.py updated (77 routes)
- [ ] mistake_fare_monitor.py updated
- [ ] Email template updated
- [ ] Test email sent successfully
- [ ] README updated with new scope

---

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `deal_finder.py` | Modify | Add origins, destinations, tier logic, Buttondown |
| `mistake_fare_monitor.py` | Modify | Add new destinations, update thresholds |
| `requirements.txt` | Modify | Add `requests` |
| `email_templates.py` | New | HTML email templates |
| `.github/workflows/find_deals.yml` | Modify | Add BUTTONDOWN_API_KEY secret |
| `landing-page/index.html` | New | Landing page |
| `landing-page/style.css` | New | Styling |
| `vercel.json` | New | Vercel config |
| `README.md` | Modify | Update with new scope |

---

## Environment Variables

### Current
- `SMTP_EMAIL` - Gmail sender address
- `SMTP_PASSWORD` - Gmail app password
- `NOTIFY_EMAIL` - Fallback recipient

### New
- `BUTTONDOWN_API_KEY` - Buttondown API key for email delivery

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| fast-flights rate limited | Medium | Add delays between searches, reduce frequency |
| 77 routes too slow | Medium | Parallelize searches, reduce weeks searched |
| Buttondown free tier hit | Low | Launch should be <100 subs initially |
| Landing page delays launch | Low | Can launch backend first, page later |

---

## Success Criteria

### Technical
- [ ] 77 routes searched successfully
- [ ] Deals classified into correct tiers
- [ ] Emails delivered via Buttondown
- [ ] Landing page live and collecting signups

### Launch
- [ ] First 50 signups within 1 week
- [ ] First deal alert sent to subscribers
- [ ] Email open rate >40%
- [ ] Zero critical bugs

---

## Implementation Order

1. **Backend first** (can test without landing page)
   - Expand routes in deal_finder.py
   - Implement tier logic
   - Update mistake_fare_monitor.py

2. **Buttondown integration** (enables multi-user)
   - Set up account
   - Integrate API
   - Test delivery

3. **Email templates** (improves UX)
   - Create HTML templates
   - Add tier styling

4. **Landing page** (enables signups)
   - Build page
   - Deploy to Vercel
   - Embed Buttondown form

5. **Launch** 🚀

---

## Checkpoint

**Implementation plan ready. Approve to start building?**

Once approved, I'll begin with Task 1.1 (expanding routes configuration).
