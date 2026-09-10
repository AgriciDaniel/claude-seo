#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="${HOME}/.claude/skills/seo-matomo"
AGENT_FILE="${HOME}/.claude/agents/seo-matomo.md"
SETTINGS_JSON="${HOME}/.claude/settings.json"
CONFIG_JSON="${HOME}/.config/claude-seo/matomo.json"
[ -d "${SKILL_DIR}" ] && rm -rf "${SKILL_DIR}" && echo "✓ Removed ${SKILL_DIR}"
[ -f "${AGENT_FILE}" ] && rm -f "${AGENT_FILE}" && echo "✓ Removed ${AGENT_FILE}"
[ -f "${CONFIG_JSON}" ] && rm -f "${CONFIG_JSON}" && echo "✓ Removed ${CONFIG_JSON}"
# Installers before v2.4.0 put the token in settings.json env. Clear it there
# too, so an upgrade-then-uninstall does not leave the old copy behind.
if [ -f "${SETTINGS_JSON}" ]; then
    python3 - "${SETTINGS_JSON}" <<'PY'
import json, os, sys, tempfile
path = sys.argv[1]
try:
    with open(path) as fh:
        data = json.load(fh)
except (OSError, json.JSONDecodeError):
    sys.exit(0)
env = data.get("env", {})
removed = []
for k in ("MATOMO_URL", "MATOMO_API_TOKEN", "MATOMO_TOKEN",
          "MATOMO_SITE_ID", "MATOMO_IDSITE"):
    if k in env:
        env.pop(k)
        removed.append(k)
if removed:
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".settings.", suffix=".json")
    try:
        os.fchmod(fd, 0o600)
    except (AttributeError, OSError):
        pass
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    print("\u2713 Cleared " + ", ".join(removed) + " from " + path)
PY
fi

echo "Note: CLAUDE_SEO_LOCAL_TARGETS, if you set it for a private instance,"
echo "is your own environment setting and was not touched."
