# Wireframe Templates: IST/SOLL Patterns

Generate before (IST) and after (SOLL) wireframes showing what the page currently
looks like vs what it should look like based on SERP expectations.

## Core Principles

1. **Ultra-concrete placeholders**: Not "add CTA" but "add pricing CTA with annual
   savings badge below hero, linking to /pricing#enterprise"
2. **Mobile-first**: Assume 375px viewport first; above-the-fold (~600px) must
   contain the most critical element for the page type
3. **Semantic HTML**: Output as section outline with HTML5 elements

## IST Generation

Parse the current page and map to this structure:

```
IST: [URL]
├── ABOVE FOLD
│   ├── [element]: "[actual content]"
│   └── [element]: "[actual content]"
├── MAIN CONTENT
│   ├── [section]: "[summary]" (~XXX words)
│   └── [section]: "[summary]" (~XXX words)
├── SUPPORTING
│   └── [element]: "[description]"
└── FOOTER — [elements present]

Missing from SERP expectations:
- [element]: [why it matters]
```

## SOLL Templates by Page Type

### 1. Landing Page

```
<header> Nav: logo + 3-4 links max + primary CTA button </header>
<section class="hero">
  H1: [value proposition matching target keyword]
  Subhead: [supporting benefit] | CTA: [primary action]
  Trust line: "Trusted by [X] companies including [logos]"
</section>
<section class="social-proof"> 3-5 logo badges + key metric </section>
<section class="features"> 3 blocks: icon + H3 + 2-line desc (address PAA) </section>
<section class="how-it-works"> 3-step process with numbered icons </section>
<section class="testimonial"> Quote + photo + name + title + company </section>
<section class="pricing"> 2-3 tiers, recommended highlighted, annual toggle </section>
<section class="faq"> 5-7 PAA questions, FAQPage schema </section>
<section class="final-cta"> Repeat hero CTA with urgency </section>
```

### 2. Blog Post

```
<article>
  <header> H1 | Author + photo + credentials | Date + Updated | Reading time </header>
  <nav class="toc"> Jump links to H2 sections </nav>
  <section class="intro"> Hook + thesis + TL;DR box (above fold) </section>
  <section> H2: [cluster 1] — address PAA #1 </section>
  <section> H2: [cluster 2] — address PAA #2 </section>
  <section> H2: [cluster 3] — comparison table if SERP warrants </section>
  <section> H2: [cluster 4] — image/diagram </section>
  <section class="expert-quote"> Blockquote from SME (E-E-A-T) </section>
  <section> H2: FAQ — remaining PAA questions </section>
  <footer> Author bio | Related posts (3) | CTA: newsletter </footer>
</article>
```

### 3. Product Page

```
<section class="product-hero">
  H1: [product + benefit keyword] | Gallery: 4-6 images
  Price + savings indicator | CTA: "Add to Cart" (above fold)
  Trust: stars + review count + shipping
</section>
<section class="key-features"> 4-6 bullets: feature + benefit </section>
<section class="specifications"> Table: specs, dimensions, compatibility </section>
<section class="reviews"> aggregateRating + 5 reviews, filterable </section>
<section class="comparison"> "Why choose this" table (if SERP shows intent) </section>
<section class="faq"> Product PAA questions </section>
<section class="related"> 4 complementary products </section>
```

### 4. Comparison Page

```
<header>
  H1: "[A] vs [B]: [year] Comparison"
  Quick verdict: "Best for [use case]: [winner]"
</header>
<section class="matrix"> Feature table: check/cross/partial icons </section>
<section class="reviews">
  H2: [A] — pros, cons, best for, pricing
  H2: [B] — pros, cons, best for, pricing
</section>
<section class="verdict"> Persona recs: "Choose A if...", "Choose B if..." </section>
<section class="faq"> Comparison PAA questions </section>
```

### 5. Service Page

```
<section class="hero"> H1: [service + location] | CTA: "Free Consultation" </section>
<section class="problem"> Empathy-driven problem statement </section>
<section class="process"> 3-5 numbered steps </section>
<section class="results"> 2-3 case studies with before/after metrics </section>
<section class="credentials"> Certs, experience, team </section>
<section class="pricing"> Packages or "starting at" </section>
<section class="faq"> PAA questions </section>
<section class="cta"> Repeat CTA + contact form </section>
```

### 6. Local Page

```
<section class="hero">
  H1: [service] in [city] — [business name]
  CTA: "Call Now" + "Get Directions" | NAP displayed
</section>
<section class="map"> Google Map embed + landmark directions </section>
<section class="services"> Location-specific services (unique content) </section>
<section class="reviews"> Review widget with reviewer locations </section>
<section class="hours"> openingHoursSpecification + "open now" </section>
<section class="about"> Team, history, community (location-specific) </section>
```

### 7. Tool / Interactive

```
<section class="tool" id="tool">
  H1: Free [Tool Name] — [purpose]
  Input: [fields/dropdowns/upload] (ABOVE FOLD)
  CTA: "Calculate" / "Generate" / "Check" | Output zone
</section>
<section class="instructions"> How to Use — 3 steps max </section>
<section class="explanation"> Educational depth for SEO </section>
<section class="faq"> Tool-specific PAA </section>
<section class="related-tools"> 3-4 related tools </section>
```

### 8. Hybrid (Education + Product)

```
<section class="hero">
  H1: [education + product keyword] | Dual CTA: "Learn More" + "Try Free"
</section>
<section class="education"> Address awareness-stage PAA </section>
<section class="solution"> Bridge: how [Product] solves this </section>
<section class="features"> 3-4 benefit-framed features </section>
<section class="proof"> Case study or testimonial </section>
<section class="cta"> Match journey stage from SERP analysis </section>
<section class="faq"> Mix of educational + product PAA </section>
```

## Placeholder Rules

When filling SOLL placeholders, always be specific:

| Bad (vague) | Good (concrete) |
|-------------|-----------------|
| "Add a CTA" | "Add 'Start Free Trial' button below hero, green #2d6a4f, links to /signup" |
| "Include social proof" | "Add 3 logos (G2, Capterra, TrustRadius) + '4.8/5 from 2,300 reviews'" |
| "Add FAQ section" | "Add 5 FAQs from PAA: 'Is X safe?', 'How much does X cost?', ..." |
| "Improve trust" | "Add SSL badge + 'SOC 2 certified' banner + customer count" |
| "More content" | "Add 400-word section under H2 'How [Feature] Works' with diagram" |
