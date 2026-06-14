#!/usr/bin/env bash
set -euo pipefail

# fastCRW Extension Installer for Claude SEO
# Wraps everything in main() to prevent partial execution on network failure
#
# fastCRW is a Firecrawl-compatible web scraper in a single ~8MB Rust binary.
# Self-host (free, AGPL) or managed cloud at https://fastcrw.com. Because it is
# Firecrawl API-compatible, this extension reuses the firecrawl-mcp client and
# simply points its base URL at fastCRW.

main() {
    SKILL_DIR="${HOME}/.claude/skills/seo-crw"
    AGENT_DIR="${HOME}/.claude/agents"
    SEO_SKILL_DIR="${HOME}/.claude/skills/seo"
    SETTINGS_FILE="${HOME}/.claude/settings.json"

    # Default to managed cloud; override CRW_API_URL for a self-hosted engine.
    CRW_API_URL="${CRW_API_URL:-https://fastcrw.com/api}"

    echo "════════════════════════════════════════"
    echo "║   fastCRW Extension - Installer       ║"
    echo "║   For Claude SEO                     ║"
    echo "════════════════════════════════════════"
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

    # Prompt for credentials
    echo ""
    echo "fastCRW API key required (managed cloud)."
    echo "Sign up at: https://fastcrw.com"
    echo "Self-host (free, AGPL): set CRW_API_URL to your engine; key may be left empty."
    echo "Base URL: ${CRW_API_URL}"
    echo ""

    read -rsp "fastCRW API key (CRW_API_KEY): " CRW_API_KEY
    echo ""
    if [ -z "${CRW_API_KEY}" ]; then
        # Self-host engines may run without auth; allow an empty key there.
        if [ "${CRW_API_URL}" = "https://fastcrw.com/api" ]; then
            echo "x API key cannot be empty for the managed cloud."
            echo "  For self-host, set CRW_API_URL to your engine and re-run."
            exit 1
        fi
        echo "  No key supplied; assuming a self-host engine without auth."
    fi

    # Determine script directory (works for both ./install.sh and curl|bash)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Check if running from repo or standalone
    if [ -f "${SCRIPT_DIR}/skills/seo-crw/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}"
    elif [ -f "${SCRIPT_DIR}/extensions/crw/skills/seo-crw/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}/extensions/crw"
    else
        echo "x Cannot find extension source files."
        echo "  Run this script from the claude-seo repo: ./extensions/crw/install.sh"
        exit 1
    fi

    # Install skill
    echo ""
    echo "-> Installing fastCRW skill..."
    mkdir -p "${SKILL_DIR}"
    cp "${SOURCE_DIR}/skills/seo-crw/SKILL.md" "${SKILL_DIR}/SKILL.md"

    # Merge MCP config into settings.json
    echo "-> Configuring MCP server..."

    # Credentials are passed as argv (never interpolated into the source string)
    # and the settings file is written atomically with 0600 permissions.
    python3 - "${SETTINGS_FILE}" "${CRW_API_KEY}" "${CRW_API_URL}" <<'PY'
import json, os, sys, tempfile

settings_path, api_key, api_url = sys.argv[1:4]

if os.path.exists(settings_path):
    try:
        with open(settings_path) as f:
            settings = json.load(f)
    except json.JSONDecodeError:
        settings = {}
else:
    settings = {}

# fastCRW is Firecrawl API-compatible, so we reuse the firecrawl-mcp client and
# point its base URL at fastCRW via FIRECRAWL_API_URL.
env = {
    'FIRECRAWL_API_URL': api_url,
}
if api_key:
    env['FIRECRAWL_API_KEY'] = api_key

settings.setdefault('mcpServers', {})['crw-mcp'] = {
    'command': 'npx',
    'args': ['-y', 'firecrawl-mcp@3.11.0'],
    'env': env,
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
        echo "  Add the crw-mcp server manually to ~/.claude/settings.json"
        echo "  See: extensions/crw/docs/CRW-SETUP.md"
    fi

    # Pre-warm npm package without starting the MCP server binary.
    echo "-> Pre-downloading firecrawl-mcp client..."
    npx --yes --package=firecrawl-mcp@3.11.0 -- node -e "" >/dev/null 2>&1 || true

    echo ""
    echo "v fastCRW extension installed successfully!"
    echo ""
    echo "Usage:"
    echo "  1. Start Claude Code:  claude"
    echo "  2. Run commands:"
    echo "     /seo crw crawl https://example.com"
    echo "     /seo crw map https://example.com"
    echo "     /seo crw scrape https://example.com/page"
    echo "     /seo crw search \"query\" https://example.com"
    echo ""
    echo "Documentation: extensions/crw/README.md"
    echo "To uninstall: ./extensions/crw/uninstall.sh"
}

main "$@"
