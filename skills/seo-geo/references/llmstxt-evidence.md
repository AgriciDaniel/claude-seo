# `/llms.txt` — evidence-based reframe (June 2026)

## TL;DR

`/llms.txt` is **not currently consumed by any major AI search system**, and
**Google now states in its own docs that Google Search ignores it**. Generate
one anyway as low-cost optionality for non-Google AI services, but never present
it as a Google ranking or citation lever in any claude-seo report.

## Primary-source evidence

| Source | Date | What they said |
|---|---|---|
| **Google AI optimization guide** (docs) | 2026-06-29 | You don't need llms.txt/AI-text files for Google Search (incl. generative AI features); doing so "won't harm (nor help) your visibility or rankings in Google Search, **as Google Search ignores them**." |
| **John Mueller** (Google) | 2026 | Called the llms.txt discovery/differentiation use case "a dead end." |
| **John Mueller** (Google) — Reddit + Bluesky | 2025 | "No AI system currently uses llms.txt." Compared the file to deprecated meta keywords. |
| **Gary Illyes** (Google) — Search Central Live | July 2025 | Google has no plans to support llms.txt. |
| **SE Ranking** — 300k-domain study | November 2025 | Among the 50 most AI-cited domains, **only one** had an `/llms.txt`. |
| **OtterlyAI** — server-log audit | 2025 | **0.1%** of AI-bot traffic targets `/llms.txt` (84 of 62,100 requests). |
| **Anthropic, Stripe, Cloudflare, NVIDIA** — published files | 2024–2025 | All publish `llms.txt`. **None** have stated their crawlers consume third-party `llms.txt` files. |

## Where it does matter

`llms.txt` is increasingly consumed by **AI coding agents** (Cursor,
Continue, Cline, Claude Code) when loading per-library documentation.
Mintlify auto-generates `/llms.txt` and `/llms-full.txt` for thousands
of developer-docs sites. For a developer-tooling site, publishing
`llms.txt` is a net win — it helps agents quote the docs accurately.

For a non-developer business site, the value is purely defensive: zero
cost, possible future-optionality if a major AI provider eventually
adopts it.

## How claude-seo treats `llms.txt`

- `seo-geo` audits **report presence** of `/llms.txt` and `/llms-full.txt`.
- The audit notes whether the file is well-formed (Mintlify-style markdown).
- The audit explicitly does **not** assign citation-ranking weight to it.
- If the user asks to generate one, claude-seo produces a minimal valid
  example and a banner stating "Google Search ignores llms.txt (Google docs,
  2026-06-29); no major LLM provider has confirmed consumption; ship for
  non-Google optionality, not for citation".

## When this guidance changes

Update this file (and the seo-geo audit copy) when:

- Any major AI search system (Google AI Overviews, ChatGPT Search,
  Perplexity, Bing Copilot) publishes documentation confirming
  `llms.txt` consumption.
- OtterlyAI or SE Ranking publish a follow-up study showing a measurable
  inflection in `/llms.txt` request rate.
- John Mueller / Gary Illyes / equivalent retract their 2025 statements.

Last verified: 2026-06-21.
