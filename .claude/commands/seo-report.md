---
description: Run a full SEO audit + competitor analysis for any URL and save a named PDF report. Usage: /seo-report https://propertywebsite.com
---

Run a complete SEO report for: $ARGUMENTS

Follow these steps in order:

## Step 1 — Fetch property name
Fetch the URL $ARGUMENTS and extract the site's title tag or H1. This is the **property name** that will be used to name the PDF and throughout the report. If the title contains separators like | or - or :, use only the first meaningful part (e.g. "Acme Hotel" from "Acme Hotel | Official Site").

## Step 2 — Run full SEO audit
Run the complete `/seo-audit` skill on $ARGUMENTS including:
- Crawlability & Indexation (robots.txt, sitemap, canonical, noindex)
- Technical Foundations (HTTPS, redirects, load time, viewport)
- On-Page Optimization (title, meta, H1, images, links)
- Content Quality & E-E-A-T (word count, schema, OG tags)
- Authority & Trust (privacy, contact, HTTPS)
- SEO Health Index score (0-100) with category breakdown

## Step 3 — Run competitor analysis
Run the complete `seo-competitor` skill on $ARGUMENTS:
- Identify top 3-5 competitors
- Audit each competitor using the SEO Health Index
- Produce the full comparison table
- Gap analysis and competitive action plan

## Step 4 — Generate PDF (automatic — do NOT ask the user)

Immediately after Steps 1–3 complete, generate the PDF without any confirmation prompt.

1. Compile the full report content (all findings from Steps 1–3) into a single markdown string and write it to a temporary file, e.g. `%TEMP%\seo_report_tmp.md`.

2. Run the Milestone-branded PDF generator via Bash:

```bash
cd "C:\Users\harrs\OneDrive - George Brown College\Desktop\PRODUCT MANAGEMENT\AI SEO COPILOT\AI SEO COPILOT CODE\backend" && venv\Scripts\python.exe -c "
import sys, json
sys.path.insert(0, '.')
from app.services.pdf_generator import generate_audit_pdf

# Minimal results dict — pass whatever scores and data are available
results = {
    'scores': {
        'ai_visibility_score': <AI_SCORE>,
        'schema_score': <SCHEMA_SCORE>,
        'content_score': <CONTENT_SCORE>,
        'technical_score': <TECH_SCORE>,
    },
    'issues': <ISSUES_LIST>,
    'recommendations': <RECS_LIST>,
    'query_results': [],
    'schema_analysis': {},
    'content_analysis': {},
}
path = generate_audit_pdf('<PROPERTY_NAME>', results, 'seo-report')
print(path)
"
```

Replace `<PROPERTY_NAME>`, `<AI_SCORE>`, `<SCHEMA_SCORE>`, `<CONTENT_SCORE>`, `<TECH_SCORE>`, `<ISSUES_LIST>`, and `<RECS_LIST>` with the actual values collected during Steps 1–3.

The script will:
- Create `C:\Users\harrs\reportsss\<PropertyName>\` if it does not already exist (never duplicates an existing folder)
- Save the PDF as `<PropertyName>_seo-report.pdf` inside that folder
- Brand it with Milestone Inc. identity (blue header, company name, contact details, cover page)
- Set PDF metadata author/creator/producer to "Milestone Inc." — no tool attribution

## Step 5 — Confirm completion
Tell the user:
- The property name you found
- Their SEO Health Score and band (e.g. 74/100 — Fair)
- How many issues were found (critical / high / medium / low)
- The exact PDF file path (output from Step 4)
- Top 3 priority fixes
