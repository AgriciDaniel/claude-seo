#!/usr/bin/env bash
# claude-seo manual-install uninstaller (Unix / macOS / Linux)
#
# Removes the orchestrator skill (~/.claude/skills/seo), its sub-skills and its
# sub-agents.
#
# install.sh records every skill and agent it installs in
# ~/.claude/skills/seo/.claude-seo-manifest. When that manifest exists, only the
# entries it lists are removed, so a seo-* skill or agent you wrote yourself is
# left alone. Installs made before the manifest existed fall back to removing
# every seo-* skill directory and seo-*.md agent file.
#
# Plugin-install users should use Claude Code's own command instead:
#   /plugin uninstall claude-seo@agricidaniel-claude-seo
#   /plugin marketplace remove AgriciDaniel/claude-seo
set -euo pipefail

CLAUDE_DIR="${HOME}/.claude"
SKILL_DIR="${CLAUDE_DIR}/skills"
AGENT_DIR="${CLAUDE_DIR}/agents"
MANIFEST="${SKILL_DIR}/seo/.claude-seo-manifest"

main() {
    echo "→ Uninstalling Claude SEO..."

    local removed_skills=0
    local removed_agents=0

    if [ -f "${MANIFEST}" ]; then
        # Read the whole manifest first: it lives inside skills/seo, which is
        # one of the entries removed below.
        local entries
        entries=$(cat "${MANIFEST}")
        local key path
        while IFS= read -r key; do
            # Accept only the exact shapes install.sh writes, so a damaged or
            # edited manifest can never point rm outside these folders.
            if [[ "${key}" =~ ^skills/seo(-[A-Za-z0-9_-]+)?$ ]]; then
                path="${CLAUDE_DIR}/${key}"
                if [ -d "${path}" ]; then
                    rm -rf "${path}"
                    echo "  Removed: ${path}"
                    removed_skills=$((removed_skills + 1))
                fi
            elif [[ "${key}" =~ ^agents/seo-[A-Za-z0-9_-]+\.md$ ]]; then
                path="${CLAUDE_DIR}/${key}"
                if [ -f "${path}" ]; then
                    rm -f "${path}"
                    echo "  Removed: ${path}"
                    removed_agents=$((removed_agents + 1))
                fi
            elif [ -n "${key}" ]; then
                echo "  Skipped unexpected manifest entry: ${key}"
            fi
        done <<< "${entries}"
    else
        echo "  No install manifest found (older install); removing every seo-* skill and agent."

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
    fi

    if [ "${removed_skills}" -eq 0 ] && [ "${removed_agents}" -eq 0 ]; then
        echo "  Nothing to remove. Claude SEO does not appear to be installed."
        echo "  If you installed via /plugin install, run /plugin uninstall instead."
        return 0
    fi

    echo "✓ Claude SEO uninstalled (${removed_skills} skill dirs, ${removed_agents} agent files)."
}

main "$@"
