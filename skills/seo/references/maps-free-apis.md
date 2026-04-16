<!-- Updated: 2026-03-23 -->
# Free Maps APIs for claude-seo

## Source Key

- **Docs**: Official API documentation for each service
- **Policy**: Official usage policies and terms

---

## Overpass API (Best Free Option for Competitor Discovery)

**Base URL:** `https://overpass-api.de/api/interpreter`
**Docs:** https://wiki.openstreetmap.org/wiki/Overpass_API
**License:** ODbL (attribution required: "Data from OpenStreetMap")

### Rate Limits

- Slot-based: ~2 concurrent queries per IP
- Guideline: ~10,000 requests/day, ~1 GB/day download
- Default timeout: 180 seconds, 512 MiB memory per query
- Use `[timeout:25]` for lighter queries

### Query Templates

**Restaurants within 5km radius:**
```bash
curl -s "https://overpass-api.de/api/interpreter" \
  --data-urlencode 'data=[out:json][timeout:25];(node["amenity"="restaurant"](around:5000,LAT,LNG);way["amenity"="restaurant"](around:5000,LAT,LNG););out body;>;out skel qt;'
```

**All businesses on a street:**
```bash
curl -s "https://overpass-api.de/api/interpreter" \
  --data-urlencode 'data=[out:json][timeout:25];way["name"="STREET_NAME"]["addr:city"="CITY"];(._;>;);out body;'
```

**Competitor POIs by category in bounding box:**
```bash
curl -s "https://overpass-api.de/api/interpreter" \
  --data-urlencode 'data=[out:json][timeout:25];(node["amenity"="dentist"](SOUTH,WEST,NORTH,EAST);way["amenity"="dentist"](SOUTH,WEST,NORTH,EAST););out body;>;out skel qt;'
```

### Key OSM Tags for Local SEO

| Category | OSM Tag | Examples |
|----------|---------|---------|
| Food & Drink | `amenity=restaurant`, `amenity=cafe`, `amenity=fast_food` | Restaurants, cafes, takeaway |
| Healthcare | `amenity=dentist`, `amenity=doctors`, `amenity=pharmacy` | Dental, medical, pharmacy |
| Legal | `office=lawyer`, `office=notary` | Law firms, notaries |
| Home Services | `craft=plumber`, `craft=electrician`, `craft=hvac` | Trades, contractors |
| Retail | `shop=supermarket`, `shop=clothes`, `shop=car` | All retail types |
| Automotive | `shop=car`, `shop=car_repair`, `amenity=fuel` | Dealers, repair, gas |
| Hospitality | `tourism=hotel`, `tourism=motel`, `tourism=guest_house` | Accommodation |
| Financial | `amenity=bank`, `office=insurance`, `office=accountant` | Banks, insurance, accounting |

### Response Fields

Each element returns: `id`, `lat`, `lon`, `tags` object containing `name`, `phone`, `website`, `opening_hours`, `addr:street`, `addr:housenumber`, `addr:city`, `addr:postcode`, `cuisine`, `brand`, etc.

### Limitations

- No reviews, ratings, or popularity data
- No GBP-specific information
- Data quality varies by region (excellent in Europe, inconsistent elsewhere)
- Volunteer-contributed data; may be outdated
- Interactive tester: https://overpass-turbo.eu/

---

## Geoapify Places API (Structured POI Search)

**Base URL:** `https://api.geoapify.com/v2/places`
**Docs:** https://apidocs.geoapify.com/docs/places/
**Pricing:** https://www.geoapify.com/pricing

### Free Tier

- **3,000 credits/day** (1 credit = 20 places returned)
- 5 requests/second
- Requires API key (free registration, no credit card)
- **Caching and storage explicitly permitted** (unlike Google)

### Query Template

```bash
curl -s "https://api.geoapify.com/v2/places?categories=catering.restaurant&filter=circle:LNG,LAT,5000&limit=20&apiKey=YOUR_KEY"
```

### Category Hierarchy

Uses dot-separated categories: `catering.restaurant`, `commercial.supermarket`, `healthcare.dentist`, `service.financial.accounting`, `commercial.vehicle.car_dealer`

### Response Format

GeoJSON FeatureCollection. Each feature has `properties`: `name`, `city`, `state`, `postcode`, `country`, `street`, `housenumber`, `phone`, `website`, `categories`, `lat`, `lon`, `place_id`, `formatted` (full address string)

### Advantages Over Raw Overpass

- Cleaner, structured responses
- Aggregated data (OSM + OpenAddresses + WhosOnFirst + GeoNames)
- Hierarchical category taxonomy
- No rate limit surprises (clear credit system)

---

## Nominatim (Geocoding Only)

**Base URL:** `https://nominatim.openstreetmap.org`
**Docs:** https://nominatim.org/release-docs/latest/api/Overview/
**Policy:** https://operations.osmfoundation.org/policies/nominatim/

### Rate Limits (STRICT)

- **1 request/second** (absolute)
- Must include valid `User-Agent` header (stock library agents rejected)
- Auto-complete queries **forbidden**
- Bulk geocoding **forbidden** on public instance
- Repeated identical queries trigger bans (cache results)

### Forward Geocoding

```bash
curl -s "https://nominatim.openstreetmap.org/search?q=123+Main+St+Austin+TX&format=json&addressdetails=1" \
  -H "User-Agent: claude-seo/1.7.0"
```

### Reverse Geocoding

```bash
curl -s "https://nominatim.openstreetmap.org/reverse?lat=40.7128&lon=-74.0060&format=json" \
  -H "User-Agent: claude-seo/1.7.0"
```

### Response Fields

`place_id`, `lat`, `lon`, `display_name`, `importance`, `category`, `type`, `address` object (house_number, road, city, state, postcode, country)

### Best Use

- Address-to-coordinates conversion for geo-grid center point
- Reverse geocoding to validate business addresses
- **NOT suitable** for business listing discovery (use Overpass or Geoapify)

---

## Rate Limit Enforcement Pattern

```bash
# Nominatim: enforce 1 req/sec with sleep
for addr in "${addresses[@]}"; do
  curl -s "https://nominatim.openstreetmap.org/search?q=${addr}&format=json" \
    -H "User-Agent: claude-seo/1.7.0"
  sleep 1.1
done

# Overpass: no explicit rate limit, but use reasonable timeouts
# If HTTP 429 returned, implement exponential backoff

# Geoapify: 5 req/sec on free tier, no explicit enforcement needed
```

---

## Comparison Table

| Feature | Overpass | Geoapify | Nominatim |
|---------|---------|----------|-----------|
| Business discovery | Yes (tags) | Yes (categories) | Limited |
| Reviews/ratings | No | No | No |
| Geocoding | No | Yes | **Best** |
| Rate limit | ~10k/day | 3k credits/day | 1 req/sec |
| Auth required | No | API key | No |
| Caching allowed | Yes | **Explicitly** | **Required** |
| Data quality | Regional | Aggregated | Regional |
| Best for | Radius competitor search | Structured POI search | Address resolution |
