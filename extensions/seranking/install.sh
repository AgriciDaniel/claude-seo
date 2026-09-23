#!/usr/bin/env bash
# Claude SEO — SE Ranking extension installer.
#
# SE Ranking's strength for v2: AI Share-of-Voice tracking across
# ChatGPT, Gemini, Perplexity, AI Overviews, and AI Mode. The gap
# analysis ranks this as the highest-impact new extension because no
# other vendor offers a single MCP/API surface for all 5 AI platforms.
#
# Prereq: SE Ranking API key. Get one at https://seranking.com/api
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    SETTINGS_JSON="${HOME}/.claude/settings.json"

    echo "════════════════════════════════════════"
    echo "║ Claude SEO — SE Ranking extension    ║"
    echo "════════════════════════════════════════"

    command -v python3 >/dev/null 2>&1 || { echo "✗ Python 3 required."; exit 1; }

    if [ ! -d "${SKILL_DIR}/seo" ]; then
        echo "✗ claude-seo base plugin not installed."
        exit 1
    fi

    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    read -rsp "SE Ranking API key: " SR_KEY
    echo
    [ -z "${SR_KEY}" ] && { echo "✗ No key provided."; exit 1; }

    mkdir -p "${SKILL_DIR}/seo-seranking"
    cp "${SOURCE_DIR}/skills/seo-seranking/SKILL.md" "${SKILL_DIR}/seo-seranking/SKILL.md"
    echo "✓ Installed skill: ${SKILL_DIR}/seo-seranking/SKILL.md"

    mkdir -p "$(dirname "${SETTINGS_JSON}")"
    CLAUDE_SEO_SECRET="${SR_KEY}" python3 - "${SETTINGS_JSON}" <<'PY'
import json, os, sys, tempfile
path, key = sys.argv[1], os.environ["CLAUDE_SEO_SECRET"]
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except json.JSONDecodeError: sys.exit(f"✗ {path} is not valid JSON. Nothing was changed; fix it and rerun.")
data.setdefault("env", {})["SERANKING_API_KEY"] = key
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".settings.", suffix=".json")
with os.fdopen(fd, "w") as fh:
    json.dump(data, fh, indent=2)
os.chmod(tmp, 0o600)
os.replace(tmp, path)
print(f"✓ Wrote env.SERANKING_API_KEY to {path}")
PY

    echo
    echo "Done. Try: /seo seranking ai-visibility brandname"
    echo "Full docs: extensions/seranking/docs/SERANKING-SETUP.md"
}

main "$@"
