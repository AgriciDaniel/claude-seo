#!/usr/bin/env bash
# claude-seo manual-install uninstaller (Unix / macOS / Linux)
#
# Removes the orchestrator skill (~/.claude/skills/seo), all sub-skills
# (~/.claude/skills/seo-*), and all sub-agents (~/.claude/agents/seo-*.md).
#
# Uses glob enumeration rather than a hardcoded list so future skill
# additions are cleaned up automatically without releasing a new
# uninstaller.
#
# Plugin-install users should use Claude Code's own command instead:
#   /plugin uninstall claude-seo@agricidaniel-seo
#   /plugin marketplace remove AgriciDaniel/claude-seo
set -euo pipefail

SKILL_DIR="${HOME}/.claude/skills"
AGENT_DIR="${HOME}/.claude/agents"

main() {
    echo "→ Uninstalling Claude SEO..."

    local removed_skills=0
    local removed_agents=0

    # Allow empty globs to expand to nothing rather than the literal pattern
    shopt -s nullglob

    # Remove orchestrator if present
    if [ -d "${SKILL_DIR}/seo" ]; then
        rm -rf "${SKILL_DIR}/seo"
        echo "  Removed: ${SKILL_DIR}/seo"
        removed_skills=$((removed_skills + 1))
    fi

    # Remove every seo-* sub-skill directory
    for skill_path in "${SKILL_DIR}"/seo-*; do
        if [ -d "${skill_path}" ]; then
            rm -rf "${skill_path}"
            echo "  Removed: ${skill_path}"
            removed_skills=$((removed_skills + 1))
        fi
    done

    # Remove every seo-*.md agent file
    for agent_path in "${AGENT_DIR}"/seo-*.md; do
        if [ -f "${agent_path}" ]; then
            rm -f "${agent_path}"
            echo "  Removed: ${agent_path}"
            removed_agents=$((removed_agents + 1))
        fi
    done

    shopt -u nullglob

    if [ "${removed_skills}" -eq 0 ] && [ "${removed_agents}" -eq 0 ]; then
        echo "  Nothing to remove. Claude SEO does not appear to be installed."
        echo "  If you installed via /plugin install, run /plugin uninstall instead."
        return 0
    fi

    echo "✓ Claude SEO uninstalled (${removed_skills} skill dirs, ${removed_agents} agent files)."
}

main "$@"
