# Matomo extension setup

## What this gives you

1. **Matomo Reporting API** for organic traffic, landing pages, devices,
   countries, referrers, and search keywords via
   `claude-seo run matomo_report.py`.
2. **Live credential probe** via `claude-seo run matomo_auth.py --check`
   used by the `/seo matomo` skill and by the audit orchestrator to
   decide whether to spawn the `seo-matomo` agent.
3. A unified `seo-matomo` skill that routes the right command at the
   right script and an `seo-matomo` agent for `/seo audit`.

## Install

```bash
./extensions/matomo/install.sh
.\extensions\matomo\install.ps1
```

You'll be prompted for:

- Matomo instance URL (e.g. `https://analytics.example.com`) — must
  start with `http://` or `https://` and have no userinfo
- Matomo API `token_auth` (32-character hex)
- Default `idSite` (optional, e.g. `1`) — saves having to pass
  `--site-id` on every call

The installer writes `MATOMO_URL`, `MATOMO_API_TOKEN`, and
`MATOMO_SITE_ID` (if set) to `~/.claude/settings.json` under `env`
with `0o600` permissions.

## Token setup checklist

1. Log in to your Matomo instance as a Super User or Admin
2. Go to **Administration -> Personal -> Security -> API Tokens**
3. Click **Create a new token**, give it a meaningful name
   (e.g. "claude-seo") and `view` access on the sites you want to
   analyze
4. Copy the generated `token_auth` (32 hex chars) — Matomo only shows
   it once at creation

## Self-hosted instance notes

`MATOMO_URL` may point at `http://analytics.internal`,
`https://matomo.lan.example.com`, or behind a reverse proxy on a private
network. The script applies a light URL sanity check (scheme + host only)
rather than the strict SSRF protection used for arbitrary web fetches,
because self-hosted Matomo frequently lives outside the public internet.

If your Matomo instance requires a self-signed certificate, install its
CA into the system trust store. The script uses `requests` defaults; it
will fail with `SSLError` on untrusted certificates.

## Verify

```bash
claude-seo run matomo_auth.py --check
claude-seo run matomo_report.py check --json
claude-seo run matomo_report.py organic --json
```

`--check` runs `API.getMatomoVersion` against your instance and reports
the Matomo version string. Any 401/403, network error, or Matomo
`result=error` payload is surfaced as a friendly error with remediation
hints.

## Audit integration

When `matomo_auth.py --check` succeeds, the `/seo audit` orchestrator
spawns the `seo-matomo` agent alongside the existing specialists. The
agent writes `output_dir/findings/matomo.md` with organic traffic trend,
top landing pages, device / country split, and referrer breakdown. It
works alongside `seo-google` — both can run in the same audit when you
have both GA4 and Matomo configured.

## Uninstall

```bash
./extensions/matomo/uninstall.sh
```

PowerShell manual removal:

```powershell
Remove-Item -Recurse -Force "$HOME\.claude\skills\seo-matomo"
Remove-Item -Force "$HOME\.claude\agents\seo-matomo.md"
notepad "$HOME\.claude\settings.json"
```

In `settings.json`, remove `MATOMO_URL`, `MATOMO_API_TOKEN`, and
`MATOMO_SITE_ID` from the top-level `env` object.