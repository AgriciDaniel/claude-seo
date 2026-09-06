---
name: seo-redirects
description: >
  Audit redirect chains, loops, and status-code correctness (301 vs 302 vs
  307/308) across a site, including canonical drift introduced by redirects.
  Use when user says "redirects", "redirect chain", "redirect loop",
  "301 vs 302", "broken redirects", or "migration redirects".
user-invocable: true
argument-hint: "[url or urls file]"
license: MIT
metadata:
  author: AgriciDaniel
  version: "2.3.0"
  category: seo
---

# Redirect Chain & Status-Code Audit

## Why this is its own skill

`seo-technical` flags redirect chains as a URL-structure check ("no chains,
max 1 hop; 301 for permanent moves"), but that's a one-line heuristic, not an
audit. This skill does the actual chain-walking, loop detection, and
status-code correctness pass, including redirects introduced by domain or
platform migrations, and reconciles the result against canonical tags and the
XML sitemap.

## Process

1. Collect the URL set: single URL, a list of URLs, or a crawl output from
   `seo-technical` / the `firecrawl` extension (map mode) if installed.
2. For each URL, follow the redirect chain via the shared SSRF-safe fetch
   layer (`scripts/fetch_page.py`), capturing every hop's status code,
   `Location` header, and final destination. Do not follow more than 10 hops;
   report anything beyond that as a probable loop.
3. Classify each chain:
   - **Direct (0 hops):** 200 on first request. No issue.
   - **Single-hop (1 hop):** one redirect to a 200. Healthy if status code is
     semantically correct (see below).
   - **Chain (2+ hops):** multiple redirects before reaching a 200. Flag as
     an issue; the fix is always to point the origin directly at the final
     destination, not to shorten the chain by one hop.
   - **Loop:** a URL reappears in its own chain, or the chain exceeds 10 hops
     without resolving. Critical.
   - **Dead end:** chain terminates in 4xx/5xx instead of 200.
4. Check status-code semantics:
   - **301** (permanent): correct for permanent moves, merged pages, domain
     migrations, protocol/host changes (http->https, non-www->www).
   - **302 / 307** (temporary): correct for A/B tests, temporary maintenance,
     geo/device redirects meant to be short-lived. Flag 302s that have been
     stable for 6+ months (per site history/CMS logs, if available) as
     probable mis-classification — should be 301.
   - **308**: like 301 but preserves the HTTP method; correct for API
     endpoints changing location where the client must keep using
     POST/PUT.
   - **Meta-refresh and JS-based redirects**: treat as a redirect for chain
     purposes, but flag separately since Google processes these with lower
     confidence than HTTP redirects.
5. Cross-check against canonicals and the sitemap:
   - A URL that redirects should never appear as a `<loc>` in the sitemap
     (delegate the actual sitemap parse to `seo-sitemap`; this skill only
     flags the overlap once it has one).
   - A redirect's final destination should match that page's self-referencing
     canonical. Mismatches mean the redirect and the canonical disagree about
     which URL is authoritative — report as a "canonical drift" finding, not
     a plain redirect issue, since the fix is different (align canonical, not
     shorten chain).
   - Internal links pointing at a redirecting URL should be updated to the
     final destination directly; flag "linked through a redirect" separately
     from "redirect exists" since the latter alone is not a defect.

## Common Issues

| Issue | Severity | Fix |
|-------|----------|-----|
| Redirect loop | Critical | Break the cycle; verify final destination resolves to 200 |
| Chain of 3+ hops | High | Point origin directly at final destination |
| 302 used for a permanent move | Medium | Change to 301 |
| Redirect destination missing/inconsistent canonical | Medium | Align canonical tag with redirect target |
| Redirected URL still in XML sitemap | Medium | Remove from sitemap; delegate to `seo-sitemap` |
| Internal links pointing through a redirect | Low | Update links to final destination |
| Meta-refresh redirect on an important page | Low | Replace with HTTP-level 301 |
| Mixed-protocol chain (https->http->https) | High | Fix intermediate hop to stay on https |

## Output

### Redirect Health Score: XX/100

### Chains Found
| Origin | Hops | Final Status | Classification |
|--------|------|---------------|-----------------|

### Critical Issues (loops, dead ends)
### High Priority (chains, mixed-protocol hops)
### Medium Priority (status-code mismatches, canonical drift, sitemap overlap)
### Low Priority (internal links through redirects, meta-refresh)

## Error Handling

| Scenario | Action |
|----------|--------|
| URL unreachable at first hop | Report connection error with status code; skip chain-walking for that URL |
| Chain exceeds 10 hops without resolving | Report as a probable loop; do not continue following |
| Redirect target is a relative URL | Resolve against the current hop's origin before continuing |
| No `Location` header on a 3xx response | Report as a malformed redirect; treat as a dead end |
