#!/usr/bin/env bash
set -euo pipefail

# Firecrawl Extension Installer for Claude SEO
# Wraps everything in main() to prevent partial execution on network failure

main() {
    SKILL_DIR="${HOME}/.claude/skills/seo-firecrawl"
    AGENT_DIR="${HOME}/.claude/agents"
    SEO_SKILL_DIR="${HOME}/.claude/skills/seo"
    SETTINGS_FILE="${HOME}/.claude/settings.json"

    echo "════════════════════════════════════════"
    echo "║   Firecrawl Extension - Installer    ║"
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
    echo "Firecrawl API key required."
    echo "Sign up at: https://www.firecrawl.dev/app/sign-up"
    echo "Free tier: 500 credits/month"
    echo ""

    read -rsp "Firecrawl API key: " FIRECRAWL_API_KEY
    echo ""
    if [ -z "${FIRECRAWL_API_KEY}" ]; then
        echo "x API key cannot be empty."
        exit 1
    fi

    # Determine script directory (works for both ./install.sh and curl|bash)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Check if running from repo or standalone
    if [ -f "${SCRIPT_DIR}/skills/seo-firecrawl/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}"
    elif [ -f "${SCRIPT_DIR}/extensions/firecrawl/skills/seo-firecrawl/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}/extensions/firecrawl"
    else
        echo "x Cannot find extension source files."
        echo "  Run this script from the claude-seo repo: ./extensions/firecrawl/install.sh"
        exit 1
    fi

    # Install skill
    echo ""
    echo "-> Installing Firecrawl skill..."
    mkdir -p "${SKILL_DIR}"
    cp "${SOURCE_DIR}/skills/seo-firecrawl/SKILL.md" "${SKILL_DIR}/SKILL.md"

    # Merge MCP config into settings.json
    echo "-> Configuring MCP server..."

    python3 -c "
import json, os, sys

settings_path = '${SETTINGS_FILE}'
api_key = '''${FIRECRAWL_API_KEY}'''

# Read existing settings or create new
if os.path.exists(settings_path):
    with open(settings_path, 'r') as f:
        settings = json.load(f)
else:
    settings = {}

# Ensure mcpServers key exists
if 'mcpServers' not in settings:
    settings['mcpServers'] = {}

# Add Firecrawl server config
settings['mcpServers']['firecrawl-mcp'] = {
    'command': 'npx',
    'args': ['-y', 'firecrawl-mcp'],
    'env': {
        'FIRECRAWL_API_KEY': api_key
    }
}

# Write back
os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)

print('  v MCP server configured in settings.json')
" || {
        echo "  Warning: Could not auto-configure MCP server."
        echo "  Add the firecrawl-mcp server manually to ~/.claude/settings.json"
        echo "  See: extensions/firecrawl/docs/FIRECRAWL-SETUP.md"
    }

    # Pre-warm npm package without starting the MCP server binary.
    echo "-> Pre-downloading firecrawl-mcp..."
    npx --yes --package=firecrawl-mcp -- node -e "" >/dev/null 2>&1 || true

    echo ""
    echo "v Firecrawl extension installed successfully!"
    echo ""
    echo "Usage:"
    echo "  1. Start Claude Code:  claude"
    echo "  2. Run commands:"
    echo "     /seo firecrawl crawl https://example.com"
    echo "     /seo firecrawl map https://example.com"
    echo "     /seo firecrawl scrape https://example.com/page"
    echo "     /seo firecrawl search \"query\" https://example.com"
    echo ""
    echo "Documentation: extensions/firecrawl/README.md"
    echo "To uninstall: ./extensions/firecrawl/uninstall.sh"
}

main "$@"
