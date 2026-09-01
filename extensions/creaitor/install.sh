#!/usr/bin/env bash
# Claude SEO — Creaitor (GEO visibility) extension installer.
#
# Registers the Creaitor remote MCP server as `creaitor-geo` in the Claude
# user config (~/.claude.json) and copies the seo-creaitor skill into
# ~/.claude/skills/.
#
# Prereq: a Creaitor personal access token with the geo:read ability (plus
# geo:write / geo:execute for mutations and runs). Create one at
# https://app.creaitor.ai/user/api-tokens
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    # Remote MCP servers live in the Claude user config, not settings.json.
    CLAUDE_JSON="${HOME}/.claude.json"
    MCP_URL="https://app.creaitor.ai/api/v2/mcp"

    echo "════════════════════════════════════════"
    echo "║   Claude SEO — Creaitor extension    ║"
    echo "════════════════════════════════════════"

    command -v python3 >/dev/null 2>&1 || { echo "✗ Python 3 required."; exit 1; }

    if [ ! -d "${SKILL_DIR}/seo" ]; then
        echo "✗ claude-seo base plugin not installed."
        echo "  Install it first: curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash"
        exit 1
    fi

    # Locate the checked-out extension directory.
    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    echo "→ MCP endpoint: ${MCP_URL}"
    echo "! Quit other Claude Code sessions before continuing; they may rewrite ~/.claude.json on exit."
    read -rsp "Creaitor API token (input hidden): " CREAITOR_TOKEN
    echo
    if [ -z "${CREAITOR_TOKEN}" ]; then
        echo "✗ No token provided."; exit 1;
    fi


    # Merge the MCP entry into ~/.claude.json atomically. The token travels in
    # the environment, never in argv (visible in `ps`) and never interpolated
    # into the Python source below (the heredoc is quoted, so the shell does
    # not expand anything inside it).
    export CREAITOR_TOKEN
    python3 - "${CLAUDE_JSON}" <<'PY'
import json
import os
import sys
import tempfile

path = sys.argv[1]
token = os.environ["CREAITOR_TOKEN"]
url = "https://app.creaitor.ai/api/v2/mcp"

# ~/.claude.json holds the whole Claude Code user config. If it exists but is
# unreadable as a JSON object, abort rather than replace it with our one key.
data = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as fh:
        raw = fh.read().strip()
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            sys.exit(f"✗ {path} is not valid JSON — refusing to overwrite it.")
    if not isinstance(data, dict):
        sys.exit(f"✗ {path} is not a JSON object — refusing to overwrite it.")

servers = data.setdefault("mcpServers", {})
if not isinstance(servers, dict):
    sys.exit(f"✗ mcpServers in {path} is not an object — refusing to overwrite it.")

servers["creaitor-geo"] = {
    "type": "http",
    "url": url,
    "headers": {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
}

fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)),
                           prefix=".claude.", suffix=".json")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
except Exception:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise
print(f"✓ Wrote mcpServers.creaitor-geo -> {url} in {path}")
PY
    unset CREAITOR_TOKEN

    # Stage a complete skill tree, then replace atomically enough for upgrades:
    # a copy failure leaves the previous installed skill untouched.
    mkdir -p "${SKILL_DIR}"
    STAGE_DIR="$(mktemp -d "${SKILL_DIR}/.seo-creaitor.XXXXXX")"
    trap 'rm -rf "${STAGE_DIR}"' EXIT
    cp -R "${SOURCE_DIR}/skills/seo-creaitor/." "${STAGE_DIR}/"
    mkdir -p "${STAGE_DIR}/scripts"
    cp "${SOURCE_DIR}/scripts/resolve_domain.py" "${STAGE_DIR}/scripts/resolve_domain.py"
    rm -rf "${SKILL_DIR}/seo-creaitor"
    mv "${STAGE_DIR}" "${SKILL_DIR}/seo-creaitor"
    trap - EXIT
    echo "✓ Installed skill: ${SKILL_DIR}/seo-creaitor/SKILL.md"

    echo
    echo "Done. Open a new Claude Code session and run:"
    echo "  /seo creaitor overview https://example.com"
    echo
    echo "Full docs: extensions/creaitor/docs/CREAITOR-SETUP.md"
}

main "$@"
