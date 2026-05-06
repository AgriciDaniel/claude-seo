# Power PT Gym — SEO Master Audit

**Site:** [powerptgym.co.uk](https://powerptgym.co.uk)
**Business:** Power PT — friendly personal training gym, niche = adults 40+
**Address:** 14 Bradford Road, Guiseley, **LS20 8NH** (West Yorkshire / Leeds metro)
**Phone:** 01943 884 488 · **Email:** hello@powerptgym.co.uk
**Stack:** WordPress + Yoast SEO + Yoast Local SEO, fronted by Cloudflare
**Audit date:** 2026-05-06
**Data sources:** direct site crawl, DataForSEO Labs (UK), DataForSEO SERP (Guiseley/Leeds/UK, mobile), DataForSEO Backlinks

---

## 1. Executive summary

Power PT is in a stronger SEO position than the surface read suggests, but the upside is being throttled by three specific things:

1. **Service pages are essentially invisible.** `/personal-training/` ranks for 5 keywords (£2.40/mo of organic value); the homepage carries 214 keywords and £304/mo. Two blog posts do more discovery work than every service page combined.
2. **Local-pack visibility is split between map-pack and organic.** Power PT is local-pack #2 for *"personal trainer guiseley"* (234 Google reviews, 5★) but is *not in the local pack* for *"gym guiseley"* (260 searches/month) — even though the site ranks **organic #2** for that exact term. This is a Google Business Profile category problem, not a website problem.
3. **The backlink profile is being polluted by negative-SEO spam** — Telegram-channel link injections, PBN domains, SEO reseller anchors. Domain spam score is 43/100. Page-level spam is still acceptable (10), but it needs cleaning.

There are also a series of standard hygiene issues — 25+ thin pages indexable, an `/personal-training-classes-2/` duplicate, missing security headers, postcode formatting inconsistent — that are easy to fix.

The single highest-ROI move is **adding "Gym" or "Fitness centre" as a secondary GBP category** (without changing primary). That alone is likely to unlock the local pack for "gym guiseley" — 260 monthly searches with proven organic intent on the same page.

---

## 2. Scorecard

| Area | Status | Comment |
|---|---|---|
| HTTPS, redirects, robots.txt, sitemaps | ✅ Pass | Clean apex/www/HTTP/slash handling, Yoast sitemap_index |
| LocalBusiness schema | ✅ Strong | Full `ExerciseGym` JSON-LD, geo, hours, areaServed |
| Brand SERP / Knowledge Graph | ✅ Strong | KG claimed, 234 Google reviews (5★), social profiles linked |
| Local pack — *"personal trainer guiseley"* | ✅ Pos #2 | 248 (True PT) → **234 (Power)** → 11 (Daley) |
| Organic — *"gym guiseley"* (260/mo) | ✅ Pos #2 | But absent from map pack — see §4.4 |
| Indexability of utility pages | 🚨 Fail | 25+ thin/utility pages indexable, no `noindex` |
| Duplicate `/personal-training-classes-2/` | 🚨 Fail | Both URLs self-canonical |
| Click-to-call phone | 🚨 Fail | Plain text, no `tel:` link |
| Embedded Google Map / GBP link on site | 🚨 Fail | Neither on locations nor contact page |
| Service-page content depth | 🚨 Fail | `/personal-training/` ranks for 5 keywords vs homepage 214 |
| Postcode formatting consistency | ⚠️ Issue | Site shows `LS208NH`; Google KG and Fresha show correct `LS20 8NH` |
| Security headers (HSTS, CSP, etc.) | ⚠️ Issue | Only `referrer-policy` + `x-frame-options` |
| WordPress login surface | ⚠️ Issue | `/wp-login.php` and `/wp-json/` both 200 |
| Backlink profile | 🚨 Fail | Domain spam 43, Telegram/PBN/SEO-reseller anchor injections |
| Citation coverage | ⚠️ Issue | No links from Yell, Bark, Cylex, Yelp despite competitors using all four |
| Render-blocking JS | ⚠️ Issue | 42 scripts, 5 async/defer; SpamKill + Infusionsoft heavy |
| GBP categories | 🚨 Fail | Likely missing "Gym" / "Fitness centre" secondary category |

---

## 3. What's working — preserve and amplify

| Asset | Evidence | What to do |
|---|---|---|
| Brand authority on Google | KG panel claimed, 234 reviews, 5★, sitelinks for brand search | Keep gathering reviews; reply to every one |
| Schema markup | Single clean `@graph` with `ExerciseGym`, geo, hours, payment, areaServed | Just fix the postcode and `addressLocality` (use Guiseley not Leeds) |
| Local pack for "personal trainer guiseley" | Live position #2 (mobile, geo Guiseley) | Defend with reviews + GBP posts |
| Organic for "gym guiseley" cluster | #2 organic, multiple variants in pos 2–4 (260/mo, 140/mo, etc.) | Add GBP category to capture the map pack too |
| Two workhorse blog posts | `/strength-training-vs-cardio…` 23 kw / £122/mo · `/losing-weight-after-50…` 14 kw / £23/mo | Build clusters around each — these are proven topical authority |
| Recent ranking trend | 178 new positions, 57 up vs 30 down | Whatever's been done recently is working — keep doing it |

---

## 4. Findings by area

### 4.1 Indexability — 🚨 must fix

`page-sitemap.xml` exposes 49+ URLs. The following return 200 with **no `<meta name="robots" content="noindex">`** and should be set to `noindex,follow`:

| URL | Why noindex |
|---|---|
| `/thank-you/`, `/thanks/`, `/contact-thanks/`, `/trialist-thanks/`, `/ebook-thanks/`, `/calendly-thanks/` | Confirmation pages |
| `/payment_cancelled/`, `/payment-failed/`, `/confirmation/`, `/payment/` | Transaction flow |
| `/newsletter-success/`, `/callback-confirmation/`, `/submission-received/` | Form submission |
| `/parq/`, `/leaver-survey/`, `/satisfaction-survey/`, `/referral-form/` | Internal forms |
| `/inbody-yes/`, `/inbody-no/`, `/review-yes/`, `/review-no/`, `/review-confirmed/`, `/review-declined/` | Internal Y/N branches |
| `/tryus-lp-m/`, `/tryus-lp-f/`, `/waitlist-lp-m/`, `/waitlist-lp-f/`, `/tryus-thanks-meta/` | Paid landing pages |
| `/terms-disagree/`, `/terms-agreed/` | Internal terms flow |

**Set in:** Yoast → bulk editor → robots-meta = noindex,follow.

### 4.2 Duplicate page — 🚨 must fix

- `/personal-training-classes/` and `/personal-training-classes-2/` both exist, both self-canonical. Title only differs by " 2".
- **Action:** decide which is the canonical, 301-redirect the other (Redirection plugin or Yoast Premium).

### 4.3 Service-page underperformance — 🚨 the biggest content gap

| Page | Keywords ranked | ETV/mo | Needed |
|---|---|---|---|
| `/personal-training/` | 5 | £2.40 | Full rebuild — no clear H1, no FAQ, no Service schema, no pricing, weak alt text |
| `/small-group-personal-training/` | 1 | £0.10 | Same issues |
| `/classes/` | 1 | £0.20 | Same issues |
| `/mens-fitness/` | 0 in top 100 | — | Not even on the leaderboard |
| `/womens-fitness/` | 0 in top 100 | — | Not even on the leaderboard |
| `/trainers/` | 1 | £0.20 | E-A-T page; needs trainer bios with credentials |

These pages should be ranking for `personal trainer guiseley`, `small group personal training leeds`, `fitness classes guiseley`, etc. Right now the homepage takes those SERPs because the service pages don't have enough content depth or local-intent signals.

**Service-page rebuild template** (per page):
- H1 with `<service> + Guiseley` or `…+ Leeds area`
- Lead paragraph with city + postcode + nearest landmark
- `Service` schema or `LocalBusiness/hasOfferCatalog`
- 6–10-question FAQ block with `FAQPage` schema (this is the single biggest GEO/AI-Overviews lever for a local PT business)
- Price range or "from £X" — even a band builds trust
- Embedded Google Map iframe of 14 Bradford Road
- 3+ testimonials specific to that service (PT, not SGPT, etc.)
- Internal links from the two strong blog posts

### 4.4 Local SEO — strong base, two specific gaps

**NAP consistency:**
- Site shows `14 Bradford Road, Guiseley, LS208NH`
- Google Knowledge Graph has the correct `14 Bradford Rd, Guiseley, Leeds LS20 8NH`
- Fresha listing has the correct `14 Bradford Rd, Guiseley, Leeds LS20 8NH`
- **Action:** fix the site to `LS20 8NH` (with the space) everywhere — body copy, footer, schema. Pick one canonical brand name (`Power PT` or `Power Personal Training Gym`) and use it consistently.

**Schema fix:**
```json
"address": {
  "addressLocality": "Guiseley",        // currently "Leeds"
  "addressRegion": "West Yorkshire",
  "postalCode": "LS20 8NH",             // currently "LS208NH"
  "streetAddress": "14 Bradford Road",
  "addressCountry": "GB"
},
"areaServed": ["Guiseley", "Yeadon", "Rawdon", "Otley", "Menston", "Horsforth", "Leeds"]
```

**Click-to-call:**
- Phone is plain text on every page checked. Wrap as `<a href="tel:+441943884488">01943 884 488</a>`.

**Missing trust signals on `/locations/` and `/contact/`:**
- No embedded Google Map (postcode-lookup widget only)
- No anchor link to the GBP listing (despite "5★ 197 reviews" being shown via plugin)
- No anchor link to "Get directions"
- Add an iframe-embedded GBP map and a "Read our 234 Google reviews" button

**🚨 GBP category gap (highest ROI single fix):**
- Site ranks organic #2 for "gym guiseley" (260/mo)
- Site does NOT appear in the map pack for "gym guiseley" — that pack is Unit One Gym, DW Fitness First, PureGym
- Google's classifier almost certainly has Power PT's primary GBP category set to "Personal trainer". For the "gym" query class, you need a secondary category of **"Gym"** or **"Fitness centre"**.
- **Action in GBP:** Edit profile → Categories → Add secondary `Gym` (or `Fitness centre`). Do not change primary. Expected upside: 260 × 30% click share = ~78 high-intent clicks/month.

### 4.5 Technical hygiene

| Item | Current | Target |
|---|---|---|
| HSTS | ❌ Missing | `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` |
| X-Content-Type-Options | ❌ Missing | `nosniff` |
| Permissions-Policy | ❌ Missing | `geolocation=(), microphone=(), camera=()` |
| CSP | ❌ Missing | Start with report-only |
| `/wp-login.php` | 200 (open) | Restrict by IP, install WPS Hide Login + WP 2FA |
| `/wp-json/` | 200 | Block unauthenticated user enumeration |
| `/xmlrpc.php` | 403 ✅ | Already blocked |
| `/readme.html` | 403 ✅ | Already blocked |

Add the security headers via Cloudflare → Rules → Transform Rules → Modify Response Header.

### 4.6 Performance

Direct curl is fast (TTFB 53ms via Cloudflare cache), but the rendered page has issues that hurt real-user metrics:

- **HTML weight 401 KB** for the homepage — heavy
- **45 images on the homepage**, only 8 with `loading="lazy"` — add lazy to the other 37
- **42 `<script>` tags, 5 async/defer** — heaviest blockers are SpamKill (`protect.spamkill.dev`) and Infusionsoft (`nwi562.infusionsoft.com`)
- **Google Fonts loaded without preconnect** — add `<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>`
- **No `<link rel="preload">` for the LCP hero** (`Power-personal-training-gym-full-20.webp`)

Quick wins: `preconnect` for fonts + Infusionsoft origin, `preload` for the LCP image, defer SpamKill/Infusionsoft (load on form-focus if possible), lazy-load remaining images.

### 4.7 Backlinks — 🚨 spam profile needs cleaning

| Metric | Value |
|---|---|
| Backlinks | 62 |
| Referring domains | 56 |
| **Domain spam score** | **43/100** |
| Page-level (target) spam | 10/100 (still OK) |
| First seen | 2023-11-13 |

**Spam evidence — toxic anchor injections:**

| Anchor | Backlinks | What it is |
|---|---|---|
| `OUR TELEGRAM CHANEL https://t.me/s/quarterlinks25` | 9 | Telegram link injection campaign |
| `JOIN OUR TELEGRAM https://t.me/s/darksidelinks` | 2 | Telegram link injection |
| `https://powerptgym.co.uk – Skyrocket your Ahrefs DR…` | 1 | SEO reseller spam |
| `https://powerptgym.co.uk – Increase your site's backlinks…` | 1 | SEO reseller spam |

These were almost certainly not built by Power PT. They look like negative-SEO spray or residue from a low-quality vendor. Google is mostly ignoring them already, but a disavow file is worth filing.

**Disavow file generated:** `audits/powerptgym/disavow.txt` (see §6 for instructions to upload).

### 4.8 Citation gap — competitors have these, Power PT doesn't

UK fitness directories present in competitor link profiles but **NOT** linking to Power PT:

| Directory | Effort to claim | Why |
|---|---|---|
| **Yell.com** | 30 min | UK #1 directory; ranks p1 for `personal trainers guiseley` |
| **Bark.com** | 30 min | Lead-gen platform; ranks p1 |
| **Cylex UK** | 30 min | `guiseley.cylex-uk.co.uk` ranks for the brand and category |
| **Yelp.co.uk** | 30 min | Standard cross-engine citation |
| **Bing Places** | 15 min | Bing equivalent of GBP |
| **Apple Maps Connect** | 30 min | iPhone search = Apple Maps |
| **FreeIndex / Hotfrog / Scoot** | 1 hr total | Lower quality but citation consistency matters |
| **Yorkshire.com** | claim listing | Already exists, ranks #6 for the brand — claim it and ensure correct NAP + link |
| **Fresha.com** | claim listing | Already lists you with correct NAP — claim and add booking link |

For each, use the **canonical NAP**: `Power Personal Training Gym, 14 Bradford Road, Guiseley, LS20 8NH, 01943 884 488, hello@powerptgym.co.uk`.

---

## 5. Keyword opportunity matrix

### 5.1 Already ranking (defend)

| Keyword | Vol/mo | Position | Page |
|---|---|---|---|
| power personal training gym | 210 | #1 | / |
| power gym guiseley | 110 | #1 | / |
| power gym | 720 | #2 | / |
| **gym guiseley** | **260** | **#2 organic (not in pack)** | / |
| guiseley gyms | 140 | #2 | / |
| **personal trainer guiseley** | **20** | **Local #2 + Organic #3** | / |
| burn fat weights or cardio | 320 | #4 | /strength-training-vs-cardio… |
| cardio vs weight training for fat loss | 320 | #4 | " |
| losing weight after 50 | 110 | #5 | /losing-weight-after-50… |
| losing weight at 50 | 140 | #6 | " |

### 5.2 Priority target keywords (build pages)

| Keyword | Vol/mo | CPC | Difficulty | Why now |
|---|---|---|---|---|
| **menopause fitness** | 720 | £1.27 | Low | Page 1 has medical sites + PureGym; gap for a real PT brand |
| **personal trainer leeds** | 590 | £3.89 | Medium | Local pack is Claire Grogan (36 reviews) → Ultimate Performance (232) → Shape Club (44). Power PT has 234 reviews — outperforms two of three on social proof |
| **personal training leeds** | 590 | £3.89 | Medium | Same SERP as above |
| **gym guiseley** | 260 | £1.52 | Medium | Already organic #2 — pack-only fix is a GBP category change |
| **strength training over 50** | 90 | £2.23 | Medium | Existing content gap, perfect niche |
| **over 40s fitness** | 90 | £0.37 | Low | Niche match, low CPC = low competition |
| **menopause fitness coach** | (in PAS for menopause fitness) | — | Low | Direct service term |
| **personal trainer over 40** | 10 | — | Low | Tiny volume, very high intent |

### 5.3 Adjacent local terms (when site 2 opens)

`personal trainer yeadon`, `personal trainer rawdon`, `personal trainer otley`, `personal trainer menston`, `personal trainer horsforth`, `gym aireborough` — all under 50/mo each but cheap to build coverage for once each town has a real reason to be a landing page.

### 5.4 SERP intel — *"personal trainer leeds"*

Live mobile SERP from Leeds:

| Slot | Listing | Notes |
|---|---|---|
| Local pack #1 | Claire Grogan Female Fitness Trainer Leeds | 36 reviews, 5★ |
| Local pack #2 | Ultimate Performance Personal Trainers Leeds | 232 reviews, 5★ |
| Local pack #3 | Shape Club Personal Training Gym | 44 reviews, 5★ |
| Organic #1 | sport.leeds.ac.uk (University) | |
| Organic #2 | Instagram (liftwithlaurenpt) | |
| Organic #3 | clairegrogan.uk | |
| Organic #4 | leeds-pt.co.uk | |
| Organic #6 | puregym.com | |
| Organic #7 | craigparnham.com (**Horsforth-based** — proves Guiseley-area PTs can rank for "Leeds") | |

Power PT is not in the top 20 for this term. With 234 reviews, the local pack is winnable when GBP geographic relevance to Leeds CC is improved (categories, service area, posts mentioning Leeds neighbourhoods).

### 5.5 SERP intel — *"menopause fitness"*

| Rank | Domain | Type |
|---|---|---|
| #1 | AI Overview | (synthetic) |
| Organic #1 | mymenopausecentre.com | Davina McCall content |
| #3 | Bupa | Brand authority article |
| #5 | NHS | .gov |
| #4 (organic) | owningyourmenopause.com | Direct competitor |
| #6 | fitnessinmenopause.com | Direct competitor |
| #7 | News.exeter.ac.uk | Research |
| #8 | PureGym | Tip article |

- AI Overview is present — passage-level citability matters (clean H2 + 40-60 word answers wins citations)
- "People also search" includes `menopause fitness coach near me` and `menopause fitness coach certification` — niche service-search intent

### 5.6 Competitor gap (True PT vs Power PT)

DataForSEO's intersection (keywords True PT ranks for that Power PT doesn't, top 20):

