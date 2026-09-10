# Matomo extension setup

## What this gives you

1. **Matomo Reporting API** for organic traffic, landing pages, devices,
   countries, referrers, and search keywords via
   `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_report.py`.
2. **Live credential probe** via `"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_auth.py --check`
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

The installer writes them to `~/.config/claude-seo/matomo.json` with `0600`
permissions, atomically (temp file plus rename, so a crash never leaves a
half-written or truncated credential file). This is the same location and the
same guarded write pattern the `backlinks_auth` module uses for the Moz and
Bing keys. The token is deliberately kept out of `~/.claude/settings.json`,
which is a general-purpose config file that tooling reads, prints, and syncs.

Environment variables still take precedence for any field the file does not
supply, and remain the right choice on a shared machine or in CI:

```bash
export MATOMO_URL="https://analytics.example.com"
export MATOMO_API_TOKEN="...32 hex..."
export MATOMO_SITE_ID="1"
```

## Token setup checklist

1. Log in to your Matomo instance as a Super User or Admin
2. Go to **Administration -> Personal -> Security -> API Tokens**
3. Click **Create a new token**, give it a meaningful name
   (e.g. "claude-seo") and `view` access on the sites you want to
   analyze
4. Copy the generated `token_auth` (32 hex chars) — Matomo only shows
   it once at creation

## Self-hosted instance on a private address

Every request to your Matomo instance goes through claude-seo's shared SSRF
guard, the `url_safety` module: the instance URL is validated, its hostname is
pinned to the validated address for the life of the request, and a redirect
away from the instance is refused rather than followed.

That guard refuses private, loopback, and link-local addresses by default, so
an instance at `http://matomo.internal:8080`, `http://192.168.1.20`, or
`http://localhost:8080` is refused until you say it is yours. Name it in the
`CLAUDE_SEO_LOCAL_TARGETS` allowlist:

```bash
export CLAUDE_SEO_LOCAL_TARGETS="matomo.internal:8080"
```

Entries are `host` or `host:port`, comma-separated, matched exactly. A bare
`host` matches any port on that host; `host:port` matches that port only.
There is no wildcard, no range, and no "allow private" mode. To make it
permanent, put the export in your shell profile or the `env` block of
`~/.claude/settings.json`.

The allowlist is deliberately narrow, and the narrowness is the point:

- It is consulted only for the top-level instance URL. A redirect target or
  any other host stays fail-closed, so a compromised or misconfigured Matomo
  cannot use the allowlist to reach the rest of your network.
- Cloud metadata endpoints (169.254.169.254, `metadata.google.internal`,
  100.100.100.200, and their siblings) are refused even when listed.
- Unset, claude-seo behaves exactly as it does without the feature.

`extensions/matomo/install.sh` and `install.ps1` detect a private instance
address at install time and print the exact line to add.

Full semantics: [SECURITY.md](../../../SECURITY.md).

If your Matomo instance requires a self-signed certificate, install its
CA into the system trust store. The script uses `requests` defaults; it
will fail with `SSLError` on untrusted certificates.

## Verify

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_auth.py --check
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_report.py check --json
"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run matomo_report.py organic --json
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

This removes the skill, the agent, and
`~/.config/claude-seo/matomo.json`, and clears any `MATOMO_*` entries a
pre-v2.4.0 installer had left in `~/.claude/settings.json`.

PowerShell manual removal:

```powershell
Remove-Item -Recurse -Force "$HOME\.claude\skills\seo-matomo"
Remove-Item -Force "$HOME\.claude\agents\seo-matomo.md"
Remove-Item -Force "$HOME\.config\claude-seo\matomo.json"
```

If you installed a pre-v2.4.0 build, also open `~/.claude/settings.json` and
remove `MATOMO_URL`, `MATOMO_API_TOKEN`, and `MATOMO_SITE_ID` from the
top-level `env` object.