# DataForSEO Extension for Claude SEO

Live SEO data via the [DataForSEO MCP server](https://github.com/dataforseo/mcp-server-typescript). Adds 22 commands across 9 API modules: SERP analysis, keyword research, backlinks, on-page analysis, competitor analysis, content analysis, business listings, AI visibility checking, and LLM mention tracking.

## Prerequisites

- [Claude SEO](https://github.com/AgriciDaniel/claude-seo) installed
- Node.js 20+
- [DataForSEO account](https://app.dataforseo.com/register) with API credentials

## Installation

### Unix/macOS/Linux

```bash
git clone https://github.com/AgriciDaniel/claude-seo.git
cd claude-seo
./extensions/dataforseo/install.sh
```

### Windows

```powershell
git clone https://github.com/AgriciDaniel/claude-seo.git
cd claude-seo
.\extensions\dataforseo\install.ps1
```

The installer will:
1. Prompt for your DataForSEO username and password
2. Install the skill and agent files
3. Configure the MCP server in `~/.claude/settings.json`
4. Pre-download the `dataforseo-mcp-server` npm package

## Commands

### SERP Analysis

| Command | Description |
|---------|-------------|
| `/seo dataforseo serp <keyword>` | Google organic SERP results (also supports Bing/Yahoo via `se` parameter) |
| `/seo dataforseo serp-youtube <keyword>` | YouTube search results |
| `/seo dataforseo youtube <video_id>` | YouTube video deep analysis (info, comments, subtitles) |

### Keyword Research

| Command | Description |
|---------|-------------|
| `/seo dataforseo keywords <seed>` | Keyword ideas, suggestions, and related terms |
| `/seo dataforseo volume <keywords>` | Search volume for keyword list |
| `/seo dataforseo difficulty <keywords>` | Keyword difficulty scores |
| `/seo dataforseo intent <keywords>` | Search intent classification |
| `/seo dataforseo trends <keyword>` | Google Trends data over time |

### Domain & Competitor Analysis

| Command | Description |
|---------|-------------|
| `/seo dataforseo backlinks <domain>` | Full backlink profile with spam scores |
| `/seo dataforseo competitors <domain>` | Competing domains and traffic estimates |
| `/seo dataforseo ranked <domain>` | Keywords a domain ranks for |
| `/seo dataforseo intersection <domains>` | Keyword/backlink overlap (2-20 domains) |
| `/seo dataforseo traffic <domains>` | Bulk traffic estimation |
| `/seo dataforseo subdomains <domain>` | Subdomains with ranking data |
| `/seo dataforseo top-searches <domain>` | Top queries mentioning domain |

### Technical / On-Page

| Command | Description |
|---------|-------------|
| `/seo dataforseo onpage <url>` | On-page analysis (Lighthouse + content parsing) |
| `/seo dataforseo tech <domain>` | Technology stack detection |
| `/seo dataforseo whois <domain>` | WHOIS registration data |

### Content & Business Data

| Command | Description |
|---------|-------------|
| `/seo dataforseo content <keyword/url>` | Content analysis, search, and phrase trends |
| `/seo dataforseo listings <keyword>` | Business listings search |

### AI Visibility / GEO

| Command | Description |
|---------|-------------|
| `/seo dataforseo ai-scrape <query>` | ChatGPT web scraper for GEO visibility |
| `/seo dataforseo ai-mentions <keyword>` | LLM mention tracking across AI platforms |

## API Modules

All 9 DataForSEO modules are enabled:

| Module | Purpose | Example Commands |
|--------|---------|-----------------|
| SERP | Search engine results | serp, serp-youtube, youtube |
| KEYWORDS_DATA | Search volume, trends | volume, trends |
| DATAFORSEO_LABS | Keyword research, competitors | keywords, difficulty, intent, competitors, ranked, subdomains, top-searches |
| BACKLINKS | Link profiles | backlinks, intersection |
| ONPAGE | Page analysis (Lighthouse) | onpage |
| DOMAIN_ANALYTICS | Tech detection, WHOIS | tech, whois |
| BUSINESS_DATA | Business listings | listings |
| CONTENT_ANALYSIS | Content quality, trends | content |
| AI_OPTIMIZATION | ChatGPT scraper, LLM mentions | ai-scrape, ai-mentions |

## API Credits

DataForSEO charges per API call. Credit costs vary by endpoint:

- **SERP** calls: ~0.001-0.003 per request
- **Keyword** research: ~0.0005-0.002 per keyword
- **Backlinks**: ~0.002-0.01 per request
- **On-page** analysis: ~0.01-0.05 per page
- **AI optimization**: ~0.01 per request

New accounts include a free trial balance. See [DataForSEO pricing](https://dataforseo.com/pricing) for current rates.

## Field Filtering

The extension includes a custom `field-config.json` that reduces API response sizes by ~75%, keeping only SEO-relevant fields. This saves tokens and speeds up analysis.

## Integration with Claude SEO

When installed, other Claude SEO skills automatically detect DataForSEO availability and use live data:

- **`/seo audit`**:Uses real SERP, backlink, and on-page data
- **`/seo technical`**:Uses on-page analysis for real technical data
- **`/seo content`**:Uses keyword volume, difficulty, and intent data
- **`/seo geo`**:Uses ChatGPT scraper and LLM mentions for GEO signals
- **`/seo plan`**:Uses competitor and keyword data for strategy

## Troubleshooting

### MCP server not connecting

1. Check credentials: `cat ~/.claude/settings.json | grep DATAFORSEO`
2. Test manually: `npx -y dataforseo-mcp-server`
3. Re-run installer: `./extensions/dataforseo/install.sh`

### API errors

- **401 Unauthorized**: Check username/password in settings.json
- **402 Payment Required**: Add credits at [app.dataforseo.com](https://app.dataforseo.com)
- **429 Rate Limited**: Wait and retry (DataForSEO has per-second limits)

### Module not available

If a specific command fails, check that the module is in `ENABLED_MODULES` in your settings.json. All 9 modules should be listed.

## Uninstall

### Unix/macOS/Linux

```bash
./extensions/dataforseo/uninstall.sh
```

### Windows

```powershell
.\extensions\dataforseo\uninstall.ps1
```

This removes the skill, agent, field config, and MCP server entry from settings.json.

## Links

- [DataForSEO API Docs](https://docs.dataforseo.com/)
- [DataForSEO MCP Server](https://github.com/dataforseo/mcp-server-typescript)
- [Claude SEO](https://github.com/AgriciDaniel/claude-seo)
