#!/usr/bin/env bash
set -euo pipefail

echo "Removing Google Search Console extension..."

# Remove skill directory
rm -rf "${HOME}/.claude/skills/seo-gsc-extension"
echo "v Removed skill files"

# Remove MCP entry from settings.json
SETTINGS_FILE="${HOME}/.claude/settings.json"
if [ -f "${SETTINGS_FILE}" ]; then
    python3 - "${SETTINGS_FILE}" <<'PY' || echo "  Warning: Could not update settings.json automatically."
import json, os, sys

settings_path = sys.argv[1]
with open(settings_path, 'r') as f:
    settings = json.load(f)

if 'mcpServers' in settings and 'google-searchconsole-mcp' in settings['mcpServers']:
    del settings['mcpServers']['google-searchconsole-mcp']
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    print('v Removed MCP server from settings.json')
else:
    print('  MCP server not found in settings.json (already removed)')
PY
fi

echo ""
echo "Note: the OAuth token cache at ~/.gsc-mcp/tokens/ is left in place."
echo "Remove it manually (rm -rf ~/.gsc-mcp) to fully revoke local access."
echo ""
echo "v Google Search Console extension uninstalled."
echo "  Core Claude SEO skills are unchanged."
