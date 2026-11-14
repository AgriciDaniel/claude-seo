#!/usr/bin/env bash
set -euo pipefail
SKILL_DIR="${HOME}/.claude/skills/seo-shopify"
if [ -d "${SKILL_DIR}" ]; then
    rm -rf "${SKILL_DIR}" && echo "✓ Removed ${SKILL_DIR}"
else
    # Plugin installs have no copied skill: the plugin provides seo-shopify.
    echo "No copied skill at ${SKILL_DIR}. On a plugin install the skill ships with the plugin and stays."
fi
echo "Done. (Nothing to remove from settings.json; the credential lives in your project's .shopify-env, which was not touched.)"
