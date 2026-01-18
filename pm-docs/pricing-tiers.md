# Detty Flight Deals - Pricing Tiers Research

**Date:** January 18, 2026
**Purpose:** Define deal tiers (Normal/Good/Great/WOW) for all Tier 1 destinations

---

## MVP Coverage

**Origins (7):** JFK, EWR, IAD, ATL, DFW, IAH, BOS
**Destinations (11):** Lagos, Accra, Abuja, Dakar, Freetown, Abidjan, Lomé, Cotonou, Douala, Yaoundé, Kinshasa
**Total Routes:** 77

---

## Deal Tier Framework

Based on user input and market research:

| Tier | Definition | Alert Policy |
|------|------------|--------------|
| **Normal** | Typical market price | Don't alert |
| **Good** | 20-30% below normal | Alert (Free + Premium) |
| **Great** | 35-50% below normal | Alert (Occasional Free, All Premium) |
| **WOW** | 50%+ below normal (mistake fare territory) | Alert (Premium only) |

---

## Tier 1 Destinations - Pricing Research

### West Africa

#### Lagos, Nigeria (LOS)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Lagos-Murtala-Muhammed-LOS), [Expedia](https://www.expedia.com/lp/flights/jfk/los/new-york-to-lagos), [Momondo](https://www.momondo.com/flights/lagos)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,200-1,500 |
| 25th percentile | ~$980-1,100 |
| Best recent deals | $685-800 |
| Direct flights | Yes (Delta from JFK/ATL) |
| Peak season | December (+13% avg) |
| Cheap months | September, October, January |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,200+ | Don't alert |
| Good | $900-1,200 | Alert |
| Great | $700-900 | Alert |
| WOW | <$700 | Premium only |

---

#### Abuja, Nigeria (ABV)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Abuja-ABV), [Expedia](https://www.expedia.com/lp/flights/jfk/abv/new-york-to-abuja), [Momondo](https://www.momondo.com/flights/abuja)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,200-1,800 |
| 25th percentile | ~$800-1,000 |
| Best recent deals | $700-800 |
| Direct flights | No (all connecting) |
| Peak season | December (+avg increase) |
| Cheap months | September, November |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,200+ | Don't alert |
| Good | $900-1,200 | Alert |
| Great | $700-900 | Alert |
| WOW | <$700 | Premium only |

---

#### Accra, Ghana (ACC)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Accra-Kotoka-ACC), [Expedia](https://www.expedia.com/Cheap-Flights-To-Accra.d280.Travel-Guide-Flights), [Momondo](https://www.momondo.com/flights/accra)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,200-1,400 |
| 25th percentile | ~$975-1,100 |
| Best recent deals | $700-850 |
| Direct flights | Yes (Delta/United from JFK/IAD) |
| Peak season | December, July-August |
| Cheap months | May, April |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,100+ | Don't alert |
| Good | $850-1,100 | Alert |
| Great | $650-850 | Alert |
| WOW | <$650 | Premium only |

---

#### Dakar, Senegal (DSS)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Dakar-Blaise-Diagne-DSS), [Delta](https://www.delta.com/us/en/flight-deals/africa-flights/flights-to-dakar), [Momondo](https://www.momondo.com/flights/senegal)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,000-1,200 |
| 25th percentile | ~$850-950 |
| Best recent deals | $400-600 |
| Direct flights | Yes (Delta from JFK) |
| Peak season | December |
| Cheap months | May, March |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,000+ | Don't alert |
| Good | $750-1,000 | Alert |
| Great | $550-750 | Alert |
| WOW | <$550 | Premium only |

---

#### Freetown, Sierra Leone (FNA)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Freetown-Lungi-Intl-FNA), [Expedia](https://www.expedia.com/Cheap-Flights-To-Freetown.d1231.Travel-Guide-Flights), [Momondo](https://www.momondo.com/flights/freetown)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,100-1,300 |
| 25th percentile | ~$1,000-1,100 |
| Best recent deals | $800-1,000 |
| Direct flights | No |
| Peak season | December (+13%) |
| Cheap months | October, January |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,100+ | Don't alert |
| Good | $900-1,100 | Alert |
| Great | $700-900 | Alert |
| WOW | <$700 | Premium only |

---

#### Abidjan, Ivory Coast (ABJ)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Abidjan-Felix-H-Boigny-ABJ), [Air France](https://wwws.airfrance.us/en-us/flights-to-abidjan), [Cheapflights](https://www.cheapflights.com/flights-to-abidjan/)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,400-1,600 |
| 25th percentile | ~$1,000-1,200 |
| Best recent deals | $850-950 |
| Direct flights | No |
| Peak season | July, December |
| Cheap months | October, February |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,300+ | Don't alert |
| Good | $1,000-1,300 | Alert |
| Great | $800-1,000 | Alert |
| WOW | <$800 | Premium only |

---

#### Lomé, Togo (LFW)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Lome-LFW), [Air France](https://wwws.airfrance.us/en-us/flights-to-lome), [Momondo](https://www.momondo.com/flights/lome)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,400-1,600 |
| 25th percentile | ~$1,000-1,200 |
| Best recent deals | $500-800 |
| Direct flights | No |
| Peak season | December |
| Cheap months | January |
| Note | Often cheaper to fly to Accra and drive |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,300+ | Don't alert |
| Good | $1,000-1,300 | Alert |
| Great | $750-1,000 | Alert |
| WOW | <$750 | Premium only |

