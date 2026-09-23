# Agent access policy: robots.txt, Content-Signal, WAF, Web Bot Auth

Facts checked 2026-09-23 against vendor documentation unless marked
secondary. robots.txt is a **preference signal, not access control**: several
user-triggered agents do not treat it as binding, and TollBit's State of the
Bots reports (secondary) found a meaningful share of AI fetchers reaching
disallowed URLs. Protect private paths with authentication.

## User-agent tokens by purpose

Check the bot that governs the claim you are making. Crawler roles and the
citability rules live in `seo-geo`; this table adds what matters for agents.

| Token | Vendor | Purpose | robots.txt (vendor docs) | Verify by |
|---|---|---|---|---|
| GPTBot | OpenAI | model training | honoured | openai.com/gptbot.json |
| OAI-SearchBot | OpenAI | ChatGPT search index | honoured | openai.com/searchbot.json |
| ChatGPT-User | OpenAI | user-initiated fetches and actions | "may not apply" | openai.com/chatgpt-user.json; Web Bot Auth |
| OAI-AdsBot | OpenAI | ad landing-page checks | see vendor docs | openai.com/adsbot.json |
| ClaudeBot | Anthropic | model training | honoured (incl. Crawl-delay) | claude.com/crawling/bots.json |
| Claude-SearchBot | Anthropic | Claude search-result citability | honoured | claude.com/crawling/bots.json |
| Claude-User | Anthropic | user-initiated fetches | honoured | claude.com/crawling/bots.json |
| PerplexityBot | Perplexity | search index | honoured | perplexity.com/perplexitybot.json |
| Perplexity-User | Perplexity | user-initiated fetches | generally ignored | perplexity.com/perplexity-user.json |
| Google-Agent | Google | user-triggered agent fetches | generally ignored | developers.google.com/static/crawling/ipranges/user-triggered-agents.json |
| Google-Extended | Google | Gemini training/grounding control token, no crawler; never Google Search | honoured | n/a |

Anthropic's help center previously said IP ranges were not published; as of
2026-08 they are at `claude.com/crawling/bots.json`. Do not IP-block
Anthropic's crawlers: a blocked crawler cannot read robots.txt at all.

## RFC 9309 group selection (the most common mistake)

A crawler obeys **only** the most specific group that names its token. If
any group names it, the `*` group is ignored entirely for that crawler. So a
line placed in `User-agent: *` does not reach `GPTBot` when a
`User-agent: GPTBot` group exists.

This matters for `Content-Signal`. Cloudflare's managed robots.txt puts it in
the `*` group, and no normative text says it escapes group selection. When a
site has named groups, repeat the line inside each one.
`agentic_fix.py robots` does exactly that, and never touches Allow/Disallow.

A 5xx on robots.txt tells compliant crawlers to treat the site as fully
disallowed. A 4xx means "no restrictions".

## Content-Signal

Syntax: `Content-Signal: search=yes, ai-input=yes, ai-train=no`.

| Key | Meaning |
|---|---|
| `search` | Building a search index and showing links/snippets (excludes AI summaries) |
| `ai-input` | Using content as input to an AI answer (RAG, grounding) |
| `ai-train` | Training or fine-tuning models |
| `use` | Experimental Cloudflare field (`immediate`, `reference`, `full`); the managed default was `search=yes, ai-train=no, use=reference` in 2026-09 |

Status: Cloudflare's CC0 Content Signals Policy (launched 2025-09-24). The
IETF individual draft `draft-romm-aipref-contentsignals` expired 2026-04-04;
the IETF AIPREF working group vocabulary (`draft-ietf-aipref-vocab`) has not
reached consensus. Google has said it does not act on Content-Signal. Present
it as a stated preference with no confirmed effect.

## Illustrative robots.txt (welcomes agents and search, not training)

```
User-agent: *
Content-Signal: search=yes, ai-input=yes, ai-train=no
Allow: /

User-agent: OAI-SearchBot
User-agent: ChatGPT-User
User-agent: Claude-SearchBot
User-agent: Claude-User
User-agent: PerplexityBot
User-agent: Perplexity-User
Content-Signal: search=yes, ai-input=yes, ai-train=no
Allow: /

User-agent: GPTBot
User-agent: ClaudeBot
User-agent: Google-Extended
Content-Signal: search=yes, ai-input=yes, ai-train=no
Disallow: /

Sitemap: https://example.com/sitemap.xml
```

Blocking a training crawler is a business decision. Never recommend it by
default, and never present it as affecting Google Search. Google-Agent needs no
line because it generally ignores robots.txt; put `/checkout/` and
`/account/` behind authentication.

## WAF and bot management

- Allowlist **verified** bots and signed agents, not user-agent strings.
  Cloudflare, AWS WAF, Akamai, HUMAN and Vercel verify Web Bot Auth or
  published IP ranges; Perplexity documents WAF recipes.
- Keep CAPTCHAs and challenge pages off content and informational pages.
- A WAF that challenges an unverified request carrying `GPTBot` is behaving
  correctly. `agentic_check.py --ua-matrix` shows how unverified traffic is
  treated; confirm real-agent behaviour in WAF logs.

## Web Bot Auth

How agents prove identity: HTTP Message Signatures (RFC 9421), Ed25519 keys,
a key directory at `/.well-known/http-message-signatures-directory`
(`application/http-message-signatures-directory+json`), and `tag="web-bot-auth"`.

- Current draft: `draft-ietf-webbotauth-httpsig-protocol-00` (2026-09-01),
  replacing the earlier Meunier individual drafts.
- `Signature-Agent` is now a **dictionary keyed by signature label**, e.g.
  `Signature-Agent: sig1="https://signer.example"`. The bare-string form is
  outdated; some verifiers may still expect it, so test before relying on it.
- Signers reported: OpenAI (agent and cloud-browser traffic), Google
  (experimental, `https://agent.bot.goog`), Amazon Bedrock AgentCore, Shopify.
  Anthropic and Perplexity signing is claimed only by secondary sources.

Site owners do not publish a key directory unless they operate an agent. They
verify signatures at the edge.

## Reporting rules

- Report training, search and user-fetch access on separate lines.
- Label Content-Signal and Web Bot Auth as draft or policy, with the check
  date.
- Never promise ranking, citation or traffic effects from any robots change.
