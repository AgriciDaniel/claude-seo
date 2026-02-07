---
name: seo-sitemap
description: >
  Analyze existing XML sitemaps or generate new ones with industry templates.
  Validates format, URLs, and structure. Use when user says "sitemap",
  "generate sitemap", "sitemap issues", or "XML sitemap".
---

# Sitemap Analysis & Generation

## Mode 1: Analyze Existing Sitemap

### Validation Checks
- Valid XML format
- URL count <50,000 per file (protocol limit)
- All URLs return HTTP 200
- `<lastmod>` dates are accurate (not all identical)
- No deprecated tags: `<priority>` and `<changefreq>` are ignored by Google
- Sitemap referenced in robots.txt
- Compare crawled pages vs sitemap — flag missing pages

### Quality Signals
- Sitemap index file if >50k URLs
- Split by content type (pages, posts, images, videos)
- No non-canonical URLs in sitemap
- No noindexed URLs in sitemap
- No redirected URLs in sitemap
- HTTPS URLs only (no HTTP)

### Common Issues
| Issue | Severity | Fix |
|-------|----------|-----|
| >50k URLs in single file | Critical | Split with sitemap index |
| Non-200 URLs | High | Remove or fix broken URLs |
| Noindexed URLs included | High | Remove from sitemap |
| Redirected URLs included | Medium | Update to final URLs |
| All identical lastmod | Low | Use actual modification dates |
| Priority/changefreq used | Info | Can remove (ignored by Google) |

## Mode 2: Generate New Sitemap

### Process
1. Ask for business type (or auto-detect from existing site)
2. Load industry template from `assets/` directory
3. Interactive structure planning with user
4. Apply quality gates:
   - ⚠️ WARNING at 30+ location pages (require 60%+ unique content)
   - 🛑 HARD STOP at 50+ location pages (require justification)
5. Generate valid XML output
6. Split at 50k URLs with sitemap index
7. Generate STRUCTURE.md documentation

### Safe Programmatic Pages (OK at scale)
✅ Integration pages (with real setup docs)
✅ Template/tool pages (with downloadable content)
✅ Glossary pages (200+ word definitions)
✅ Product pages (unique specs, reviews)
✅ User profile pages (user-generated content)

### Penalty Risk (avoid at scale)
❌ Location pages with only city name swapped
❌ "Best [tool] for [industry]" without industry-specific value
❌ "[Competitor] alternative" without real comparison data
❌ AI-generated pages without human review and unique value

## Sitemap Format

### Standard Sitemap
```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page</loc>
    <lastmod>2026-02-07</lastmod>
  </url>
</urlset>
```

### Sitemap Index (for >50k URLs)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap-pages.xml</loc>
    <lastmod>2026-02-07</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-posts.xml</loc>
    <lastmod>2026-02-07</lastmod>
  </sitemap>
</sitemapindex>
```

## Output

### For Analysis
- `VALIDATION-REPORT.md` — analysis results
- Issues list with severity
- Recommendations

### For Generation
- `sitemap.xml` (or split files with index)
- `STRUCTURE.md` — site architecture documentation
- URL count and organization summary
