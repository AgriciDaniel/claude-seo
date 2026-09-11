#!/usr/bin/env bash
# Claude SEO — MentionAgent extension installer.
#
# Wires the MentionAgent remote MCP server (https://mentionagent.ai/mcp,
# Streamable HTTP, bearer key) into ~/.claude.json and copies the
# seo-mentionagent skill into ~/.claude/skills/.
#
# Prereq: a MentionAgent API key. Create one in the dashboard under
# Settings, Agent access (shown once). https://mentionagent.ai/mcp/
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    # MCP servers live in ~/.claude.json (the file `claude mcp add` writes).
    # NOT ~/.claude/settings.json - `mcpServers` is not a key Claude Code reads
    # there, so entries written to settings.json silently never load.
    MCP_CONFIG_JSON="${HOME}/.claude.json"

    echo "════════════════════════════════════════"
    echo "║  Claude SEO — MentionAgent extension ║"
    echo "════════════════════════════════════════"

    command -v python3 >/dev/null 2>&1 || {
        echo "✗ Python 3 required."; exit 1;
    }

    if [ ! -d "${SKILL_DIR}/seo" ]; then
        echo "✗ claude-seo base plugin not installed."
        echo "  Install it first: curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash"
        exit 1
    fi

    # Locate this script's directory so the call works for both
    # `./install.sh` and `curl | bash` invocations.
    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    read -rsp "MentionAgent API key (ma_live_...): " MA_KEY
    echo
    if [ -z "${MA_KEY}" ]; then
        echo "✗ No key provided."; exit 1;
    fi

    mkdir -p "${SKILL_DIR}/seo-mentionagent"
    cp "${SOURCE_DIR}/skills/seo-mentionagent/SKILL.md" "${SKILL_DIR}/seo-mentionagent/SKILL.md"
    echo "✓ Installed skill: ${SKILL_DIR}/seo-mentionagent/SKILL.md"

    # Merge MCP config into ~/.claude.json atomically. Remote server, so no
    # command to run: the client speaks Streamable HTTP to the URL directly.
    mkdir -p "$(dirname "${MCP_CONFIG_JSON}")"
    python3 - "${MCP_CONFIG_JSON}" "${MA_KEY}" <<'PY'
import json
import os
import sys
import tempfile

path, key = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    try:
        with open(path) as fh:
            data = json.load(fh)
    except json.JSONDecodeError:
        data = {}
data.setdefault("mcpServers", {})["mentionagent"] = {
    "type": "http",
    "url": "https://mentionagent.ai/mcp",
    "headers": {"Authorization": f"Bearer {key}"},
}
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
print(f"✓ Wrote mcpServers.mentionagent to {path}")
PY

    echo
    echo "Done. Open a new Claude Code session and run:"
    echo "  /seo mentionagent status"
    echo
    echo "Full docs: extensions/mentionagent/docs/MENTIONAGENT-SETUP.md"
}

main "$@"
