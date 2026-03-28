# DataForSEO Account Setup

Step-by-step guide to getting DataForSEO API credentials for the Claude SEO extension.

## 1. Create Account

1. Go to [app.dataforseo.com/register](https://app.dataforseo.com/register)
2. Sign up with your email address
3. Verify your email

New accounts include a free trial balance for testing.

## 2. Find API Credentials

1. Log in to [app.dataforseo.com](https://app.dataforseo.com)
2. Go to **API Access** in the left sidebar
3. Your credentials are:
   - **Username**: Your registered email address
   - **Password**: Your API password (set during registration)

These are the values you'll enter when running the extension installer.

## 3. Understanding Credits

DataForSEO uses a credit-based system:

- Each API call costs a small number of credits
- Different endpoints have different costs
- Credits are purchased in advance
- Monitor usage at [app.dataforseo.com/dashboard](https://app.dataforseo.com/dashboard)

**Typical costs per call:**

| Endpoint Type | Approximate Cost |
|--------------|-----------------|
| SERP (single query) | $0.001-0.003 |
| Keyword volume (per keyword) | $0.0005-0.002 |
| Backlink summary | $0.002-0.005 |
| Backlink list | $0.005-0.01 |
| On-page crawl (per page) | $0.01-0.05 |
| AI optimization (per call) | $0.01 |

## 4. Manual MCP Configuration

If the installer's auto-configuration fails, add this to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "dataforseo": {
      "command": "npx",
      "args": ["-y", "dataforseo-mcp-server"],
      "env": {
        "DATAFORSEO_USERNAME": "your-email@example.com",
        "DATAFORSEO_PASSWORD": "your-api-password",
        "ENABLED_MODULES": "SERP,KEYWORDS_DATA,ONPAGE,DATAFORSEO_LABS,BACKLINKS,DOMAIN_ANALYTICS,BUSINESS_DATA,CONTENT_ANALYSIS,AI_OPTIMIZATION",
        "FIELD_CONFIG_PATH": "/home/youruser/.claude/skills/seo/dataforseo-field-config.json"
      }
    }
  }
}
```

Replace the username, password, and FIELD_CONFIG_PATH with your actual values.

## 5. Configure Cost Controls

Claude SEO includes a cost estimation and approval system. Initialize it:

```bash
python3 scripts/dataforseo_costs.py init
```

This creates `~/.claude-seo/dataforseo-cost-config.json` with conservative defaults:
- **Approval mode:** `threshold` (asks for approval when estimated cost >= $0.50)
- **Queue:** Standard (cheapest) preferred over live
- **Limits:** Reduced SERP depth, keyword counts, and row limits

To always require approval before any API call:
```bash
python3 scripts/dataforseo_costs.py config --set approval_mode=always
```

To set a custom spending threshold:
```bash
python3 scripts/dataforseo_costs.py config --set threshold_usd=3.00
```

## 6. Verify Installation

After installing, start Claude Code and run:

```
/seo dataforseo serp test query
```

If you see search results, the extension is working correctly.
