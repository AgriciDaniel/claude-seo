#!/usr/bin/env bash
# Claude SEO — Ahrefs extension uninstaller.
set -euo pipefail

SKILL_DIR="${HOME}/.claude/skills/seo-ahrefs"
MCP_CONFIG_JSON="${HOME}/.claude.json"

if [ -d "${SKILL_DIR}" ]; then
    rm -rf "${SKILL_DIR}"
    echo "✓ Removed ${SKILL_DIR}"
fi

if [ -f "${MCP_CONFIG_JSON}" ]; then
    python3 - "${MCP_CONFIG_JSON}" <<'PY'
import json, os, sys, tempfile
path = sys.argv[1]
with open(path) as fh:
    data = json.load(fh)
servers = data.get("mcpServers", {})
if "ahrefs" in servers:
    servers.pop("ahrefs")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", prefix=".settings.", suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    print(f"✓ Removed mcpServers.ahrefs from {path}")
else:
    print(f"  (no mcpServers.ahrefs entry to remove in {path})")
PY
fi

echo "Done."