The gap is mostly **geographic expansion** — True PT ranks in Wetherby (`pride gym wetherby` 590/mo, `gyms in wetherby` 590/mo, `5 star fitness wetherby`), Doncaster, Wakefield, Rotherham, Grimsby, Corby. They've grown by adding locations.

This tells you something strategic: True PT's growth model is multi-location. Power PT has two strategic options:

1. **Niche depth** — own "over 40s personal training" topically across the UK, then convert that authority locally. Cheaper, faster compound returns.
2. **Geographic breadth** — when Site 2 opens, replicate True PT's playbook with a dedicated `/locations/<town>/` URL pattern.

Recommend (1) first; (2) when Site 2 lands.

---

## 6. Prioritised action plan

Effort: 🟢 ≤2h · 🟡 half-day · 🔴 multi-day. Impact: ★★★ high · ★★ medium · ★ small.

### Tier 1 — this week (~1 dev day total)

| # | Action | Effort | Impact | Owner |
|---|---|---|---|---|
| 1 | Add **"Gym" or "Fitness centre" as a secondary GBP category** (do not change primary) | 🟢 | ★★★ | Marketing |
| 2 | Set `noindex,follow` on the 25+ thin/utility URLs in §4.1 (Yoast bulk editor) | 🟢 | ★★ | Dev |
| 3 | 301-redirect `/personal-training-classes-2/` → `/personal-training-classes/` | 🟢 | ★ | Dev |
| 4 | Wrap every visible phone number in `tel:+441943884488` | 🟢 | ★★ | Dev |
| 5 | Embed GBP Google Map iframe on `/locations/` and `/contact/` | 🟢 | ★★ | Dev |
| 6 | Add "Read our 234 Google reviews" button linking to GBP profile, on `/locations/`, `/contact/`, footer | 🟢 | ★★ | Dev |
| 7 | Fix postcode site-wide to `LS20 8NH` (text + JSON-LD) | 🟢 | ★★ | Dev |
| 8 | Update schema `addressLocality` from `Leeds` → `Guiseley`; expand `areaServed` array | 🟢 | ★★ | Dev |
| 9 | Submit disavow file to Google Search Console — `audits/powerptgym/disavow.txt` | 🟢 | ★★ | Marketing |
| 10 | Add HSTS, X-Content-Type-Options, Permissions-Policy via Cloudflare Transform Rules | 🟢 | ★ | Dev |
| 11 | Restrict `/wp-login.php` (Cloudflare WAF rule + WPS Hide Login plugin) | 🟢 | ★ | Dev |

