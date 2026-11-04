#!/usr/bin/env bash
# Claude SEO: Coupler.io extension installer.
#
# Wires the hosted Coupler.io MCP server (https://mcp.coupler.io/mcp) into
# ~/.claude.json and copies the seo-coupler skill into ~/.claude/skills/.
#
# No API key: the server uses OAuth. After installing, run /mcp in Claude
# Code, select coupler-io and choose Authenticate.
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    # MCP servers live in ~/.claude.json (the file `claude mcp add` writes).
    # NOT ~/.claude/settings.json - `mcpServers` is not a key Claude Code reads
    # there, so entries written to settings.json silently never load.
    MCP_CONFIG_JSON="${HOME}/.claude.json"

    echo "════════════════════════════════════════"
    echo "║   Claude SEO: Coupler.io extension   ║"
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

    mkdir -p "${SKILL_DIR}/seo-coupler"
    cp "${SOURCE_DIR}/skills/seo-coupler/SKILL.md" "${SKILL_DIR}/seo-coupler/SKILL.md"
    echo "✓ Installed skill: ${SKILL_DIR}/seo-coupler/SKILL.md"

    # Merge MCP config into ~/.claude.json atomically.
    mkdir -p "$(dirname "${MCP_CONFIG_JSON}")"
    python3 - "${MCP_CONFIG_JSON}" <<'PY'
import json
import os
import sys
import tempfile

path = sys.argv[1]
data = {}
if os.path.exists(path):
    try:
        with open(path) as fh:
            data = json.load(fh)
    except json.JSONDecodeError:
        sys.exit(f"✗ {path} is not valid JSON. Nothing was changed; fix it and rerun.")
data.setdefault("mcpServers", {})["coupler-io"] = {
    "type": "http",
    "url": "https://mcp.coupler.io/mcp",
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
print(f"✓ Wrote mcpServers.coupler-io to {path}")
PY

    echo
    echo "Done. Next:"
    echo "  1. In Coupler.io, create and run a data flow with Claude as the destination."
    echo "  2. Open a new Claude Code session, run /mcp, select coupler-io and choose Authenticate."
    echo "  3. Run: /seo coupler sources"
    echo
    echo "Full docs: extensions/coupler/docs/COUPLER-SETUP.md"
}

main "$@"
