#!/usr/bin/env bash
# Claude SEO: Bing Webmaster + IndexNow extension installer.
#
# Stores the Bing Webmaster Tools API key + IndexNow host key in
# ~/.claude/settings.json for the seo-bing skill, which wraps the existing
# scripts/bing_webmaster.py and indexnow_submit.py.
#
# Plugin installs already ship the skill (skills/seo-bing), so only the keys
# are stored. Manual installs (~/.claude/skills/seo) also get the skill copied
# with its launcher path rewritten, because they have no ${CLAUDE_PLUGIN_ROOT}.
#
# Microsoft Copilot citations are fed by the Bing index, making this the
# canonical extension for "AI search visibility outside Google".
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    SETTINGS_JSON="${HOME}/.claude/settings.json"

    echo "════════════════════════════════════════"
    echo "║ Claude SEO: Bing Webmaster + IndexNow ║"
    echo "════════════════════════════════════════"

    command -v python3 >/dev/null 2>&1 || { echo "✗ Python 3 required."; exit 1; }

    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    # Support both traditional (curl|bash → ~/.claude/skills/seo) and marketplace
    # (plugin install → ${CLAUDE_PLUGIN_ROOT}, or ~/.claude/plugins/cache/.../skills/seo)
    # installations. A plugin install never populates ~/.claude/skills/seo, so that
    # check alone would always abort; check the plugin locations too before failing.
    INSTALL_MODE=""
    PLUGIN_ROOT=""
    if [ -d "${SKILL_DIR}/seo" ]; then
        INSTALL_MODE="manual"
    elif [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -d "${CLAUDE_PLUGIN_ROOT}/skills/seo" ]; then
        INSTALL_MODE="plugin"; PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
    else
        _OWN_ROOT="$(cd "${SOURCE_DIR}/../.." >/dev/null 2>&1 && pwd || true)"
        if [ -n "${_OWN_ROOT}" ] && [ -d "${_OWN_ROOT}/skills/seo" ] && [ -f "${_OWN_ROOT}/.claude-plugin/plugin.json" ]; then
            INSTALL_MODE="plugin"; PLUGIN_ROOT="${_OWN_ROOT}"
        else
            _GLOB_MATCH=$(ls -d "${HOME}/.claude/plugins/cache/"*/claude-seo/*/skills/seo 2>/dev/null | tail -n1 || true)
            if [ -n "${_GLOB_MATCH}" ] && [ -d "${_GLOB_MATCH}" ]; then
                INSTALL_MODE="plugin"; PLUGIN_ROOT="$(cd "${_GLOB_MATCH}/../.." >/dev/null 2>&1 && pwd)"
            fi
        fi
    fi
    if [ -z "${INSTALL_MODE}" ]; then
        echo "✗ claude-seo base not installed (no plugin install and no ~/.claude/skills/seo)."
        exit 1
    fi
    if [ "${INSTALL_MODE}" = "plugin" ]; then
        echo "✓ claude-seo plugin detected: storing keys only."
        if [ ! -f "${PLUGIN_ROOT}/skills/seo-bing/SKILL.md" ]; then
            echo "! This plugin version does not ship the seo-bing skill yet."
            echo "  Update the claude-seo plugin, then /seo bing will load."
        fi
    fi

    read -rsp "Bing Webmaster Tools API key (https://www.bing.com/webmasters/api): " BING_KEY
    echo
    read -rp  "IndexNow host key (32+ chars, you'll publish this at /<key>.txt): " INDEXNOW_KEY
    read -rp  "IndexNow keyLocation URL (https://example.com/<key>.txt): " INDEXNOW_LOC

    [ -z "${BING_KEY}" ] && [ -z "${INDEXNOW_KEY}" ] && {
        echo "✗ Provide at least one of: Bing API key, IndexNow key."; exit 1;
    }

    if [ "${INSTALL_MODE}" = "manual" ]; then
        # Same rewrite the main installer applies: a copied personal skill has
        # no ${CLAUDE_PLUGIN_ROOT}, so the launcher token becomes the absolute
        # manual-install path. In a basic regular expression "$" is literal
        # unless it ends the expression, so the token needs no escaping.
        mkdir -p "${SKILL_DIR}/seo-bing"
        sed -e 's#"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo"#"$HOME/.claude/skills/seo/scripts/claude-seo"#g' \
            "${SOURCE_DIR}/skills/seo-bing/SKILL.md" > "${SKILL_DIR}/seo-bing/SKILL.md"
        echo "✓ Installed skill: ${SKILL_DIR}/seo-bing/SKILL.md"
    fi

    mkdir -p "$(dirname "${SETTINGS_JSON}")"

    CLAUDE_SEO_SECRET="${BING_KEY}" CLAUDE_SEO_INDEXNOW_KEY="${INDEXNOW_KEY}" python3 - "${SETTINGS_JSON}" "${INDEXNOW_LOC}" <<'PY'
import json, os, sys, tempfile
path = sys.argv[1]
idx_loc = sys.argv[2] if len(sys.argv) > 2 else ""
bing = os.environ.get("CLAUDE_SEO_SECRET", "")
idx_key = os.environ.get("CLAUDE_SEO_INDEXNOW_KEY", "")
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except json.JSONDecodeError: sys.exit(f"✗ {path} is not valid JSON. Nothing was changed; fix it and rerun.")
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
    echo "Done. Restart Claude Code so the new env values load, then verify that"
    echo "your IndexNow key is published:"
    echo "  /seo bing verify-indexnow --host example.com"
}
main "$@"
