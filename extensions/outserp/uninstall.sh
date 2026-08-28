#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="${HOME}/.claude/skills/seo-outserp"
SETTINGS_JSON="${HOME}/.claude/settings.json"
[ -d "${SKILL_DIR}" ] && rm -rf "${SKILL_DIR}" && echo "✓ Removed ${SKILL_DIR}"
if [ -f "${SETTINGS_JSON}" ]; then
  python3 - "${SETTINGS_JSON}" <<'PY'
import json, os, sys, tempfile
path = sys.argv[1]; data = json.load(open(path))
changed = False
if "outserp" in data.get("mcpServers", {}):
    data["mcpServers"].pop("outserp"); changed = True
    print("✓ Removed mcpServers.outserp")
if "OUTSERP_API_KEY" in data.get("env", {}):
    data["env"].pop("OUTSERP_API_KEY"); changed = True
    print("✓ Cleared env.OUTSERP_API_KEY")
if changed:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".settings.", suffix=".json")
    with os.fdopen(fd, "w") as fh: json.dump(data, fh, indent=2)
    os.chmod(tmp, 0o600); os.replace(tmp, path)
PY
fi
