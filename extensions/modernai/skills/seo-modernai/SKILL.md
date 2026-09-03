---
name: seo-modernai
description: Look up a brand's AI Recommendation Rate (percentage of buyer-intent questions where it's the #1 AI pick, not just mentioned) via Modern AI's free public known-entity endpoint. Use when the user asks "what's my AI visibility/recommendation rate" or wants to check a specific brand's standing in AI search answers.
---

# /seo modernai: AI Recommendation Rate Lookup

Run one command, get a brand's real AI Recommendation Rate, or a clear
"not yet published" answer. Free, no API key.

**Status note:** the endpoint is live. A brand with a published
measurement returns a real score. A brand not yet measured returns
"brand not yet published" (see step 5 below); this skill never guesses
a number.

## What this does

A single free lookup returns:

- **Recommendation Rate** (headline): percentage of eligible buyer-intent questions
  where the brand is the AI's #1 pick, not merely mentioned.
- **Recommendation Inclusion Rate** (secondary): percentage where the brand appears
  anywhere in the AI's answer, first choice or not.
- Source-class counts (editorial / review-aggregator / community), no themes or
  excerpts at the free tier.

This is a single-brand lookup, never a bulk or list operation. Do not attempt to
loop this skill over many brands in one session; the endpoint blocks that pattern
and will not return data past a small free ceiling.

## Usage

```
/seo modernai <brandname>
```

## How it works

1. Slugify `<brandname>` (lowercase, spaces/punctuation to hyphens).
2. `GET https://discovery.modernai.io/brands/<slug>`
3. Parse the JSON response (`recommendation_rate`, `recommendation_inclusion_rate`,
   `source_class_counts`, `measured_at`).
4. Present both rate figures together, clearly labeled and distinguished.
   Never render them as if they were the same metric. They measure
   different things: being the #1 pick vs. being mentioned at all.
5. If the response is 404, the brand has not been measured yet. Say so plainly;
   do not fabricate a number.
6. If the response is 429, the free ceiling has been hit for this session. Report
   that plainly and mention Modern AI's commercial access tier without pretending to
   have a real quote for it (link out to the endpoint's own offered upgrade path,
   don't invent pricing).

## What this skill will never do

- Return data for more than one brand per invocation.
- Cache or forward the underlying dataset in bulk.
- Fabricate a score when the endpoint returns 404 or an error.
