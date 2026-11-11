#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="${HOME}/.claude/skills/seo-posthog"
AGENT_FILE="${HOME}/.claude/agents/seo-posthog.md"
[ -d "${SKILL_DIR}" ] && rm -rf "${SKILL_DIR}" && echo "✓ Removed ${SKILL_DIR}"
[ -f "${AGENT_FILE}" ] && rm -f "${AGENT_FILE}" && echo "✓ Removed ${AGENT_FILE}"
echo "Note: the PostHog MCP server registration was not touched."
echo "Remove it with: claude mcp remove posthog"
