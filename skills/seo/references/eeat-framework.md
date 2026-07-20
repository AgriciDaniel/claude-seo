# E-E-A-T Evaluation Framework
## Per Google Quality Rater Guidelines (September 11, 2025); currency-checked June 2026

## Overview

E-E-A-T = **E**xperience, **E**xpertise, **A**uthoritativeness, **T**rustworthiness

**Trust is the most important member of the family** (Google's own wording);
Experience, Expertise, and Authoritativeness support the assessment of Trust.
E-E-A-T is a **concept in the Quality Rater Guidelines**, not a direct ranking
score — it informs the core ranking and helpful-content systems.

> **No "watershed" framing.** Google never characterized the December 2025 (or
> any 2026) core update as "extending E-E-A-T to ALL competitive queries," and
> never published per-industry traffic-drop percentages. Those figures and the
> "watershed" narrative are third-party SEO-blog interpretation — do not assert
> them as Google fact. Google's only on-record description of broad core updates
> is generic ("a regular update designed to better surface relevant, satisfying
> content … from all types of sites").

> **Continuous core updates.** Google now documents (changelog 2025-12-09) that
> it continually makes **smaller, unannounced core updates** between the major
> ones — so content improvements can lift rankings without waiting for the next
> major update. Treat helpful-content evaluation as always-on.

## YMYL (Your Money or Your Life)

Topics requiring the **highest** E-E-A-T standards (E-E-A-T applies broadly, but YMYL carries the highest bar):
- Health and safety
- Financial advice and transactions
- Legal information
- News and current events
- **Elections and civic trust** (added Sept 2025)
- **Democratic processes** (added Sept 2025)
- Groups of people (potential for harm)

---

## Experience (claude-seo internal scoring weight: 20%)

First-hand knowledge and personal involvement with the topic.

### Signals to Check
- [ ] Author has demonstrable first-hand experience with the topic
- [ ] Content includes original photos, screenshots, or data
- [ ] Case studies or real-world examples with specific details
- [ ] Personal process documentation or methodology descriptions
- [ ] Before/after results or outcome data
- [ ] Specific anecdotes that couldn't be fabricated

### Scoring
- **Strong**: Multiple first-hand experience signals, original content
- **Moderate**: Some personal experience evident
- **Weak**: Generic information, no personal touch
- **None**: Clearly AI-generated or scraped content

---

## Expertise (claude-seo internal scoring weight: 25%)

Formal qualifications, training, and demonstrated knowledge.

### Signals to Check
- [ ] Author credentials relevant to topic (bio, certifications)
- [ ] Technical accuracy and depth appropriate for audience
- [ ] Claims supported by evidence or sources
- [ ] Specialized vocabulary used correctly
- [ ] Up-to-date with current developments in the field
- [ ] Byline with author name and credentials visible

### Scoring
- **Strong**: Verified credentials, deep technical accuracy
- **Moderate**: Demonstrable knowledge, some credentials
- **Weak**: Surface-level information, no credentials
- **None**: Factual errors, misinformation

---

## Authoritativeness (claude-seo internal scoring weight: 25%)

Recognition by others as a go-to source.

### Signals to Check
- [ ] Site recognized as authority in its niche
- [ ] Author recognized as expert (external citations, speaking, publications)
- [ ] Content cited by other authoritative sources
- [ ] Industry awards, certifications, or accreditations
- [ ] Consistent publication history in the topic area
- [ ] Featured in reputable media outlets
- [ ] Professional affiliations

### Scoring
- **Strong**: Widely recognized authority, cited by others
- **Moderate**: Growing recognition, some external validation
- **Weak**: No external recognition
- **None**: Negative reputation, known for misinformation

---

## Trustworthiness (claude-seo internal scoring weight: 30%)

The most important factor, overall reliability and transparency.

### Signals to Check
- [ ] Clear contact information (physical address, phone, email)
- [ ] Privacy policy and terms of service
- [ ] HTTPS with valid certificate
- [ ] Transparent about who creates content and why
- [ ] Customer reviews and testimonials
- [ ] Corrections and update history visible
- [ ] No deceptive practices (hidden ads, clickbait)
- [ ] Secure payment processing (for e-commerce)
- [ ] Return/refund policy visible

### Scoring
- **Strong**: Full transparency, verified business, positive reputation
- **Moderate**: Good trust signals, minor gaps
- **Weak**: Missing key trust signals
- **None**: Deceptive practices, scam indicators

---

## September 2025 QRG Updates

### AI Content Assessment
Raters now formally evaluate whether content appears AI-generated:
- AI content is **acceptable** if it demonstrates genuine E-E-A-T
- Low-quality AI content (generic, no unique value) is penalized
- The presence of AI-generated content is not inherently penalizing
- What matters: does the content provide unique value regardless of creation method?

### Markers of Low-Quality AI Content
- Generic phrasing without specificity
- Lack of original insight or unique perspective
- No first-hand experience signals
- Factual inaccuracies
- Repetitive structure across multiple pages
- No author attribution or expertise signals

### Spam Policies (updated 2026-05-15)
- **Expired domain abuse**: Buying expired domains for their backlinks
- **Site reputation abuse**: Using a reputable site to host low-quality content (parasite SEO)
- **Scaled content abuse**: Mass-producing content without value — Google's policy now **explicitly** names "using generative AI tools to generate many pages without adding value" (also covers automated transformations like synonymizing/translating).
- **Back-button hijacking** (NEW, malicious practices): manipulating browser history (`history.pushState`/`replaceState`, including via third-party ad/library scripts) so users can't use the Back button. Announced 2026-04-13; **enforcement live since 2026-06-15** (manual actions + automated demotions).

### AI Overview Evaluation
Raters assess quality of AI-generated summaries in search results.

### RSL 1.0 (Really Simple Licensing)
New machine-readable content licensing standard (December 2025) for AI training:
- Backed by: Reddit, Yahoo, Medium, Quora, Cloudflare, Akamai, Creative Commons
- Allows publishers to specify AI licensing terms
- Augments robots.txt for AI-specific permissions

---

## Experience Signals Are Critical Differentiators

The "Experience" dimension is a key differentiator, especially against scaled/AI content:
- First-person narrative ("I tested this...", "In my experience...")
- Original photos and screenshots (not stock images)
- Specific examples with verifiable details
- Process documentation showing actual work done

**Why:** AI can generate expertise-sounding content but cannot fabricate genuine experience.

---

## Overall Scoring Guide

| Score | Description |
|-------|-------------|
| 90-100 | Exceptional E-E-A-T, authority site, recognized expert, full transparency |
| 70-89 | Strong E-E-A-T, demonstrated expertise, good trust signals |
| 50-69 | Moderate E-E-A-T, some signals, room for improvement |
| 30-49 | Weak E-E-A-T, minimal signals, significant gaps |
| 0-29 | Very low E-E-A-T, no visible signals, potential trust issues |

---

## Improvement Recommendations by Score

### 0-29 (Critical)
1. Add contact information and about page
2. Establish author identity with credentials
3. Implement HTTPS
4. Remove deceptive elements

### 30-49 (Major)
1. Add author bios with credentials
2. Include first-hand experience content
3. Get external citations/mentions
4. Add customer testimonials

### 50-69 (Moderate)
1. Deepen content with original research
2. Build topical authority through content clusters
3. Pursue industry recognition
4. Document processes and methodologies

### 70-89 (Minor)
1. Maintain freshness with regular updates
2. Expand author presence across platforms
3. Pursue speaking/publication opportunities
4. Add video/multimedia demonstrating expertise

### 90-100 (Maintenance)
1. Continue publishing high-quality content
2. Monitor and respond to reputation issues
3. Keep credentials and certifications current
