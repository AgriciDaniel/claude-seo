#!/usr/bin/env bash
# Claude SEO — Profound (LLM citation tracker) extension installer.
#
# Profound tracks brand citation rates across major LLMs and exposes
# them as structured time-series. Pairs with seo-seranking (which
# samples mention rates) for triangulated AI visibility data.
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    SETTINGS_JSON="${HOME}/.claude/settings.json"

    echo "════════════════════════════════════════"
    echo "║   Claude SEO — Profound extension    ║"
    echo "════════════════════════════════════════"

    command -v python3 >/dev/null 2>&1 || { echo "✗ Python 3 required."; exit 1; }
    [ ! -d "${SKILL_DIR}/seo" ] && { echo "✗ claude-seo base not installed."; exit 1; }

    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    read -rsp "Profound API key: " PROFOUND_KEY
    echo
    [ -z "${PROFOUND_KEY}" ] && { echo "✗ No key provided."; exit 1; }

    mkdir -p "${SKILL_DIR}/seo-profound"
    cp "${SOURCE_DIR}/skills/seo-profound/SKILL.md" "${SKILL_DIR}/seo-profound/SKILL.md"

    CLAUDE_SEO_SECRET="${PROFOUND_KEY}" python3 - "${SETTINGS_JSON}" <<'PY'
import json, os, sys, tempfile
path, key = sys.argv[1], os.environ["CLAUDE_SEO_SECRET"]
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except json.JSONDecodeError: sys.exit(f"✗ {path} is not valid JSON. Nothing was changed; fix it and rerun.")
data.setdefault("env", {})["PROFOUND_API_KEY"] = key
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".settings.", suffix=".json")
with os.fdopen(fd, "w") as fh: json.dump(data, fh, indent=2)
os.chmod(tmp, 0o600); os.replace(tmp, path)
print(f"✓ Wrote env.PROFOUND_API_KEY to {path}")
PY

    echo "Done. Try: /seo profound citations brandname"
}
main "$@"
