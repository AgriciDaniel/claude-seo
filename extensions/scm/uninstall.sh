#!/usr/bin/env bash
set -euo pipefail

echo "Removing SEO Content Machine extension..."

rm -rf "${HOME}/.claude/skills/seo-scm"
echo "v Removed skill files"

MCP_CONFIG_FILE="${HOME}/.claude.json"
if [ -f "${MCP_CONFIG_FILE}" ]; then
    python3 - "${MCP_CONFIG_FILE}" <<'PY' || echo "  Warning: Could not update ~/.claude.json automatically."
import json, sys

settings_path = sys.argv[1]
with open(settings_path, 'r') as f:
    settings = json.load(f)

entry = settings.get('mcpServers', {}).get('scm')
if entry and any(str(arg).startswith('seo-content-machine-mcp') for arg in entry.get('args', [])):
    del settings['mcpServers']['scm']
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    print('v Removed MCP server from ~/.claude.json')
else:
    print('  No "scm" MCP server from this extension in ~/.claude.json; any other "scm" entry is left alone')
PY
fi

echo ""
echo "v SEO Content Machine extension uninstalled."
echo "  Core Claude SEO skills are unchanged."
