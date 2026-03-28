#!/usr/bin/env bash
set -euo pipefail

# Claude SEO Installer
# Wraps everything in main() to prevent partial execution on network failure

main() {
    SKILL_DIR="${HOME}/.claude/skills/seo"
    AGENT_DIR="${HOME}/.claude/agents"
    REPO_URL="https://github.com/AgriciDaniel/claude-seo"
    # Pin to a specific release tag to prevent silent updates from main.
    # Override: CLAUDE_SEO_TAG=main bash install.sh
    REPO_TAG="${CLAUDE_SEO_TAG:-v1.6.0}"

    echo "════════════════════════════════════════"
    echo "║   Claude SEO - Installer             ║"
    echo "║   Claude Code SEO Skill              ║"
    echo "════════════════════════════════════════"
    echo ""

    # Check prerequisites
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        echo "✓ Python ${PYTHON_VERSION} detected"
    else
        echo "⚠  Python 3 not found. uv can install it automatically if needed."
    fi

    # Determine source: local repo or GitHub download
    # Local mode: auto-detected when install.sh is run from within the repo
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    LOCAL_SOURCE=""

    if [ -f "${SCRIPT_DIR}/seo/SKILL.md" ]; then
        LOCAL_SOURCE="${SCRIPT_DIR}"
    fi

    # Helper: symlink in local mode, copy in remote mode
    install_to() {
        local src="$1" dst="$2"
        if [ -n "${LOCAL_SOURCE}" ]; then
            rm -rf "${dst}"
            ln -sfn "${src}" "${dst}"
        else
            if [ -d "${src}" ]; then
                mkdir -p "${dst}"
                cp -r "${src}/"* "${dst}/"
            else
                cp -r "${src}" "${dst}"
            fi
        fi
    }

    # Create directories
    mkdir -p "${SKILL_DIR}"
    mkdir -p "${AGENT_DIR}"

    if [ -n "${LOCAL_SOURCE}" ]; then
        echo "→ Installing from local source (symlinked): ${LOCAL_SOURCE}"
        SOURCE_DIR="${LOCAL_SOURCE}"
    else
        command -v git >/dev/null 2>&1 || { echo "✗ Git is required but not installed."; exit 1; }
        TEMP_DIR=$(mktemp -d)
        trap "rm -rf ${TEMP_DIR}" EXIT
        echo "↓ Downloading Claude SEO (${REPO_TAG})..."
        git clone --depth 1 --branch "${REPO_TAG}" "${REPO_URL}" "${TEMP_DIR}/claude-seo" 2>/dev/null
        SOURCE_DIR="${TEMP_DIR}/claude-seo"
    fi

    # Main skill: install individual items from seo/ into SKILL_DIR
    echo "→ Installing skill files..."
    for item in "${SOURCE_DIR}/seo/"*; do
        [ -e "${item}" ] || continue
        install_to "${item}" "${SKILL_DIR}/$(basename "${item}")"
    done

    # Sub-skills
    if [ -d "${SOURCE_DIR}/skills" ]; then
        for skill_dir in "${SOURCE_DIR}/skills"/*/; do
            skill_name=$(basename "${skill_dir}")
            install_to "${skill_dir%/}" "${HOME}/.claude/skills/${skill_name}"
        done
    fi

    # Schema, pdf, scripts, hooks -> merged into SKILL_DIR
    for dir_name in schema pdf scripts hooks; do
        if [ -d "${SOURCE_DIR}/${dir_name}" ]; then
            install_to "${SOURCE_DIR}/${dir_name}" "${SKILL_DIR}/${dir_name}"
        fi
    done

    # Agents
    echo "→ Installing subagents..."
    for agent_file in "${SOURCE_DIR}/agents/"*.md; do
        [ -f "${agent_file}" ] || continue
        install_to "${agent_file}" "${AGENT_DIR}/$(basename "${agent_file}")"
    done

    # Make hooks executable
    chmod +x "${SKILL_DIR}/hooks/"*.sh 2>/dev/null || true
    chmod +x "${SKILL_DIR}/hooks/"*.py 2>/dev/null || true

    # Extensions (optional add-ons: dataforseo, banana)
    if [ -d "${SOURCE_DIR}/extensions" ]; then
        echo "→ Installing extensions..."
        for ext_dir in "${SOURCE_DIR}/extensions"/*/; do
            [ -d "${ext_dir}" ] || continue
            ext_name=$(basename "${ext_dir}")
            # Extension skills
            if [ -d "${ext_dir}skills" ]; then
                for ext_skill in "${ext_dir}skills"/*/; do
                    [ -d "${ext_skill}" ] || continue
                    ext_skill_name=$(basename "${ext_skill}")
                    install_to "${ext_skill%/}" "${HOME}/.claude/skills/${ext_skill_name}"
                done
            fi
            # Extension agents
            if [ -d "${ext_dir}agents" ]; then
                for agent_file in "${ext_dir}agents/"*.md; do
                    [ -f "${agent_file}" ] || continue
                    install_to "${agent_file}" "${AGENT_DIR}/$(basename "${agent_file}")"
                done
            fi
            # Extension references
            if [ -d "${ext_dir}references" ]; then
                mkdir -p "${SKILL_DIR}/extensions/${ext_name}"
                install_to "${ext_dir}references" "${SKILL_DIR}/extensions/${ext_name}/references"
            fi
            # Extension scripts
            if [ -d "${ext_dir}scripts" ]; then
                mkdir -p "${SKILL_DIR}/extensions/${ext_name}"
                install_to "${ext_dir}scripts" "${SKILL_DIR}/extensions/${ext_name}/scripts"
            fi
        done
    fi

    # Check for uv (required for running scripts via PEP 723 inline metadata)
    if command -v uv >/dev/null 2>&1; then
        echo "  ✓ uv detected -- scripts will auto-resolve dependencies via PEP 723"
        echo "→ Installing Playwright browsers (optional, for visual analysis)..."
        uv run --with playwright python -m playwright install chromium 2>/dev/null || \
            echo "  ⚠  Playwright browser install failed. Visual analysis will use WebFetch fallback."
    else
        echo "  ⚠  uv not found. Install it: https://docs.astral.sh/uv/getting-started/installation/"
        echo "     Scripts use PEP 723 inline metadata and require 'uv run' to execute."
    fi

    echo ""
    echo "✓ Claude SEO installed successfully!"
    if [ -n "${LOCAL_SOURCE}" ]; then
        echo "  (local mode: changes to source files are reflected immediately)"
    fi
    echo ""
    echo "Usage:"
    echo "  1. Start Claude Code:  claude"
    echo "  2. Run commands:       /seo audit https://example.com"
    echo ""
    echo "To uninstall: curl -fsSL ${REPO_URL}/raw/main/uninstall.sh | bash"
}

main "$@"
