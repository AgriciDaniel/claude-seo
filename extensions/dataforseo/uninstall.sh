#!/usr/bin/env bash
set -euo pipefail

main() {
    echo "→ Uninstalling DataForSEO extension..."

    # Remove skill
    rm -rf "${HOME}/.claude/skills/seo-dataforseo"

    # Remove agent
    rm -f "${HOME}/.claude/agents/seo-dataforseo.md"

    # Remove field config
    rm -f "${HOME}/.claude/skills/seo/dataforseo-field-config.json"

    # Remove MCP server entry from ~/.claude.json
    MCP_CONFIG_FILE="${HOME}/.claude.json"
    if [ -f "${MCP_CONFIG_FILE}" ]; then
        python3 - "${MCP_CONFIG_FILE}" <<'PY' 2>/dev/null || echo "  ⚠  Could not auto-remove MCP config. Remove 'dataforseo' from ~/.claude.json manually."
import json, os, sys
settings_path = sys.argv[1]
with open(settings_path, 'r') as f:
    settings = json.load(f)
if 'mcpServers' in settings and 'dataforseo' in settings['mcpServers']:
    del settings['mcpServers']['dataforseo']
    if not settings['mcpServers']:
        del settings['mcpServers']
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    print('  ✓ Removed dataforseo from ~/.claude.json')
else:
    print('  ✓ No dataforseo entry in ~/.claude.json')
PY
    fi

    echo "✓ DataForSEO extension uninstalled."
}

main "$@"
