# Google AI Optimization Guide — primary-source synthesis (June 2026)

Google published a dedicated **AI optimization guide** under Search Central
docs (under the new "Generative AI fundamentals" section; announced via the
Search Central blog 2026-05-15, doc last updated 2026-06-29). Its position is
the most-cited primary source for how AI Overviews and AI Mode interact with
Search ranking. Every claude-seo audit that touches GEO should treat this doc
as the canonical reference and reject community claims that contradict it.

**Primary source:**
https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
(announcing blog: https://developers.google.com/search/blog/2026/05/a-new-resource-for-optimizing)

> **Companion doc — third-party SEO tools (2026-06-05):** Google published
> "Using third-party SEO tools, services, and advice." No tool guarantees
> rankings; third-party tools have **no access to Google's internal ranking
> data**; Google does not endorse vendors; evaluate AEO/GEO claims against
> official guidance; Search Console is the authoritative first-party source.
> claude-seo's scores are heuristics, not Google-internal signals — state this
> honestly in reports. Source:
> https://developers.google.com/search/docs/fundamentals/third-party-seo

## TL;DR

> "Optimizing for generative AI search is **still SEO** from Google's
> perspective. AEO and GEO are rebranded labels for the same work."
> — Google, AI optimization guide

AI Overviews and AI Mode are grounded in the same ranking and quality systems
as classic Search. Two AI techniques layer on top:

1. **RAG / grounding** — retrieves indexed pages, generates a response with
   clickable source links.
2. **Query fan-out** — issues multiple related sub-queries and pulls in
   additional results before answering.

**Eligibility floor:** a page must be **indexed and eligible to be shown with
a snippet in Google Search** to appear in any AI feature. There is no separate
"AI index". Everything that follows is SEO fundamentals applied through this
lens.

## The myth-busting section (most important)

Google explicitly says you **do NOT need to**:

| Claim Google rejects | Source |
|---|---|
| Create `llms.txt` or AI-specific markup files | AI optimization guide §"Myths" |
| "Chunk" your content into small pieces for AI | Same |
| Rewrite content for AI with specific phrasings or long-tail keyword variations | Same |
| Chase inauthentic mentions across blogs / forums / videos | Same |
| Over-invest in structured data specifically for AI features | Same |

What **does** matter, per Google: unique, non-commodity, first-hand content.
Their example contrasts "7 Tips for First-Time Homebuyers" (commodity) with
"Why We Waived the Inspection & Saved Money: A Look Inside the Sewer Line"
(lived experience).

> **Cross-reference:** the llms.txt myth is independently confirmed by
> [[llmstxt-evidence]] (Mueller, Illyes, SE Ranking 300k-domain study,
> OtterlyAI server-log audit). Both files must stay aligned.

## The "creating helpful content" companion guide

The AI optimization guide links to Google's E-E-A-T guidance:

**Primary source:**
https://developers.google.com/search/docs/fundamentals/creating-helpful-content

Key actionable test — **Who / How / Why**:

- **Who** created it — bylines expected where readers expect them; author
  background pages required for YMYL.
- **How** it was created — especially for AI-assisted content; disclose
  process where readers would reasonably ask.
- **Why** it exists — "to help people," not "to attract search clicks."

YMYL ("Your Money or Your Life") topics get extra weight: health, finance,
safety. Sept 2025 QRG expanded YMYL to include political / social topics.

Google's listed warning signs to self-audit against:

- Writing to a target word count (there isn't one)
- Entering niches with no expertise just for traffic
- Faking publication-date freshness
- Mass content churn for "freshness" signals

## AI content policy

**Primary source:**
https://developers.google.com/search/blog/2023/02/google-search-and-ai-content
(plus the Search Essentials spam policies)

Generative AI content is fine if it meets Search Essentials. It crosses into
spam when used to **scale low-value pages** (QRG §4.6.5 scaled content abuse,
§4.6.6 low-effort main content).

Two operational requirements with concrete enforcement surfaces:

1. **Merchant Center — AI-generated product images:** must carry IPTC
   `DigitalSourceType: TrainedAlgorithmicMedia` metadata. See
   `skills/seo-images/SKILL.md` for the audit + injection pattern.
2. **AI-generated product titles and descriptions:** must be separately
   specified and labeled as AI-generated in the merchant feed.

## Forward-looking: agent-friendly pages and WebMCP

The AI optimization guide pivots near the end to **AI agents** — not just
summarizers. Agents interact with sites through three channels: screenshots
plus a vision model, raw HTML/DOM, and the browser accessibility tree.

Full audit criteria: `skills/seo-technical/references/agent-friendly-pages.md`.

The guide also covers **WebMCP** (proposed standard for direct site to agent
interaction. Chrome 149 origin-trial and 2026-06-09 sign-up claims are
unresolved, with three shipped Lighthouse audits) and **UCP** (Universal
Commerce Protocol, open standard co-developed with Shopify, Etsy, Wayfair,
Target, Walmart; Google-confirmed reference implementation in AI Mode in
Search; ucp.dev lists 2026-04-08 as the latest date-based release, non-Google
and hedged). UCP audit criteria:
`skills/seo-ecommerce/references/ucp-universal-commerce-protocol.md`.

## How claude-seo treats this guide

1. `seo-geo` audits cite this URL as the authoritative source whenever the
   user asks about AEO/GEO frameworks.
2. The myth-busting list above gates community-sourced AI-SEO recommendations
   — if a recommendation contradicts Google's stated position, flag it.
3. Where a third-party claim and Google contradict, claude-seo defers to
   Google and notes the contradiction explicitly.
4. `seo-ecommerce` and `seo-images` enforce the two operational requirements
   above for sites using AI to generate product content.

## Last verified

2026-06-21. Re-check the source doc each quarter. Update this file whenever:

- Google publishes new myth-busting / clarification.
- Any of the linked policy docs revise eligibility or enforcement language.
- The UCP / WebMCP standards advance (UCP has ucp.dev-listed date-based spec
  2026-04-08, non-Google and hedged; WebMCP Chrome 149 origin-trial status is
  unresolved).
