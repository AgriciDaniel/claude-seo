#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="${HOME}/.claude/skills/seo-posthog"
AGENT_FILE="${HOME}/.claude/agents/seo-posthog.md"
REMOVED=""
[ -d "${SKILL_DIR}" ] && rm -rf "${SKILL_DIR}" && echo "✓ Removed ${SKILL_DIR}" && REMOVED=1
[ -f "${AGENT_FILE}" ] && rm -f "${AGENT_FILE}" && echo "✓ Removed ${AGENT_FILE}" && REMOVED=1
if [ -z "${REMOVED}" ]; then
    # Plugin installs have no copied files: the plugin provides both.
    echo "No copied skill or agent found. On a plugin install both ship with the plugin and stay."
fi
echo "Note: the PostHog MCP server registration was not touched."
echo "Remove it with: claude mcp remove posthog"