---

#### Cotonou, Benin (COO)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Cotonou-COO), [Expedia](https://www.expedia.com/Cheap-Flights-To-Cotonou.d898.Travel-Guide-Flights), [Momondo](https://www.momondo.com/flights/cotonou)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,200-1,500 |
| 25th percentile | ~$950-1,100 |
| Best recent deals | $850-950 |
| Direct flights | No |
| Peak season | July (+11%) |
| Cheap months | November |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,200+ | Don't alert |
| Good | $900-1,200 | Alert |
| Great | $700-900 | Alert |
| WOW | <$700 | Premium only |

---

### Central Africa

#### Douala, Cameroon (DLA)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Douala-DLA), [Air France](https://wwws.airfrance.us/en-us/flights-to-douala), [Momondo](https://www.momondo.com/flights/douala)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,000-1,200 |
| 25th percentile | ~$800-950 |
| Best recent deals | $570-800 |
| Direct flights | No |
| Peak season | December (+7%) |
| Cheap months | April, May, January |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,000+ | Don't alert |
| Good | $800-1,000 | Alert |
| Great | $600-800 | Alert |
| WOW | <$600 | Premium only |

---

#### Yaoundé, Cameroon (NSI)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Yaounde-Nsimalen-NSI), [Expedia](https://www.expedia.com/Cheap-Flights-To-Yaounde.d3886.Travel-Guide-Flights), [Air France](https://wwws.airfrance.us/en-us/flights-to-yaounde)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,000-1,200 |
| 25th percentile | ~$800-950 |
| Best recent deals | $560-700 |
| Direct flights | No |
| Peak season | July |
| Cheap months | February, January, August |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,000+ | Don't alert |
| Good | $800-1,000 | Alert |
| Great | $600-800 | Alert |
| WOW | <$600 | Premium only |

---

#### Kinshasa, DRC (FIH)
**Sources:** [KAYAK](https://www.kayak.com/flight-routes/United-States-US0/Kinshasa-N-djili-FIH), [Air France](https://wwws.airfrance.us/en-us/flights-to-kinshasa), [Momondo](https://www.momondo.com/flights/kinshasa)

| Data Point | Value |
|------------|-------|
| Average roundtrip | $1,800-2,000 |
| 25th percentile | ~$1,200-1,400 |
| Best recent deals | $700-950 |
| Direct flights | No (2+ stops typical) |
| Peak season | December (+5%), June (+8%) |
| Cheap months | May |
| Note | Most expensive Tier 1 destination |

| Tier | Price Range | Threshold |
|------|-------------|-----------|
| Normal | $1,500+ | Don't alert |
| Good | $1,100-1,500 | Alert |
| Great | $850-1,100 | Alert |
| WOW | <$850 | Premium only |

---

## Summary Table - All Tier 1 Destinations

| Destination | Code | Normal | Good | Great | WOW |
|-------------|------|--------|------|-------|-----|
| Lagos | LOS | $1,200+ | $900-1,200 | $700-900 | <$700 |
| Abuja | ABV | $1,200+ | $900-1,200 | $700-900 | <$700 |
| Accra | ACC | $1,100+ | $850-1,100 | $650-850 | <$650 |
| Dakar | DSS | $1,000+ | $750-1,000 | $550-750 | <$550 |
| Freetown | FNA | $1,100+ | $900-1,100 | $700-900 | <$700 |
| Abidjan | ABJ | $1,300+ | $1,000-1,300 | $800-1,000 | <$800 |
| Lomé | LFW | $1,300+ | $1,000-1,300 | $750-1,000 | <$750 |
| Cotonou | COO | $1,200+ | $900-1,200 | $700-900 | <$700 |
| Douala | DLA | $1,000+ | $800-1,000 | $600-800 | <$600 |
| Yaoundé | NSI | $1,000+ | $800-1,000 | $600-800 | <$600 |
| Kinshasa | FIH | $1,500+ | $1,100-1,500 | $850-1,100 | <$850 |

---

## Alert Policy Summary

| Tier | Free Users | Premium Users |
|------|------------|---------------|
| **Good** | Yes (all) | Yes |
| **Great** | Occasional (tease) | Yes (all) |
| **WOW** | No | Yes |
| **Premium/Biz/First** | No | Yes |
| **Points/Award deals** | No | Yes |

---

## Notes on Pricing Variability

1. **Seasonal swings:** December prices can be 10-15% higher across all routes
2. **Booking window:** Best prices typically 45-90 days out
3. **Day of week:** Thursday departures often 10-15% cheaper than Sunday
4. **Mistake fares:** Can drop to 50-70% below normal, last hours not days
5. **Direct vs. connecting:** Direct flights (Lagos, Accra, Dakar) tend to have more predictable pricing

---

## Sources

- [KAYAK Flight Routes](https://www.kayak.com)
- [Expedia Flight Deals](https://www.expedia.com)
- [Momondo Flight Search](https://www.momondo.com)
- [Google Flights](https://www.google.com/travel/flights)
- [Skyscanner](https://www.skyscanner.com)
- [Air France US](https://wwws.airfrance.us)
- [Delta Air Lines](https://www.delta.com)
