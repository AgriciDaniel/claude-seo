# URL Indexation Status Report

**Property:** {property}
**URLs Inspected:** {total_urls}

## Summary

| Status | Count | Percentage |
|--------|-------|-----------|
| Indexed (PASS) | {pass_count} | {pass_pct}% |
| Not Indexed (FAIL) | {fail_count} | {fail_pct}% |
| Neutral | {neutral_count} | {neutral_pct}% |
| Errors | {error_count} | {error_pct}% |

## Detailed Results

| URL | Verdict | Coverage State | Fetch State | Google Canonical | Last Crawl |
|-----|---------|---------------|-------------|-----------------|------------|
{results_table}

## Canonical Mismatches

URLs where Google selected a different canonical than declared:

| URL | User Canonical | Google Canonical |
|-----|---------------|-----------------|
{canonical_mismatches_table}

## Common Issues

| Issue | Count | Priority | Action |
|-------|-------|----------|--------|
{issues_table}

## Rich Results Detected

| URL | Rich Result Type | Status |
|-----|-----------------|--------|
{rich_results_table}

---
*URL Inspection API: 2,000 inspections/day per site, 600/min.*
*Generated {timestamp} via Google Search Console URL Inspection API.*
