#!/usr/bin/env bash
set -euo pipefail

# Claude SEO Installer
# Wraps everything in main() to prevent partial execution on network failure

main() {
    SKILL_DIR="${HOME}/.claude/skills/seo"
    AGENT_DIR="${HOME}/.claude/agents"
    REPO_URL="https://github.com/AgriciDaniel/claude-seo"
    # Pin to a specific release tag to prevent silent updates from main.
    # This default MUST be bumped on every release. CI guard
    # (tests/test_manifest_consistency.py) enforces this matches plugin.json.
    # Override: CLAUDE_SEO_TAG=main bash install.sh
    REPO_TAG="${CLAUDE_SEO_TAG:-v2.2.5}"

    echo "════════════════════════════════════════"
    echo "║   Claude SEO - Installer             ║"
    echo "║   Claude Code SEO Skill              ║"
    echo "════════════════════════════════════════"
    echo ""

    # Check prerequisites. The runtime launcher performs cross-platform Python
    # resolution and validates the minimum supported version.
    command -v git >/dev/null 2>&1 || { echo "✗ Git is required but not installed."; exit 1; }

    # Create directories
    mkdir -p "${SKILL_DIR}"
    mkdir -p "${AGENT_DIR}"

    # Clone or update
    TEMP_DIR=$(mktemp -d)
    cleanup() { rm -rf -- "${TEMP_DIR}"; }
    trap cleanup EXIT

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

    # Copy deterministic data files consumed by bundled scripts such as
    # seo_updates.py. Keep the repository-relative data/ layout intact.
    if [ -d "${TEMP_DIR}/claude-seo/data" ]; then
        mkdir -p "${SKILL_DIR}/data"
        cp -r "${TEMP_DIR}/claude-seo/data/"* "${SKILL_DIR}/data/"
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

    # Copy the stable runtime launcher. Manual installs use its explicit path;
    # plugin installs expose the repository bin/ directory automatically.
    if [ -f "${TEMP_DIR}/claude-seo/bin/claude-seo" ]; then
        mkdir -p "${SKILL_DIR}/bin"
        cp "${TEMP_DIR}/claude-seo/bin/claude-seo" "${SKILL_DIR}/bin/claude-seo"
        chmod +x "${SKILL_DIR}/bin/claude-seo"
    fi

    # Copy hooks
    if [ -d "${TEMP_DIR}/claude-seo/hooks" ]; then
        mkdir -p "${SKILL_DIR}/hooks"
        cp -r "${TEMP_DIR}/claude-seo/hooks/"* "${SKILL_DIR}/hooks/"
        chmod +x "${SKILL_DIR}/hooks/"*.sh 2>/dev/null || true
        chmod +x "${SKILL_DIR}/hooks/"*.py 2>/dev/null || true
        # Manual installs copy hook files only; enforcement loads through the plugin manifest.
        echo "  Note: hook enforcement requires plugin install (/plugin install ${REPO_URL}); manual hook copy is best-effort."
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
    cp "${TEMP_DIR}/claude-seo/.claude-plugin/plugin.json" "${SKILL_DIR}/runtime-plugin.json" 2>/dev/null || true

    # Manual installs cannot rely on plugin bin/ PATH injection. Rewrite only
    # exact files copied from this checkout during this install.
    rewrite_doc() {
        local doc="$1" temp_doc
        temp_doc="${doc}.claude-seo-tmp"
        sed -e 's#claude-seo run#"$HOME/.claude/skills/seo/bin/claude-seo" run#g' \
            -e 's#claude-seo setup#"$HOME/.claude/skills/seo/bin/claude-seo" setup#g' \
            -e 's#claude-seo doctor#"$HOME/.claude/skills/seo/bin/claude-seo" doctor#g' \
            "${doc}" > "${temp_doc}"
        mv "${temp_doc}" "${doc}"
    }
    for source_root in "${TEMP_DIR}/claude-seo/skills"/*; do
        [ -d "${source_root}" ] || continue
        skill_name=$(basename "${source_root}")
        while IFS= read -r -d '' source_doc; do
            relative_doc=${source_doc#"${source_root}/"}
            doc="${HOME}/.claude/skills/${skill_name}/${relative_doc}"
            [ -f "${doc}" ] && rewrite_doc "${doc}"
        done < <(find "${source_root}" -type f -name '*.md' -print0)
    done
    for source_root in "${TEMP_DIR}/claude-seo/extensions"/*/skills/*; do
        [ -d "${source_root}" ] || continue
        skill_name=$(basename "${source_root}")
        while IFS= read -r -d '' source_doc; do
            relative_doc=${source_doc#"${source_root}/"}
            doc="${HOME}/.claude/skills/${skill_name}/${relative_doc}"
            [ -f "${doc}" ] && rewrite_doc "${doc}"
        done < <(find "${source_root}" -type f -name '*.md' -print0)
    done
    for source_root in "${TEMP_DIR}/claude-seo/extensions"/*/references; do
        [ -d "${source_root}" ] || continue
        ext_name=$(basename "$(dirname "${source_root}")")
        while IFS= read -r -d '' source_doc; do
            relative_doc=${source_doc#"${source_root}/"}
            doc="${SKILL_DIR}/extensions/${ext_name}/references/${relative_doc}"
            [ -f "${doc}" ] && rewrite_doc "${doc}"
        done < <(find "${source_root}" -type f -name '*.md' -print0)
    done
    for source_doc in "${TEMP_DIR}/claude-seo/agents"/*.md "${TEMP_DIR}/claude-seo/extensions"/*/agents/*.md; do
        [ -f "${source_doc}" ] || continue
        doc="${AGENT_DIR}/$(basename "${source_doc}")"
        [ -f "${doc}" ] && rewrite_doc "${doc}"
    done

    echo "→ Creating isolated Python runtime..."
    set +e
    "${SKILL_DIR}/bin/claude-seo" setup
    runtime_status=$?
    set -e
    if [ "${runtime_status}" -ne 0 ] && [ "${runtime_status}" -ne 10 ]; then
        echo "✗ Core Python runtime setup failed. Installation is incomplete." >&2
        exit 1
    elif [ "${runtime_status}" -eq 10 ]; then
        echo "⚠ Core runtime installed, but Chromium setup is incomplete." >&2
    fi

    echo ""
    echo "✓ Claude SEO installed successfully!"
    echo ""
    echo "Usage:"
    echo "  1. Start Claude Code:  claude"
    echo "  2. Run commands:       /seo audit https://example.com"
    echo ""
    echo "Python deps location: ${SKILL_DIR}/requirements.txt"
    echo "Inspect remote scripts before piping them to bash."
    echo "To uninstall: curl -fsSL ${REPO_URL}/raw/main/uninstall.sh | bash"
}

main "$@"
