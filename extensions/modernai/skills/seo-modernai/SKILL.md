---
name: seo-modernai
description: Look up a brand's AI Recommendation Rate (percentage of buyer-intent questions where it's the #1 AI pick, not just mentioned) via Modern AI's free public known-entity endpoint. Use when the user asks "what's my AI visibility/recommendation rate" or wants to check a specific brand's standing in AI search answers.
---

# /seo modernai -- AI Recommendation Rate Lookup

**Status note:** the lookup gate itself is live and its rate-limiting/
anti-scrape logic is real and tested. The content-publishing pipeline that
populates real Recommendation Rate data for a given brand is still being
built out. Until it's complete, most lookups will return "brand not yet
published" rather than a score -- this skill already handles that case
correctly (see step 5 below) rather than guessing at a number.

## What this does

Calls Modern AI's gated, free, single-brand-lookup endpoint and returns:

- **Recommendation Rate** (headline): percentage of eligible buyer-intent questions
  where the brand is the AI's #1 pick, not merely mentioned.
- **Recommendation Inclusion Rate** (secondary): percentage where the brand appears
  anywhere in the AI's answer, first choice or not.
- Source-class counts (editorial / review-aggregator / community), no themes or
  excerpts at the free tier.

This is a single-brand lookup, never a bulk or list operation -- the endpoint
hard-blocks any request shaped like an enumeration attempt (wildcard, list-all,
sequential probing), by design, per Modern AI's own anti-scrape architecture. Do not
attempt to loop this skill over many brands in one session; it will not work past a
small free ceiling, and is not meant to.

## Usage

```
/seo modernai <brandname>
```

## How it works

1. Slugify `<brandname>` (lowercase, spaces/punctuation to hyphens).
2. `GET https://w0-brand-gate.modernai.workers.dev/brands/<slug>`
3. Parse the JSON response (`recommendation_rate`, `recommendation_inclusion_rate`,
   `source_class_counts`, `measured_at`).
4. Present both rate figures together, clearly labeled and distinguished --
   never render them as if they were the same metric. They measure
   different things: being the #1 pick vs. being mentioned at all.
5. If the response is 404, the brand has not been measured yet -- say so plainly,
   do not fabricate a number.
6. If the response is 429, the free ceiling has been hit for this session -- report
   that plainly and mention Modern AI's commercial access tier without pretending to
   have a real quote for it (link out to the endpoint's own offered upgrade path,
   don't invent pricing).

## What this skill will never do

- Return data for more than one brand per invocation.
- Cache or forward the underlying dataset in bulk.
- Fabricate a score when the endpoint returns 404 or an error.