### Tier 2 — next 2–4 weeks (~3 dev days + content time)

| # | Action | Effort | Impact |
|---|---|---|---|
| 12 | Rebuild `/personal-training/` as a Guiseley-first service page with H1, FAQ + FAQPage schema, pricing range, embedded map, 3 testimonials, internal links from blog | 🔴 | ★★★ |
| 13 | Same template applied to `/small-group-personal-training/`, `/mens-fitness/`, `/womens-fitness/`, `/classes/` | 🔴 | ★★★ |
| 14 | Build `/personal-trainer-leeds/` landing page — frame as "Leeds-area personal training, based in Guiseley, serving Leeds North & West" | 🟡 | ★★★ |
| 15 | Build `/menopause-fitness/` pillar page linking to all menopause-related blog posts; `FAQPage` schema | 🟡 | ★★★ |
| 16 | Claim Yorkshire.com listing; verify Fresha listing; ensure both link to the site with brand anchor | 🟢 | ★★ |
| 17 | Submit to Yell, Bark, Cylex, Yelp, Bing Places, Apple Maps Connect, FreeIndex (all with canonical NAP) | 🟡 | ★★ |
| 18 | Add `<link rel="preconnect">` for `fonts.gstatic.com` and `nwi562.infusionsoft.com`; preload LCP hero | 🟢 | ★ |
| 19 | Add `loading="lazy"` to remaining ~37 homepage images | 🟢 | ★ |
| 20 | Defer SpamKill + Infusionsoft scripts (load on form-focus where possible) | 🟡 | ★ |

