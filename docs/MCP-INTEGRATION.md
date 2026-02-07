# MCP Integration

## Overview

Claude SEO can integrate with Model Context Protocol (MCP) servers to access external APIs and enhance analysis capabilities.

## Available Integrations

### PageSpeed Insights API

Use Google's PageSpeed Insights API directly for real Core Web Vitals data.

**Configuration:**

1. Get an API key from [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the PageSpeed Insights API
3. Use in your analysis:

```bash
curl "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=URL&key=YOUR_API_KEY"
```

### Google Search Console

For organic search data, use the Google Search Console API or community MCP servers.

**Community Options:**
- Search for `mcp-server-gsc` or similar community packages
- Configure with your Google Cloud credentials

### Custom MCP Configuration

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "pagespeed": {
      "command": "your-pagespeed-mcp-command",
      "args": ["--api-key", "YOUR_KEY"]
    }
  }
}
```

## API Usage Examples

### PageSpeed Insights

```python
import requests

def get_pagespeed_data(url: str, api_key: str) -> dict:
    """Fetch PageSpeed Insights data for a URL."""
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        "url": url,
        "key": api_key,
        "strategy": "mobile",  # or "desktop"
        "category": ["performance", "accessibility", "best-practices", "seo"]
    }
    response = requests.get(endpoint, params=params)
    return response.json()
```

### Core Web Vitals from CrUX

```python
def get_crux_data(url: str, api_key: str) -> dict:
    """Fetch Chrome UX Report data for a URL."""
    endpoint = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
    payload = {
        "url": url,
        "formFactor": "PHONE"  # or "DESKTOP"
    }
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}
    response = requests.post(endpoint, json=payload, headers=headers, params=params)
    return response.json()
```

## Metrics Available

### From PageSpeed Insights

| Metric | Description |
|--------|-------------|
| LCP | Largest Contentful Paint (lab) |
| INP | Interaction to Next Paint (estimated) |
| CLS | Cumulative Layout Shift (lab) |
| FCP | First Contentful Paint |
| TBT | Total Blocking Time |
| Speed Index | Visual progress speed |

### From CrUX (Field Data)

| Metric | Description |
|--------|-------------|
| LCP | 75th percentile, real users |
| INP | 75th percentile, real users |
| CLS | 75th percentile, real users |
| TTFB | Time to First Byte |

## Best Practices

1. **Rate Limiting**: Respect API quotas (typically 25k requests/day for PageSpeed)
2. **Caching**: Cache results to avoid redundant API calls
3. **Field vs Lab**: Prioritize field data (CrUX) for ranking signals
4. **Error Handling**: Handle API errors gracefully

## Without API Keys

If you don't have API keys, Claude SEO can still:

1. Analyze HTML source for potential issues
2. Identify common performance problems
3. Check for render-blocking resources
4. Evaluate image optimization opportunities
5. Detect JavaScript-heavy implementations

The analysis will note that actual Core Web Vitals measurements require field data from real users.
