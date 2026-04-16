# Supplementary Google APIs for SEO

## Knowledge Graph Search API

Verify brand/entity presence in Google's Knowledge Graph.

**Endpoint:** `GET https://kgsearch.googleapis.com/v1/entities:search`

| Param | Description |
|-------|-------------|
| `query` | Search query |
| `ids` | Specific entity IDs (e.g., `/m/0d6lp`) |
| `languages` | Language codes (e.g., `en`) |
| `types` | Schema.org types to filter (e.g., `Organization`, `Person`) |
| `limit` | Max results (1-500) |
| `key` | API key (required) |

**Response:**
```json
{
  "itemListElement": [{
    "result": {
      "@id": "kg:/m/0d6lp",
      "name": "Google",
      "@type": ["Organization", "Corporation"],
      "description": "Technology company",
      "detailedDescription": {
        "articleBody": "Google LLC is an American...",
        "url": "https://en.wikipedia.org/wiki/Google"
      },
      "image": { "url": "..." },
      "url": "https://www.google.com"
    },
    "resultScore": 4892.5
  }]
}
```

**Use for SEO:** Verify if a brand has a Knowledge Panel, check entity disambiguation, find related entities.

**Quota:** 100,000 reads/day. Free. API key only.

---

## Custom Search JSON API

Programmatic Google search results (limited).

**Endpoint:** `GET https://customsearch.googleapis.com/customsearch/v1`

| Param | Description |
|-------|-------------|
| `key` | API key (required) |
| `cx` | Programmable Search Engine ID (required) |
| `q` | Search query |
| `num` | Results per page (1-10) |
| `start` | Start index (max 91) |
| `dateRestrict` | Date restriction (e.g., `d30` for 30 days) |
| `gl` | Country (e.g., `us`) |
| `lr` | Language restriction |
| `searchType` | `image` for image search |
| `siteSearch` | Restrict to a domain |

**Limitations:**
- Max 100 total results per query (10 pages x 10 results)
- **CLOSED to new customers as of 2025.** Existing customers must migrate by January 2027.
- 100 queries/day free, $5 per 1,000 up to 10,000/day

**For SERP data, prefer DataForSEO** (`/seo dataforseo serp`) which has no such limitations.

---

## Web Risk API

Check if URLs are flagged as unsafe by Google Safe Browsing.

**Endpoint:** `GET https://webrisk.googleapis.com/v1/uris:search`

| Param | Description |
|-------|-------------|
| `threatTypes` | `MALWARE`, `SOCIAL_ENGINEERING`, `UNWANTED_SOFTWARE`, `SOCIAL_ENGINEERING_EXTENDED_COVERAGE` |
| `uri` | URL to check |
| `key` | API key (required) |

**Response (clean URL):** Empty threat object.

**Response (flagged URL):**
```json
{
  "threat": {
    "threatTypes": ["MALWARE"],
    "expireTime": "2026-04-01T00:00:00Z"
  }
}
```

**Use for SEO:** Check if pages are flagged (could explain deindexing), verify competitor safety, audit outbound links.

**Quota:** 6,000 QPM. 100,000/month free tier. Requires billing enabled on GCP project.