### Tier 3 — months 2–3 (compound growth)

| # | Action | Effort | Impact |
|---|---|---|---|
| 21 | Topic-cluster build around `/strength-training-vs-cardio…` — sibling posts, `lower-back fat loss`, `weight training for women over 40`, `is cardio bad for menopause` | 🔴 | ★★★ |
| 22 | Topic-cluster build around `/losing-weight-after-50…` — `weight loss perimenopause`, `losing belly fat over 50`, `protein intake over 50` | 🔴 | ★★★ |
| 23 | Internal-link audit: every fitness blog post must contextually link to a service page (PT, SGPT, classes) | 🟡 | ★★ |
| 24 | Earn 5–10 high-quality UK backlinks: Wharfedale Observer guest column, Yorkshire Post over-40s fitness pitch, Pitchero local-club pages, Yorkshire Live | 🔴 | ★★ |
| 25 | When Site 2 opens, build dedicated `/locations/<town>/` URL with its own LocalBusiness schema and embedded map | 🔴 | ★★ |
| 26 | Build neighbouring-town landing pages: Yeadon, Rawdon, Otley, Menston, Horsforth | 🟡 | ★ |

---

## 7. Measurement plan

After Tier 1 ships, monitor weekly for 4 weeks:

| Metric | Tool | Baseline | Target after 30 days |
|---|---|---|---|
| Local-pack appearance for "gym guiseley" | Manual SERP check from Guiseley | Not in pack | In pack (any position) |
| GBP "discovery searches" | GBP Insights | (unknown) | +20% |
| GBP "calls" | GBP Insights | (unknown) | +15% |
| Branded impressions | GSC | (unknown) | flat (don't lose them) |
| Non-branded impressions | GSC | (unknown) | +10% |
| Avg position for `gym guiseley` | GSC | #2 organic | #1 or local pack |
| Domain spam score | DataForSEO | 43 | drop to <30 within 90 days post-disavow |
| Service-page keyword count | DataForSEO ranked_keywords | 5 (PT page) | >25 within 60 days of rebuild |

---

## 8. Files in this audit

| File | What's in it |
|---|---|
| `master.md` | This file — consolidated audit + action plan |
| `disavow.txt` | Google Search Console disavow file (upload via [search.google.com/search-console/disavow-links](https://search.google.com/search-console/disavow-links)) |
| `keyword-opportunities.md` | Detailed keyword-cluster intelligence: SERP reads for "personal trainer leeds" and "menopause fitness", PAA questions to seed FAQs, niche keyword shortlist |
| `competitor-gap.md` | True PT vs Power PT keyword-gap analysis with strategic implications |

---

## 9. Open questions for the client

1. Is GBP currently claimed by you/your team, and what's the **primary** category set to right now?
2. Have you previously hired any SEO/link-building vendor? (Helps explain the spam anchors.)
3. Is "Site 2" already announced internally with a town/postcode? Affects how soon to build the second `/locations/<town>/` URL.
4. Do you have GA4 + GSC connected? If yes, we can layer the next pass with real traffic and CTR data once those connectors are wired in (the GA4 MCP disconnected mid-audit).
5. Is the Infusionsoft/Keap stack staying? Several script-weight wins are easier if it goes.

---

*Generated 2026-05-06 with DataForSEO Labs (UK), DataForSEO SERP (Guiseley/Leeds/UK, mobile), DataForSEO Backlinks, and direct site crawl.*
