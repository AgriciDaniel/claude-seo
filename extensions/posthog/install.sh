#!/usr/bin/env bash
# Claude SEO: PostHog extension installer.
#
# Installs the seo-posthog skill and agent. Data comes from the PostHog MCP
# server, so no credential is collected or stored here.
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"
    AGENTS_DIR="${HOME}/.claude/agents"

    echo "════════════════════════════════════════"
    echo "║ Claude SEO - PostHog extension      ║"
    echo "════════════════════════════════════════"

    [ ! -d "${SKILL_DIR}/seo" ] && { echo "✗ claude-seo base not installed."; exit 1; }

    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    mkdir -p "${SKILL_DIR}/seo-posthog"
    cp "${SOURCE_DIR}/skills/seo-posthog/SKILL.md" "${SKILL_DIR}/seo-posthog/SKILL.md"
    echo "✓ Installed skill: ${SKILL_DIR}/seo-posthog/SKILL.md"

    mkdir -p "${AGENTS_DIR}"
    cp "${SOURCE_DIR}/agents/seo-posthog.md" "${AGENTS_DIR}/seo-posthog.md"
    echo "✓ Installed agent: ${AGENTS_DIR}/seo-posthog.md"

    if command -v claude >/dev/null 2>&1; then
        echo
        read -rp "Register the PostHog MCP server now (https://mcp.posthog.com/mcp)? [y/N]: " REPLY
        if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
            if claude mcp add --transport http posthog https://mcp.posthog.com/mcp; then
                echo "✓ MCP server registered. Run /mcp in Claude Code to authenticate."
            else
                echo "! Could not register the MCP server. See extensions/posthog/docs/POSTHOG-SETUP.md"
            fi
        fi
    else
        echo
        echo "! 'claude' CLI not found. Register the MCP server manually:"
        echo "  claude mcp add --transport http posthog https://mcp.posthog.com/mcp"
    fi

    echo
    echo "Done. Verify inside Claude Code with: /seo posthog check"
    echo "Full docs: extensions/posthog/docs/POSTHOG-SETUP.md"
}
main "$@"
