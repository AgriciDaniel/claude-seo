---
name: seo-ahrefs
description: Ahrefs API analyst (extension). Reads referring domains, backlinks, organic keywords, and content explorer data via the tested @ahrefs/mcp@0.0.11 server. Pairs with seo-backlinks for multi-source confidence weighting.
metadata:
  version: "2.2.3"
compatibility: "Tested with @ahrefs/mcp@0.0.11 (installed by extensions/ahrefs/install.sh)."
---

# seo-ahrefs

Live Ahrefs data via the tested `@ahrefs/mcp@0.0.11` server.
Package check (2026-07-10): verify the current Ahrefs MCP package source before changing this tested version.

## Prerequisites

- Run `extensions/ahrefs/install.sh` (Linux/macOS) or `install.ps1` (Windows) before using this skill.
- An Ahrefs API token (https://ahrefs.com/api).
- Node 18+ on `$PATH` for the MCP server.

Before calling any Ahrefs tool, verify the MCP is connected by checking
that any Ahrefs MCP tool is available in this session. If tools are
not available, tell the user the extension is not installed and
provide the install command above.

## Routing

| Command | Action |
|---|---|
| `/seo ahrefs metrics <url>` | Domain / URL rating, referring domain count, organic traffic estimate |
| `/seo ahrefs backlinks <url>` | Top referring domains, anchor distribution, follow/nofollow ratio |
| `/seo ahrefs organic <url>` | Organic keywords, ranking distribution, traffic by country |
| `/seo ahrefs content <topic>` | Content Explorer top results, social shares, referring domains |

## Output conventions

- Cite the data source on every metric: "Ahrefs (live, confidence 1.00)".
- When Ahrefs and Moz disagree on the same metric, trust Ahrefs and note the discrepancy in the report.
- Toxic link assessment: combine Ahrefs backlink quality signals with the existing seo-backlinks Common Crawl + verify crawler signals.

## Cross-skill delegation

- For multi-source confidence weighting across Moz + Bing + Common Crawl + Ahrefs, hand back to `seo-backlinks`.
- For SERP-feature analysis where Ahrefs and DataForSEO overlap, prefer DataForSEO for live SERP data.

## Cost guardrails

Ahrefs API usage is metered per unit. Before running a batch (>= 50 URLs):

1. Estimate cost with `python3 scripts/dataforseo_costs.py` (the cost-tracker module is generic and supports Ahrefs unit accounting).
2. Surface the estimate to the orchestrator.
3. Log actual cost after each call.

This is the same workflow the seo-dataforseo skill uses.
