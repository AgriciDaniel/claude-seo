# Google API Authentication Setup

## Overview

Three credential types serve different APIs:

| Type | Used By | Cost |
|------|---------|------|
| **API Key** | PageSpeed Insights, CrUX, CrUX History, Knowledge Graph | Free |
| **Service Account** | Search Console, Indexing API, GA4 | Free |
| **Both** | Full seo-google skill | Free |

## Step 1: Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project** > **New Project**
3. Name it (e.g., "Claude SEO") and note the project ID
4. Select the project after creation

## Step 2: Enable APIs

Navigate to **APIs & Services > Library** and enable:

| API | Required For |
|-----|-------------|
| Google Search Console API | GSC Search Analytics, URL Inspection, Sitemaps |
| PageSpeed Insights API | PSI Lighthouse lab data |
| Chrome UX Report API | CrUX field data + History |
| Web Search Indexing API | Indexing API v3 |
| Google Analytics Data API | GA4 organic traffic |
| Knowledge Graph Search API | Entity verification (optional) |

## Step 3: Create an API Key

1. **APIs & Services > Credentials > Create Credentials > API key**
2. Click **Restrict key**:
   - Under **API restrictions**, select: PageSpeed Insights API, Chrome UX Report API, Knowledge Graph Search API
3. Copy the generated API key and store it securely

## Step 4: Create a Service Account

1. **IAM & Admin > Service Accounts > Create Service Account**
2. Name: `claude-seo` (or similar)
3. Skip optional permissions steps
4. Click on the created service account > **Keys > Add Key > Create new key > JSON**
5. Download the JSON file and store it securely (e.g., `~/.config/claude-seo/service_account.json`)

The JSON file looks like:
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "<service-account-private-key>",
  "client_email": "<service-account-identifier>",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

The `client_email` field is what you add to GSC and GA4.

## Step 5: Grant Search Console Access

1. Go to [Google Search Console](https://search.google.com/search-console)
2. Select your property
3. **Settings > Users and permissions > Add user**
4. Paste the service account `client_email`
5. Set permission level:
   - **Full** for read-only (Search Analytics, URL Inspection, Sitemaps)
   - **Owner** if you also need the Indexing API

## Step 6: Grant GA4 Access

1. Go to [Google Analytics](https://analytics.google.com)
2. **Admin > Property Access Management > Add users** (the + icon)
3. Paste the service account `client_email`
4. Set role: **Viewer** (minimum for read-only reporting)
5. Note the numeric property ID from **Admin > Property Details** (e.g., `123456789`)

## Step 7: Create Config File

```bash
mkdir -p ~/.config/claude-seo
```

With a per-project profile, create the directory that `google_auth.py --check` prints instead.

Save to `google-api.json` in the config directory that `google_auth.py --check` prints (default `~/.config/claude-seo/`, or `CLAUDE_SEO_PROFILE_DIR` when the project sets it, see Per-Project Profiles):

```json
{
  "service_account_path": "~/.config/claude-seo/service_account.json",
  "api_key": "<GOOGLE_API_KEY>",
  "default_property": "sc-domain:example.com",
  "ga4_property_id": "properties/123456789"
}
```

The service account key can live anywhere; `service_account_path` points to it.

### Property URL Formats

| Format | Example | When to Use |
|--------|---------|-------------|
| Domain property | `sc-domain:example.com` | Covers all URLs on the domain (recommended) |
| URL-prefix property | `https://example.com/` | Covers only that specific prefix |

## Step 8: Verify Setup

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run google_auth.py --check
```

Expected output at Tier 2 (full):
```
Credential Tier: 2 -- Full (API key + Service Account + GA4)

  [OK] PageSpeed Insights v5
  [OK] Chrome UX Report (CrUX) API
  [OK] CrUX History API
  [OK] Google Search Console API
       Service account: configured
  [OK] Google Indexing API v3
  [OK] GA4 Data API v1beta
```

## Per-Project Profiles

Each project can use its own Google account and properties.
Set `CLAUDE_SEO_PROFILE_DIR` in the project's `.claude/settings.local.json`:

```json
{
  "env": {
    "CLAUDE_SEO_PROFILE_DIR": "~/.config/claude-seo/profiles/project-xyz"
  }
}
```

The scripts then read and write `google-api.json`, `oauth-token.json`, `backlinks-api.json` and `matomo.json` only in that directory.
They do not fall back to `~/.config/claude-seo/`, so put the shared `api_key` into each profile or set `GOOGLE_API_KEY`.
The DataForSEO budget stays global, shared by all projects.
The value must be an absolute path or start with `~/`; the filesystem root and the home directory are rejected.
`google_auth.py --check` prints the directory it reads.
Keep the profile in a private directory outside any git repository: it holds API keys and the OAuth token.

The gcloud sign-in (`gcloud auth application-default login`) lives outside the profile.
To use a different gcloud account per project, also set `CLOUDSDK_CONFIG` in the same `env` block.

## Environment Variable Alternatives

Instead of (or in addition to) the config file:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | API key for PSI/CrUX |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON |
| `GA4_PROPERTY_ID` | GA4 property (e.g., `properties/123456789`) |
| `GSC_PROPERTY` | Default GSC property (e.g., `sc-domain:example.com`) |

## OAuth Scopes Used

| Scope | APIs |
|-------|------|
| `https://www.googleapis.com/auth/webmasters.readonly` | GSC (read) |
| `https://www.googleapis.com/auth/webmasters` | GSC (read/write, needed for sitemap submission) |
| `https://www.googleapis.com/auth/indexing` | Indexing API |
| `https://www.googleapis.com/auth/analytics.readonly` | GA4 (read) |

## Troubleshooting

| Error | Fix |
|-------|-----|
| `403 Forbidden` on GSC | Service account email not added to GSC property, or wrong permission level |
| `403 Forbidden` on GA4 | Service account email not added to GA4 property as Viewer |
| `404 Not Found` on GSC | Wrong property URL format. Use `sc-domain:` or include trailing slash for URL-prefix |
| `404 Not Found` on CrUX | Site has insufficient Chrome traffic. Not a credentials issue. |
| `429 Rate Limit` | Wait and retry. See rate-limits-quotas.md for per-API limits |
| `API not enabled` | Enable the specific API in GCP Console > APIs & Services > Library |
