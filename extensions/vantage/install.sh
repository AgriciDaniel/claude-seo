#!/usr/bin/env bash
# Claude SEO — Vantage (AI-citation checker) extension installer.
#
# Vantage checks whether a domain is cited by ChatGPT, Perplexity, or Gemini
# for a given topic. Free tier: 3 checks/month, no card required. Pairs with
# seo-geo (which explains WHY a citation gap exists) as a free first spot-check
# before committing to seo-profound or seo-seranking for continuous tracking.
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    SETTINGS_JSON="${HOME}/.claude/settings.json"

    echo "════════════════════════════════════════"
    echo "║    Claude SEO — Vantage extension    ║"
    echo "════════════════════════════════════════"

    command -v python3 >/dev/null 2>&1 || { echo "✗ Python 3 required."; exit 1; }
    [ ! -d "${SKILL_DIR}/seo" ] && { echo "✗ claude-seo base not installed."; exit 1; }

    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    echo "Get a free API key (3 checks/month, no card) at https://vantagemcp.dev"
    read -rsp "Vantage API key: " VANTAGE_KEY
    echo
    [ -z "${VANTAGE_KEY}" ] && { echo "✗ No key provided."; exit 1; }

    mkdir -p "${SKILL_DIR}/seo-vantage"
    cp "${SOURCE_DIR}/skills/seo-vantage/SKILL.md" "${SKILL_DIR}/seo-vantage/SKILL.md"

    python3 - "${SETTINGS_JSON}" "${VANTAGE_KEY}" <<'PY'
import json, os, sys, tempfile
path, key = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except json.JSONDecodeError: data = {}
data.setdefault("env", {})["VANTAGE_API_KEY"] = key
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".settings.", suffix=".json")
with os.fdopen(fd, "w") as fh: json.dump(data, fh, indent=2)
os.chmod(tmp, 0o600); os.replace(tmp, path)
print(f"✓ Wrote env.VANTAGE_API_KEY to {path}")
PY

    echo "Done. Try: /seo vantage check example.com"
}
main "$@"
