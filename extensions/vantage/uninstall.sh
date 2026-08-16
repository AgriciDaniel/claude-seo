#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="${HOME}/.claude/skills/seo-vantage"
SETTINGS_JSON="${HOME}/.claude/settings.json"
[ -d "${SKILL_DIR}" ] && rm -rf "${SKILL_DIR}" && echo "✓ Removed ${SKILL_DIR}"
if [ -f "${SETTINGS_JSON}" ]; then
  python3 - "${SETTINGS_JSON}" <<'PY'
import json, os, sys, tempfile
path = sys.argv[1]; data = json.load(open(path))
if "VANTAGE_API_KEY" in data.get("env", {}):
    data["env"].pop("VANTAGE_API_KEY")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".settings.", suffix=".json")
    with os.fdopen(fd, "w") as fh: json.dump(data, fh, indent=2)
    os.chmod(tmp, 0o600); os.replace(tmp, path)
    print("✓ Cleared env.VANTAGE_API_KEY")
PY
fi
