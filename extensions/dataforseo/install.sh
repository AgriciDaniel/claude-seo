#!/usr/bin/env bash
set -euo pipefail

# DataForSEO Extension Installer for Claude SEO
# Wraps everything in main() to prevent partial execution on network failure

main() {
    SKILL_DIR="${HOME}/.claude/skills/seo-dataforseo"
    AGENT_DIR="${HOME}/.claude/agents"
    SEO_SKILL_DIR="${HOME}/.claude/skills/seo"
    SETTINGS_FILE="${HOME}/.claude/settings.json"

    echo "════════════════════════════════════════"
    echo "║   DataForSEO Extension - Installer   ║"
    echo "║   For Claude SEO                     ║"
    echo "════════════════════════════════════════"
    echo ""

    # Check prerequisites
    if [ ! -d "${SEO_SKILL_DIR}" ]; then
        echo "✗ Claude SEO is not installed."
        echo "  Install it first: curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash"
        exit 1
    fi
    echo "✓ Claude SEO detected"

    if ! command -v node >/dev/null 2>&1; then
        echo "✗ Node.js is required but not installed."
        echo "  Install Node.js 20+: https://nodejs.org/"
        exit 1
    fi

    NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
    if [ "${NODE_VERSION}" -lt 20 ]; then
        echo "✗ Node.js 20+ required (found v${NODE_VERSION})."
        echo "  Update: https://nodejs.org/"
        exit 1
    fi
    echo "✓ Node.js v$(node -v | sed 's/v//') detected"

    if ! command -v npx >/dev/null 2>&1; then
        echo "✗ npx is required but not found (comes with npm)."
        exit 1
    fi
    echo "✓ npx detected"

    # Prompt for credentials
    echo ""
    echo "DataForSEO API credentials required."
    echo "Sign up at: https://app.dataforseo.com/register"
    echo ""

    read -rp "DataForSEO username (email): " DFSE_USERNAME
    if [ -z "${DFSE_USERNAME}" ]; then
        echo "✗ Username cannot be empty."
        exit 1
    fi

    read -rsp "DataForSEO password: " DFSE_PASSWORD
    echo ""
    if [ -z "${DFSE_PASSWORD}" ]; then
        echo "✗ Password cannot be empty."
        exit 1
    fi

    # Determine script directory (works for both ./install.sh and curl|bash)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Check if running from repo or standalone
    if [ -f "${SCRIPT_DIR}/skills/seo-dataforseo/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}"
    elif [ -f "${SCRIPT_DIR}/extensions/dataforseo/skills/seo-dataforseo/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}/extensions/dataforseo"
    else
        echo "✗ Cannot find extension source files."
        echo "  Run this script from the claude-seo repo: ./extensions/dataforseo/install.sh"
        exit 1
    fi

    # Install skill
    echo ""
    echo "→ Installing DataForSEO skill..."
    mkdir -p "${SKILL_DIR}"
    cp "${SOURCE_DIR}/skills/seo-dataforseo/SKILL.md" "${SKILL_DIR}/SKILL.md"

    # Install agent
    echo "→ Installing DataForSEO agent..."
    mkdir -p "${AGENT_DIR}"
    cp "${SOURCE_DIR}/agents/seo-dataforseo.md" "${AGENT_DIR}/seo-dataforseo.md"

    # Install field config
    echo "→ Installing field config..."
    cp "${SOURCE_DIR}/field-config.json" "${SEO_SKILL_DIR}/dataforseo-field-config.json"

    # Merge MCP config into settings.json
    echo "→ Configuring MCP server..."
    FIELD_CONFIG_PATH="${SEO_SKILL_DIR}/dataforseo-field-config.json"

    python3 -c "
import json, os, sys

settings_path = '${SETTINGS_FILE}'
username = '''${DFSE_USERNAME}'''
password = '''${DFSE_PASSWORD}'''
field_config = '${FIELD_CONFIG_PATH}'

# Read existing settings or create new
if os.path.exists(settings_path):
    with open(settings_path, 'r') as f:
        settings = json.load(f)
else:
    settings = {}

# Ensure mcpServers key exists
if 'mcpServers' not in settings:
    settings['mcpServers'] = {}

# Add DataForSEO server config
settings['mcpServers']['dataforseo'] = {
    'command': 'npx',
    'args': ['-y', 'dataforseo-mcp-server'],
    'env': {
        'DATAFORSEO_USERNAME': username,
        'DATAFORSEO_PASSWORD': password,
        'ENABLED_MODULES': 'SERP,KEYWORDS_DATA,ONPAGE,DATAFORSEO_LABS,BACKLINKS,DOMAIN_ANALYTICS,BUSINESS_DATA,CONTENT_ANALYSIS,AI_OPTIMIZATION',
        'FIELD_CONFIG_PATH': field_config
    }
}

# Write back
os.makedirs(os.path.dirname(settings_path), exist_ok=True)
with open(settings_path, 'w') as f:
    json.dump(settings, f, indent=2)

print('  ✓ MCP server configured in settings.json')
" || {
        echo "  ⚠  Could not auto-configure MCP server."
        echo "  Add the dataforseo server manually to ~/.claude/settings.json"
        echo "  See: extensions/dataforseo/docs/DATAFORSEO-SETUP.md"
    }

    # Pre-warm npm package without starting the MCP server binary.
    echo "→ Pre-downloading dataforseo-mcp-server..."
    npx --yes --package=dataforseo-mcp-server -- node -e "" >/dev/null 2>&1 || true

    echo ""
    echo "✓ DataForSEO extension installed successfully!"
    echo ""
    echo "Usage:"
    echo "  1. Start Claude Code:  claude"
    echo "  2. Run commands:"
    echo "     /seo dataforseo serp best coffee shops"
    echo "     /seo dataforseo keywords seo tools"
    echo "     /seo dataforseo backlinks example.com"
    echo "     /seo dataforseo ai-mentions your brand"
    echo ""
    echo "All 22 commands: see extensions/dataforseo/README.md"
    echo "To uninstall: ./extensions/dataforseo/uninstall.sh"
}

main "$@"
