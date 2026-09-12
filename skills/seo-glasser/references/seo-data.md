# SEO data examples

Endpoint input schemas below were inspected on 2026-09-12. Use live `inspect`
for current availability, Price, charge clauses, and supported fields.
The commands demonstrate execution after the user authorizes the cost and scope.
Choose unused output paths for each task.

## SERP evidence for content and competitor research

Provider: [Serper](https://glasser.ai/providers/serper), Endpoint: `/search`.

```bash
glasser inspect -p serper -e /search
```

Write `serp-input.json` with a file-writing tool:

```json
{"q":"coffee subscription","gl":"us","hl":"en","num":10}
```

```bash
glasser run -p serper -e /search -f serp-input.json -o serp-results.json
```

`q` is required; `gl` and `hl` are two-letter lowercase country and language
codes; `num` is 1–20. Change the example's market to the user's target.
Return organic positions, titles, URLs, and snippets that are present.
For `/seo content-brief` or `/seo competitor-pages`, use them to identify search
intent and candidate competitor pages. A snippet is not a full-page audit.
Fetch selected public pages through Claude SEO's existing safe fetch workflow
when the analysis needs page content. SERP results do not measure keyword
volume, domain authority, or AI citation share.

## Keyword demand for a content plan

Provider: [DataForSEO](https://glasser.ai/providers/dataforseo), Endpoint:
`/v3/keywords_data/google_ads/search_volume/live`.

```bash
glasser inspect -p dataforseo -e /v3/keywords_data/google_ads/search_volume/live
```

Write `volume-input.json`:

```json
{"keywords":["coffee subscription","coffee delivery"],"location_code":2840,"language_code":"en"}
```

```bash
glasser run -p dataforseo -e /v3/keywords_data/google_ads/search_volume/live -f volume-input.json -o volume-results.json
```

The wrapper accepts an object, not the direct API's task array. All three fields
are required. It accepts 1–100 keywords. `2840` is the US example; verify the
Provider's location code for another market instead of guessing. Unsupported
search operators such as `site:` are rejected by this Endpoint's schema.

For `/seo plan` or `/seo content-brief`, report the supplied monthly search
volumes, market, and data period. Google Ads competition and CPC are advertising
metrics, not organic ranking difficulty. Missing volume is unknown, not zero.
Do not claim that this Endpoint measures backlinks or AI visibility.

## Local competitor listings

Provider: Serper, Endpoint: `/maps`.

```bash
glasser inspect -p serper -e /maps
```

Write `maps-input.json`:

```json
{"q":"coffee shops","ll":"@1.2897,103.8501,14z","gl":"sg","hl":"en"}
```

```bash
glasser run -p serper -e /maps -f maps-input.json -o maps-results.json
```

`q` is required; `ll` is optional and uses `@latitude,longitude,zoomz` notation.
This example targets Singapore. The schema also permits `gl` and `hl`; it does
not accept `num`. Preserve location context in the output.

For `/seo local`, compare names, addresses, websites, ratings, and review counts
only where returned. One Maps query is a listing snapshot, not a geo-grid rank
study or access to the user's private Google Business Profile. Keep existing
Google and DataForSEO workflows for tasks requiring those capabilities.
