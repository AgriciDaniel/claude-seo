#!/usr/bin/env bash
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills/seo-scm"
    SEO_SKILL_DIR="${HOME}/.claude/skills/seo"
    MCP_CONFIG_FILE="${HOME}/.claude.json"
    SCM_MCP_PACKAGE="seo-content-machine-mcp@1.1.1"

    echo "════════════════════════════════════════"
    echo "║   SEO Content Machine - Installer    ║"
    echo "║   For Claude SEO                     ║"
    echo "════════════════════════════════════════"
    echo ""

    if [ ! -d "${SEO_SKILL_DIR}" ]; then
        echo "x Claude SEO is not installed."
        echo "  Install it first: curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash"
        exit 1
    fi
    echo "v Claude SEO detected"

    if ! command -v node >/dev/null 2>&1; then
        echo "x Node.js is required but not installed."
        echo "  Install Node.js 18+: https://nodejs.org/"
        exit 1
    fi

    NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "${NODE_VERSION}" -lt 18 ]; then
        echo "x Node.js 18+ required (found v${NODE_VERSION})."
        echo "  Update: https://nodejs.org/"
        exit 1
    fi
    echo "v Node.js v$(node -v | sed 's/v//') detected"

    if ! command -v npx >/dev/null 2>&1; then
        echo "x npx is required but not found (comes with npm)."
        exit 1
    fi
    echo "v npx detected"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [ -f "${SCRIPT_DIR}/skills/seo-scm/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}"
    elif [ -f "${SCRIPT_DIR}/extensions/scm/skills/seo-scm/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}/extensions/scm"
    else
        echo "x Cannot find extension source files."
        echo "  Run this script from the claude-seo repo: ./extensions/scm/install.sh"
        exit 1
    fi

    echo ""
    echo "-> Installing SCM skill..."
    mkdir -p "${SKILL_DIR}"
    cp "${SOURCE_DIR}/skills/seo-scm/SKILL.md" "${SKILL_DIR}/SKILL.md"

    echo "-> Configuring MCP server (no API key needed, it talks to the SCM app on this machine)..."
    python3 - "${MCP_CONFIG_FILE}" "${SCM_MCP_PACKAGE}" <<'PY'
import json, os, sys, tempfile

settings_path, package = sys.argv[1], sys.argv[2]

if os.path.exists(settings_path):
    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except json.JSONDecodeError:
        sys.exit(f"x {settings_path} is not valid JSON. Nothing was changed; fix it and rerun.")
else:
    settings = {}

servers = settings.setdefault('mcpServers', {})
if 'scm' in servers:
    print('  v An "scm" MCP server is already configured; kept as it is')
    sys.exit(0)

servers['scm'] = {
    'command': 'npx',
    'args': ['-y', package],
}

os.makedirs(os.path.dirname(settings_path) or '.', exist_ok=True)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(settings_path) or '.', prefix='.settings.', suffix='.json')
try:
    with os.fdopen(fd, 'w') as f:
        json.dump(settings, f, indent=2)
    if os.path.exists(settings_path):
        os.chmod(tmp, os.stat(settings_path).st_mode & 0o777)
    os.replace(tmp, settings_path)
except Exception:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise

print('  v MCP server configured in ~/.claude.json')
PY
    if [ $? -ne 0 ]; then
        echo "  Warning: Could not auto-configure MCP server."
        echo "  Add it manually: claude mcp add scm -- npx -y ${SCM_MCP_PACKAGE}"
        echo "  See: extensions/scm/docs/SCM-SETUP.md"
    fi

    echo "-> Pre-downloading ${SCM_MCP_PACKAGE}..."
    npx --yes --package="${SCM_MCP_PACKAGE}" -- node -e "" >/dev/null 2>&1 || true

    echo ""
    echo "v SEO Content Machine extension installed!"
    echo ""
    echo "SEO Content Machine must be running on this machine."
    echo "No SCM yet? 14-day free trial, no card needed:"
    echo "  https://seocontentmachine.com/members/signup/trial?utm_source=claude-seo&utm_medium=extension&utm_campaign=claude-seo&utm_content=installer"
    echo ""
    echo "Usage:"
    echo "  1. Open SEO Content Machine, then start Claude Code:  claude"
    echo "  2. Run commands:"
    echo "     /seo cluster plan \"<seed keyword>\""
    echo "     /seo scm execute"
    echo "     /seo scm status"
    echo ""
    echo "Documentation: extensions/scm/README.md"
    echo "To uninstall: ./extensions/scm/uninstall.sh"
}

main "$@"
