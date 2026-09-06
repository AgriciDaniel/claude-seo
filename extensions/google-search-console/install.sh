#!/usr/bin/env bash
set -euo pipefail

# Google Search Console Extension Installer for Claude SEO
# Wraps everything in main() to prevent partial execution on network failure

main() {
    SKILL_DIR="${HOME}/.claude/skills/seo-gsc-extension"
    SEO_SKILL_DIR="${HOME}/.claude/skills/seo"
    SETTINGS_FILE="${HOME}/.claude/settings.json"

    echo "══════════════════════════════════════════════"
    echo "║  Google Search Console Extension - Installer ║"
    echo "║  For Claude SEO                              ║"
    echo "══════════════════════════════════════════════"
    echo ""

    # Check prerequisites
    if [ ! -d "${SEO_SKILL_DIR}" ]; then
        echo "x Claude SEO is not installed."
        echo "  Install it first: curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash"
        exit 1
    fi
    echo "v Claude SEO detected"

    if ! command -v node >/dev/null 2>&1; then
        echo "x Node.js is required but not installed."
        echo "  Install Node.js 20+: https://nodejs.org/"
        exit 1
    fi

    NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "${NODE_VERSION}" -lt 20 ]; then
        echo "x Node.js 20+ required (found v${NODE_VERSION})."
        echo "  Update: https://nodejs.org/"
        exit 1
    fi
    echo "v Node.js v$(node -v | sed 's/v//') detected"

    if ! command -v npx >/dev/null 2>&1; then
        echo "x npx is required but not found (comes with npm)."
        exit 1
    fi
    echo "v npx detected"

    echo ""
    echo "No API key needed. google-searchconsole-mcp ships with built-in"
    echo "OAuth credentials; the first tool call opens a browser window for"
    echo "you to sign in and grant read-only Search Console access."
    echo ""

    # Determine script directory (works for both ./install.sh and curl|bash)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Check if running from repo or standalone
    if [ -f "${SCRIPT_DIR}/skills/seo-gsc-extension/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}"
    elif [ -f "${SCRIPT_DIR}/extensions/google-search-console/skills/seo-gsc-extension/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}/extensions/google-search-console"
    else
        echo "x Cannot find extension source files."
        echo "  Run this script from the claude-seo repo: ./extensions/google-search-console/install.sh"
        exit 1
    fi

    # Install skill
    echo "-> Installing Google Search Console skill..."
    mkdir -p "${SKILL_DIR}"
    cp "${SOURCE_DIR}/skills/seo-gsc-extension/SKILL.md" "${SKILL_DIR}/SKILL.md"

    # Merge MCP config into settings.json
    echo "-> Configuring MCP server..."

    # settings.json is written atomically with 0600 permissions; no secrets
    # are handled here since this server authenticates via OAuth, not a key.
    python3 - "${SETTINGS_FILE}" <<'PY'
import json, os, sys, tempfile

settings_path = sys.argv[1]

if os.path.exists(settings_path):
    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except json.JSONDecodeError:
        settings = {}
else:
    settings = {}

settings.setdefault('mcpServers', {})['google-searchconsole-mcp'] = {
    'command': 'npx',
    'args': ['-y', 'google-searchconsole-mcp@1.0.1'],
}

os.makedirs(os.path.dirname(settings_path) or '.', exist_ok=True)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(settings_path) or '.', prefix='.settings.', suffix='.json')
try:
    with os.fdopen(fd, 'w') as f:
        json.dump(settings, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, settings_path)
except Exception:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise

print('  v MCP server configured in settings.json')
PY
    if [ $? -ne 0 ]; then
        echo "  Warning: Could not auto-configure MCP server."
        echo "  Add the google-searchconsole-mcp server manually to ~/.claude/settings.json"
        echo "  See: extensions/google-search-console/README.md"
    fi

    # Pre-warm npm package without starting the MCP server binary.
    echo "-> Pre-downloading google-searchconsole-mcp..."
    npx --yes --package=google-searchconsole-mcp@1.0.1 -- node -e "" >/dev/null 2>&1 || true

    echo ""
    echo "v Google Search Console extension installed successfully!"
    echo ""
    echo "Usage:"
    echo "  1. Start Claude Code:  claude"
    echo "  2. Run commands (first call opens a browser to sign in):"
    echo "     /seo gsc sites"
    echo "     /seo gsc analytics https://example.com"
    echo "     /seo gsc inspect https://example.com/page"
    echo "     /seo gsc sitemaps https://example.com"
    echo ""
    echo "Documentation: extensions/google-search-console/README.md"
    echo "To uninstall: ./extensions/google-search-console/uninstall.sh"
}

main "$@"
