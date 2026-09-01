#!/usr/bin/env bash
# Claude SEO — Creaitor extension uninstaller.
# Removes the seo-creaitor skill and the mcpServers.creaitor-geo entry.
# Nothing else in ~/.claude.json is touched.
set -euo pipefail

SKILL_DIR="${HOME}/.claude/skills/seo-creaitor"
CLAUDE_JSON="${HOME}/.claude.json"

if [ -f "${CLAUDE_JSON}" ]; then
    python3 - "${CLAUDE_JSON}" <<'PY'
import json
import os
import sys
import tempfile

path = sys.argv[1]
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
except json.JSONDecodeError:
    sys.exit(f"✗ {path} is not valid JSON — leaving it untouched.")

servers = data.get("mcpServers")
if not isinstance(servers, dict) or "creaitor-geo" not in servers:
    print(f"  (no mcpServers.creaitor-geo entry to remove in {path})")
    raise SystemExit(0)

servers.pop("creaitor-geo")
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
print(f"✓ Removed mcpServers.creaitor-geo from {path}")
PY
fi

# Remove the skill only after config validation/removal succeeds.
if [ -d "${SKILL_DIR}" ]; then
    rm -rf "${SKILL_DIR}"
    echo "✓ Removed ${SKILL_DIR}"
fi

echo "Done. Revoke the token at https://app.creaitor.ai/user/api-tokens if it is no longer needed."
