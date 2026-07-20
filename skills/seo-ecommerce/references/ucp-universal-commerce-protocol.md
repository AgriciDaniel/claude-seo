# UCP — Universal Commerce Protocol (June 2026)

UCP is a Google-initiated open standard, co-developed with Shopify, Etsy,
Wayfair, Target, and Walmart (20+ endorsers), plus payment partners (Stripe,
Visa, Mastercard, Adyen, Amex). Its purpose: let **AI agents discover,
negotiate, and transact with merchants without one-off integrations**. It is
interoperable with **A2A** (Agent2Agent), **AP2** (Agent Payments Protocol),
and **MCP**.

For commerce sites, UCP sits next to **Google Merchant Center feeds** and
**Google Business Profile** as the third leg of agent-era discovery. Google
confirms a first reference implementation for conversational buying in AI Mode
in Search; broader Universal Cart rollout details are reported from Google I/O
2026 keynote coverage; not confirmed on a Google-owned source.

**Primary sources (canonical, stable):**
- Google merchant developer guide: https://developers.google.com/merchant/ucp
  (and /merchant/ucp/guides/ucp-profile)
- Spec / overview: https://ucp.dev. ucp.dev lists **2026-04-08** as the latest
  release in its **date-based versioning** scheme (YYYY-MM-DD); revalidate
  before using it as a hard validator.

## What UCP is and isn't

| What it is | What it isn't |
|---|---|
| A capability-declaration + negotiation protocol | A new payment processor |
| Transport-agnostic (REST, MCP, A2A) | A replacement for Merchant Center feeds |
| Compatible with AP2 (Agent Payments Protocol) for cryptographic user-consent proof on autonomous purchases | A way to skip being merchant of record |
| Google reference implementation for conversational buying in AI Mode in Search | A "ranking factor" because Google has not framed it that way |

Merchants stay **Merchant of Record** under UCP — they keep customer
relationships and post-purchase ownership.

## How to declare a UCP profile

Publish a profile at `/.well-known/ucp` describing capabilities and versions.
The general shape (consult the live spec for exact field names):

```jsonc
{
  "version": "2026-04-08",
  "capabilities": [
    {
      "id": "dev.ucp.shopping.checkout",
      "version": "2026-04-08",
      "endpoint": "https://api.example.com/ucp/checkout"
    },
    {
      "id": "dev.ucp.shopping.fulfillment",
      "version": "2026-04-08",
      "endpoint": "https://api.example.com/ucp/fulfillment"
    },
    {
      "id": "dev.ucp.shopping.discount",
      "version": "2026-04-08",
      "endpoint": "https://api.example.com/ucp/discount"
    }
  ],
  "merchant": {
    "name": "Example Co.",
    "id": "merchant-center-id-here"
  }
}
```

UCP uses **date-based versioning** (`YYYY-MM-DD`), current release **2026-04-08**
— a literal `"1.0"` does not match any real UCP release and will fail the spec's
version negotiation. Platforms (AI Mode in Search, Gemini, and eventually
others) auto-discover the profile and negotiate.

### Integration paths

- **Native checkout** (default) — full agentic potential; the recommended path.
- **Embedded checkout** (optional, iframe-based) — for specific Google-approved
  merchants with complex/bespoke checkout.

Merchants join a **waitlist** and must be Google-approved before going live.

## Common capabilities to declare

| Capability ID (shape) | Purpose |
|---|---|
| `dev.ucp.shopping.checkout` | Initiate checkout, return totals + payment intent |
| `dev.ucp.shopping.fulfillment` | Quote shipping options and delivery windows |
| `dev.ucp.shopping.discount` | Apply promo codes / loyalty discounts at quote time |
| `dev.ucp.shopping.cart` | Add / remove / update items in agent-managed carts |

Exact identifiers are governed by the live spec. The namespace pattern is
`dev.ucp.<domain>.<verb>`; version values are date-based.

## What claude-seo audits

`/seo ecommerce <url>` should report:

1. **Presence:** does `/.well-known/ucp` resolve to a valid JSON document?
2. **Capability coverage:** which capabilities are declared? Flag missing
   checkout / fulfillment / discount as opportunities, not failures (the
   protocol is early).
3. **Endpoint reachability:** are declared endpoints HTTPS, valid TLS, not
   returning 5xx?
4. **Version coherence:** is the declared `version` a valid **date-based**
   (`YYYY-MM-DD`) UCP release? ucp.dev lists 2026-04-08 as latest; revalidate
   before flagging a version as invalid. Flag a literal `"1.0"` or unrecognized
   version as invalid.
5. **Integration path:** does the profile imply Native (default) or Embedded
   (approved-merchant) checkout?

The audit should **not** score the absence of UCP as a critical failure — frame
it as an opportunity, especially for merchants already on Google Merchant
Center. (UCP itself is live; what's "early" is broad merchant adoption.)

## How UCP interacts with existing surfaces

| Existing surface | Relationship to UCP |
|---|---|
| Google Merchant Center feed | Required upstream — UCP capabilities reference Merchant Center products by ID |
| Google Business Profile | Independent — UCP is product / order; GBP is store / location |
| Product schema (`hasMerchantReturnPolicy`, `shippingDetails`) | Complementary — UCP exposes the same data at the API layer; schema exposes it at the page layer |
| AP2 (Agent Payments Protocol) | Pair. UCP handles discovery + checkout structure; AP2 handles cryptographic proof of user consent. Treat FIDO governance, v0.2, and Mastercard Verifiable Intent details as secondary-source context, not canonical audit guidance until primary sources verify them. |

A merchant that already has clean Merchant Center feeds, complete Product
schema, and a checkout API can declare a UCP profile in a sprint.

## Audit posture

- **Tier 1 (e-commerce sites already on Merchant Center):** recommend
  declaring a UCP profile as a forward-looking opportunity.
- **Tier 2 (DTC sites not on Merchant Center):** do not recommend UCP yet —
  Merchant Center is the prerequisite to most flows.
- **Tier 3 (informational / B2B sites):** ignore UCP — but **do not** blanket-
  exclude hospitality/restaurant sites: UCP is expanding to **Lodging and Food**
  verticals (hotel booking in AI Mode, food delivery via Google Maps).

## Current rollout & landscape (2026)

- **Universal Cart** rollout details beyond AI Mode in Search are reported from
  Google I/O 2026 keynote coverage; not confirmed on a Google-owned source.
  Treat Gemini app, YouTube/Gmail, country expansion, and retailer lists as
  hedged context. Confirmed audit guidance remains Merchant Center eligibility,
  clean product data, and `/.well-known/ucp` readiness for AI Mode in Search.
- **GML 2026 (2026-05-20):** BNPL (Affirm, Klarna) in Google Pay; **Direct
  Offers** + Shopping ads on YouTube enabling instant purchase for UCP-integrated
  brands; AI performance insights + Ask Advisor in Merchant Center.
- **Landscape:** UCP is one of three agentic-checkout protocols — alongside
  **OpenAI's Agentic Commerce Protocol (ACP)** (its consumer Instant Checkout was
  pulled early March 2026) and **Microsoft Copilot** checkout via Shopify
  (2026-01-08). Keep ACP/Copilot as *secondary*-sourced context.

## Last verified

2026-06-21. Re-check when:

- A new dated UCP spec supersedes 2026-04-08.
- AP2 advances past v0.2 / FIDO governance milestones change.
- UCP expands to new verticals or new surfaces (beyond Search, Gemini, YouTube, Gmail).
