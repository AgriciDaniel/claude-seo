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
    REPO_TAG="${CLAUDE_SEO_TAG:-v1.9.0}"

    echo "════════════════════════════════════════"
    echo "║   Claude SEO - Installer             ║"
    echo "║   Claude Code SEO Skill              ║"
    echo "════════════════════════════════════════"
    echo ""

    # Check prerequisites
    command -v python3 >/dev/null 2>&1 || { echo "✗ Python 3 is required but not installed."; exit 1; }
    command -v git >/dev/null 2>&1 || { echo "✗ Git is required but not installed."; exit 1; }

    # Check Python version (3.10+ required)
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PYTHON_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')
    if [ "${PYTHON_OK}" = "0" ]; then
        echo "✗ Python 3.10+ is required but ${PYTHON_VERSION} was found."
        exit 1
    fi
    echo "✓ Python ${PYTHON_VERSION} detected"

    # Create directories
    mkdir -p "${SKILL_DIR}"
    mkdir -p "${AGENT_DIR}"

    # Clone or update
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf ${TEMP_DIR}" EXIT

    echo "↓ Downloading Claude SEO (${REPO_TAG})..."
    git clone --depth 1 --branch "${REPO_TAG}" "${REPO_URL}" "${TEMP_DIR}/claude-seo" 2>/dev/null

    # Copy skill files
    echo "→ Installing skill files..."
    cp -r "${TEMP_DIR}/claude-seo/skills/seo/"* "${SKILL_DIR}/"

    # Copy sub-skills
    if [ -d "${TEMP_DIR}/claude-seo/skills" ]; then
        for skill_dir in "${TEMP_DIR}/claude-seo/skills"/*/; do
            skill_name=$(basename "${skill_dir}")
            target="${HOME}/.claude/skills/${skill_name}"
            mkdir -p "${target}"
            cp -r "${skill_dir}"* "${target}/"
        done
    fi

    # Copy schema templates
    if [ -d "${TEMP_DIR}/claude-seo/schema" ]; then
        mkdir -p "${SKILL_DIR}/schema"
        cp -r "${TEMP_DIR}/claude-seo/schema/"* "${SKILL_DIR}/schema/"
    fi

    # Copy reference docs
    if [ -d "${TEMP_DIR}/claude-seo/pdf" ]; then
        mkdir -p "${SKILL_DIR}/pdf"
        cp -r "${TEMP_DIR}/claude-seo/pdf/"* "${SKILL_DIR}/pdf/"
    fi

    # Copy agents
    echo "→ Installing subagents..."
    cp -r "${TEMP_DIR}/claude-seo/agents/"*.md "${AGENT_DIR}/" 2>/dev/null || true

    # Copy shared scripts
    if [ -d "${TEMP_DIR}/claude-seo/scripts" ]; then
        mkdir -p "${SKILL_DIR}/scripts"
        cp -r "${TEMP_DIR}/claude-seo/scripts/"* "${SKILL_DIR}/scripts/"
    fi

    # Copy hooks
    if [ -d "${TEMP_DIR}/claude-seo/hooks" ]; then
        mkdir -p "${SKILL_DIR}/hooks"
        cp -r "${TEMP_DIR}/claude-seo/hooks/"* "${SKILL_DIR}/hooks/"
        chmod +x "${SKILL_DIR}/hooks/"*.sh 2>/dev/null || true
        chmod +x "${SKILL_DIR}/hooks/"*.py 2>/dev/null || true
    fi

    # Copy extensions (optional add-ons: dataforseo, banana)
    if [ -d "${TEMP_DIR}/claude-seo/extensions" ]; then
        echo "=> Installing extensions..."
        for ext_dir in "${TEMP_DIR}/claude-seo/extensions"/*/; do
            [ -d "${ext_dir}" ] || continue
            ext_name=$(basename "${ext_dir}")
            # Extension skills
            if [ -d "${ext_dir}skills" ]; then
                for ext_skill in "${ext_dir}skills"/*/; do
                    [ -d "${ext_skill}" ] || continue
                    ext_skill_name=$(basename "${ext_skill}")
                    target="${HOME}/.claude/skills/${ext_skill_name}"
                    mkdir -p "${target}"
                    cp -r "${ext_skill}"* "${target}/"
                done
            fi
            # Extension agents
            if [ -d "${ext_dir}agents" ]; then
                cp -r "${ext_dir}agents/"*.md "${AGENT_DIR}/" 2>/dev/null || true
            fi
            # Extension references
            if [ -d "${ext_dir}references" ]; then
                mkdir -p "${SKILL_DIR}/extensions/${ext_name}/references"
                cp -r "${ext_dir}references/"* "${SKILL_DIR}/extensions/${ext_name}/references/"
            fi
            # Extension scripts
            if [ -d "${ext_dir}scripts" ]; then
                mkdir -p "${SKILL_DIR}/extensions/${ext_name}/scripts"
                cp -r "${ext_dir}scripts/"* "${SKILL_DIR}/extensions/${ext_name}/scripts/"
            fi
        done
    fi

    # Copy requirements.txt to skill dir so users can retry later
    cp "${TEMP_DIR}/claude-seo/requirements.txt" "${SKILL_DIR}/requirements.txt" 2>/dev/null || true

    # Install Python dependencies (venv preferred, --user fallback)
    echo "→ Installing Python dependencies..."
    VENV_DIR="${SKILL_DIR}/.venv"
    if python3 -m venv "${VENV_DIR}" 2>/dev/null; then
        "${VENV_DIR}/bin/pip" install --quiet -r "${TEMP_DIR}/claude-seo/requirements.txt" 2>/dev/null && \
            echo "  ✓ Installed in venv at ${VENV_DIR}" || \
            echo "  ⚠  Venv pip install failed. Run: ${VENV_DIR}/bin/pip install -r ${SKILL_DIR}/requirements.txt"
    else
        pip install --quiet --user -r "${TEMP_DIR}/claude-seo/requirements.txt" 2>/dev/null || \
        echo "  ⚠  Could not auto-install. Run: pip install --user -r ${SKILL_DIR}/requirements.txt"
    fi

    # Optional: Install Playwright browsers (for screenshot analysis)
    echo "→ Installing Playwright browsers (optional, for visual analysis)..."
    if [ -f "${VENV_DIR}/bin/playwright" ]; then
        "${VENV_DIR}/bin/python" -m playwright install chromium 2>/dev/null || \
        echo "  ⚠  Playwright install failed. Visual analysis will use WebFetch fallback."
    else
        python3 -m playwright install chromium 2>/dev/null || \
        echo "  ⚠  Playwright install failed. Visual analysis will use WebFetch fallback."
    fi

    echo ""
    echo "✓ Claude SEO installed successfully!"
    echo ""
    echo "Usage:"
    echo "  1. Start Claude Code:  claude"
    echo "  2. Run commands:       /seo audit https://example.com"
    echo ""
    echo "Python deps location: ${SKILL_DIR}/requirements.txt"
    echo "To uninstall: curl -fsSL ${REPO_URL}/raw/main/uninstall.sh | bash"
}

main "$@"
