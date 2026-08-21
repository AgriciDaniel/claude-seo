# Xquik extension setup

The Xquik extension adds bounded, read-only public-post research to Claude
SEO's LISTEN workflow. It uses the existing managed Python runtime and adds no
package dependency.

## Install

Create an Xquik API key. Then run one installer from the repository root:

```bash
./extensions/xquik/install.sh
```

On Windows PowerShell:

```powershell
.\extensions\xquik\install.ps1
```

The installer:

1. Confirms that Claude SEO, its URL safety layer, and Python 3 are available.
2. prompts for the API key without echoing it.
3. Copies `seo-xquik` and its read-only adapter.
4. Atomically adds `env.X_TWITTER_SCRAPER_API_KEY` to Claude Code settings.
5. Preserves all unrelated settings and applies `0600` permissions where supported.

Invalid settings JSON stops installation. The installer never replaces invalid
JSON with an empty file.

## Verify

Open a new Claude Code session. Run a narrow search:

```text
/seo xquik listen "product name problem"
```

The command returns structured JSON. A successful result includes `status`,
`data`, and an `observed_at` timestamp. It never includes the API key.

## Research limits

- Search reads public posts through `GET /api/v1/x/tweets/search`.
- Radar reads topic signals through `GET /api/v1/radar`.
- Redirects and unsupported endpoints fail closed.
- Every request uses Claude SEO's DNS-pinned URL safety session.
- Each invocation makes one request and returns at most 100 records.
- Response cursors are discarded. The adapter never paginates automatically.
- The adapter never posts or changes an X account.
- Social activity is research evidence, not a search ranking signal.

## Rotate the key

Run the installer again. It replaces only
`env.X_TWITTER_SCRAPER_API_KEY` and keeps unrelated settings.

## Uninstall

```bash
./extensions/xquik/uninstall.sh
```

On Windows PowerShell:

```powershell
.\extensions\xquik\uninstall.ps1
```

The uninstaller removes only `seo-xquik` and its settings key. It leaves the
Claude SEO core and unrelated settings intact.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `missing_api_key` | Run the installer and open a new session |
| `unauthenticated` | Create a valid key, then run the installer again |
| `insufficient_credits` | Review the Xquik account before searching again |
| `rate_limit_exceeded` | Wait before one bounded retry |
| `invalid_response` | Stop the research run and retry later |

Xquik is an independent third-party service. Not affiliated with X Corp.
"Twitter" and "X" are trademarks of X Corp.
