#!/usr/bin/env bash
set -euo pipefail

echo "Removing Firecrawl extension..."

# Remove skill directory
rm -rf "${HOME}/.claude/skills/seo-firecrawl"
echo "v Removed skill files"

# Remove MCP entry from ~/.claude.json
MCP_CONFIG_FILE="${HOME}/.claude.json"
if [ -f "${MCP_CONFIG_FILE}" ]; then
    python3 - "${MCP_CONFIG_FILE}" <<'PY' || echo "  Warning: Could not update ~/.claude.json automatically."
import json, os, sys

settings_path = sys.argv[1]
with open(settings_path, 'r') as f:
    settings = json.load(f)

if 'mcpServers' in settings and 'firecrawl-mcp' in settings['mcpServers']:
    del settings['mcpServers']['firecrawl-mcp']
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    print('v Removed MCP server from ~/.claude.json')
else:
    print('  MCP server not found in ~/.claude.json (already removed)')
PY
fi

echo ""
echo "v Firecrawl extension uninstalled."
echo "  Core Claude SEO skills are unchanged."
