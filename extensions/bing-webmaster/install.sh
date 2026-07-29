#!/usr/bin/env bash
# Claude SEO — Bing Webmaster + IndexNow extension installer.
#
# Wires the existing scripts/bing_webmaster.py and indexnow_submit.py into
# a discoverable seo-bing skill and stores the Bing Webmaster Tools API
# key + IndexNow host key in ~/.claude/settings.json.
#
# Microsoft Copilot citations are fed by the Bing index, making this the
# canonical extension for "AI search visibility outside Google".
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    SETTINGS_JSON="${HOME}/.claude/settings.json"

    echo "════════════════════════════════════════"
    echo "║ Claude SEO — Bing Webmaster + IndexNow║"
    echo "════════════════════════════════════════"

    command -v python3 >/dev/null 2>&1 || { echo "✗ Python 3 required."; exit 1; }
    [ ! -d "${SKILL_DIR}/seo" ] && { echo "✗ claude-seo base not installed."; exit 1; }

    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    read -rsp "Bing Webmaster Tools API key (https://www.bing.com/webmasters/api): " BING_KEY
    echo
    read -rp  "IndexNow host key (32+ chars, you'll publish this at /<key>.txt): " INDEXNOW_KEY
    read -rp  "IndexNow keyLocation URL (https://example.com/<key>.txt): " INDEXNOW_LOC

    [ -z "${BING_KEY}" ] && [ -z "${INDEXNOW_KEY}" ] && {
        echo "✗ Provide at least one of: Bing API key, IndexNow key."; exit 1;
    }

    mkdir -p "${SKILL_DIR}/seo-bing"
    cp "${SOURCE_DIR}/skills/seo-bing/SKILL.md" "${SKILL_DIR}/seo-bing/SKILL.md"

    python3 - "${SETTINGS_JSON}" "${BING_KEY}" "${INDEXNOW_KEY}" "${INDEXNOW_LOC}" <<'PY'
import json, os, sys, tempfile
path, bing, idx_key, idx_loc = sys.argv[1:5]
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except json.JSONDecodeError: data = {}
env = data.setdefault("env", {})
if bing: env["BING_WEBMASTER_API_KEY"] = bing
if idx_key: env["INDEXNOW_KEY"] = idx_key
if idx_loc: env["INDEXNOW_KEY_LOCATION"] = idx_loc
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".settings.", suffix=".json")
with os.fdopen(fd, "w") as fh: json.dump(data, fh, indent=2)
os.chmod(tmp, 0o600); os.replace(tmp, path)
print(f"✓ Wrote Bing + IndexNow env to {path}")
PY

    echo
    echo "Done. Verify your IndexNow key is published:"
    echo "  "${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo" run indexnow_submit.py --host example.com \\"
    echo "    --key \$INDEXNOW_KEY --key-location \$INDEXNOW_KEY_LOCATION --verify-only"
}
main "$@"
