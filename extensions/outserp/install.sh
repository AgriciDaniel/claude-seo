#!/usr/bin/env bash
# Claude SEO — Outserp (AI answer-engine visibility + content engine) extension installer.
#
# Outserp measures actual ChatGPT / Perplexity answers for buyer-intent
# prompts (head-to-head vs. competitors) and carries a generate → optimize
# → publish production path. Pairs with seo-profound / seo-seranking for
# triangulated AI visibility coverage.
#
# The Outserp MCP server is remote (https://mcp.outserp.ai/mcp) and
# authenticates via OAuth — no credential is required at install time.
# An API key for the REST fallback (https://outserp.ai/api-docs) may be
# provided optionally.
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    SETTINGS_JSON="${HOME}/.claude/settings.json"

    echo "════════════════════════════════════════"
    echo "║   Claude SEO — Outserp extension     ║"
    echo "════════════════════════════════════════"

    command -v python3 >/dev/null 2>&1 || { echo "✗ Python 3 required."; exit 1; }
    if [ ! -d "${SKILL_DIR}/seo" ]; then
        echo "✗ claude-seo base plugin not installed."
        echo "  Install it first: curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash"
        exit 1
    fi

    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    echo "The Outserp MCP server authenticates via OAuth (run /mcp in Claude Code"
    echo "after install). Optionally, provide an API key for the REST fallback."
    read -rsp "Outserp API key (optional, press Enter to skip): " OUTSERP_KEY
    echo

    mkdir -p "${SKILL_DIR}/seo-outserp"
    cp "${SOURCE_DIR}/skills/seo-outserp/SKILL.md" "${SKILL_DIR}/seo-outserp/SKILL.md"
    echo "✓ Installed skill: ${SKILL_DIR}/seo-outserp/SKILL.md"

    # Merge MCP config (and optional API key) into ~/.claude/settings.json
    # atomically. Credentials are passed as argv, never interpolated into
    # the Python source string.
    mkdir -p "$(dirname "${SETTINGS_JSON}")"
    python3 - "${SETTINGS_JSON}" "${OUTSERP_KEY}" <<'PY'
import json, os, sys, tempfile
path, key = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    try:
        with open(path) as fh:
            data = json.load(fh)
    except json.JSONDecodeError:
        data = {}
data.setdefault("mcpServers", {})["outserp"] = {
    "type": "http",
    "url": "https://mcp.outserp.ai/mcp",
}
if key:
    data.setdefault("env", {})["OUTSERP_API_KEY"] = key
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".",
                           prefix=".settings.", suffix=".json")
try:
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
except Exception:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise
print(f"✓ Wrote mcpServers.outserp to {path}")
if key:
    print(f"✓ Wrote env.OUTSERP_API_KEY to {path}")
PY

    echo
    echo "Done. Open a new Claude Code session, run /mcp to complete the OAuth"
    echo "flow for 'outserp', then try:"
    echo "  /seo outserp whoami"
    echo "  /seo outserp audit example.com"
    echo
    echo "Full docs: extensions/outserp/docs/OUTSERP-SETUP.md"
}

main "$@"
