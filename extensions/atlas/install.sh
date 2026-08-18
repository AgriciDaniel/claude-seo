#!/usr/bin/env bash
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills/seo-atlas-image-gen"
    SEO_SKILL_DIR="${HOME}/.claude/skills/seo"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [ ! -d "${SEO_SKILL_DIR}" ]; then
        echo "x Claude SEO is not installed."
        echo "  Install Claude SEO before installing this extension."
        exit 1
    fi

    if [ -f "${SCRIPT_DIR}/skills/seo-atlas-image-gen/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}"
    elif [ -f "${SCRIPT_DIR}/extensions/atlas/skills/seo-atlas-image-gen/SKILL.md" ]; then
        SOURCE_DIR="${SCRIPT_DIR}/extensions/atlas"
    else
        echo "x Cannot find the Atlas extension source files."
        exit 1
    fi

    echo "-> Installing Atlas Cloud SEO image generation skill..."
    mkdir -p "${SKILL_DIR}/scripts" "${SKILL_DIR}/references"
    cp "${SOURCE_DIR}/skills/seo-atlas-image-gen/SKILL.md" "${SKILL_DIR}/SKILL.md"
    cp "${SOURCE_DIR}/scripts/"*.py "${SKILL_DIR}/scripts/"
    cp "${SOURCE_DIR}/references/"*.md "${SKILL_DIR}/references/"

    for installed_doc in "${SKILL_DIR}/SKILL.md" "${SKILL_DIR}/references/"*.md; do
        [ -f "${installed_doc}" ] || continue
        temp_doc="${installed_doc}.claude-seo-tmp"
        sed -e 's#claude-seo run#"$HOME/.claude/skills/seo/bin/claude-seo" run#g' \
            -e 's#claude-seo setup#"$HOME/.claude/skills/seo/bin/claude-seo" setup#g' \
            -e 's#claude-seo doctor#"$HOME/.claude/skills/seo/bin/claude-seo" doctor#g' \
            "${installed_doc}" > "${temp_doc}"
        mv "${temp_doc}" "${installed_doc}"
    done

    echo "v Atlas Cloud extension installed."
    echo "  Export ATLASCLOUD_API_KEY before generating an image."
    echo "  Usage: /seo atlas-image-gen og \"Professional SaaS dashboard\""
}

main "$@"
