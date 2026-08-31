#!/usr/bin/env bash
# Claude SEO — Matomo extension installer.
#
# Self-hosted (or Matomo Cloud) Reporting API. Provides organic traffic,
# landing pages, device / country breakdowns, and referrer analysis as a
# GA4 alternative or complement.
#
# Prereq: a Matomo instance URL, an API token_auth, and (optionally) a
# default site ID.
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    AGENTS_DIR="${HOME}/.claude/agents"
    SETTINGS_JSON="${HOME}/.claude/settings.json"

    echo "════════════════════════════════════════"
    echo "║ Claude SEO — Matomo extension       ║"
    echo "════════════════════════════════════════"

    command -v python3 >/dev/null 2>&1 || { echo "✗ Python 3 required."; exit 1; }
    [ ! -d "${SKILL_DIR}/seo" ] && { echo "✗ claude-seo base not installed."; exit 1; }

    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    read -rp "Matomo instance URL (e.g. https://analytics.example.com): " MATOMO_URL
    [ -z "${MATOMO_URL}" ] && { echo "✗ Matomo URL required."; exit 1; }

    read -rsp "Matomo API token_auth (32-char hex): " MATOMO_TOKEN
    echo
    [ -z "${MATOMO_TOKEN}" ] && { echo "✗ Matomo token_auth required."; exit 1; }

    read -rp "Default site ID (idSite, optional, e.g. 1): " MATOMO_SITE_ID
    echo

    mkdir -p "${SKILL_DIR}/seo-matomo"
    cp "${SOURCE_DIR}/skills/seo-matomo/SKILL.md" "${SKILL_DIR}/seo-matomo/SKILL.md"
    echo "✓ Installed skill: ${SKILL_DIR}/seo-matomo/SKILL.md"

    mkdir -p "${AGENTS_DIR}"
    cp "${SOURCE_DIR}/agents/seo-matomo.md" "${AGENTS_DIR}/seo-matomo.md"
    echo "✓ Installed agent: ${AGENTS_DIR}/seo-matomo.md"

    python3 - "${SETTINGS_JSON}" "${MATOMO_URL}" "${MATOMO_TOKEN}" "${MATOMO_SITE_ID}" <<'PY'
import json, os, sys, tempfile
path, url, token, site = sys.argv[1:5]
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except json.JSONDecodeError: data = {}
env = data.setdefault("env", {})
env["MATOMO_URL"] = url
env["MATOMO_API_TOKEN"] = token
if site:
    env["MATOMO_SITE_ID"] = site
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".settings.", suffix=".json")
with os.fdopen(fd, "w") as fh:
    json.dump(data, fh, indent=2)
os.chmod(tmp, 0o600)
os.replace(tmp, path)
print(f"✓ Wrote MATOMO_* env to {path}")
PY

    echo
    echo "Done. Verify with:"
    echo "  claude-seo run matomo_auth.py --check"
    echo "  claude-seo run matomo_report.py check --json"
    echo "Full docs: extensions/matomo/docs/MATOMO-SETUP.md"
}
main "$@"