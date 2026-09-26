#!/usr/bin/env bash
# Claude SEO — Shopify Crawler Access extension installer.
#
# Copies the seo-shopify skill next to the other skills. The scripts it uses
# (shopify_env.py, shopify_crawl.py) ship with claude-seo already. No API keys:
# the crawl credential is minted in the merchant's Shopify admin and lives in a
# project-local .shopify-env (see docs/SHOPIFY-SETUP.md).
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"

    echo "════════════════════════════════════════"
    echo "║   Claude SEO — Shopify Crawler Access ║"
    echo "════════════════════════════════════════"

    [ ! -d "${SKILL_DIR}/seo" ] && { echo "✗ claude-seo base not installed."; exit 1; }

    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    mkdir -p "${SKILL_DIR}/seo-shopify"
    cp "${SOURCE_DIR}/skills/seo-shopify/SKILL.md" "${SKILL_DIR}/seo-shopify/SKILL.md"
    echo "✓ Installed skill: ${SKILL_DIR}/seo-shopify"
    echo "Next: issue a Crawler Access signature in the Shopify admin and write it to"
    echo "      .shopify-env in your audit folder (template: ${SOURCE_DIR}/.shopify-env.example)."
    echo "Done. Try: /seo shopify https://shop.example"
}
main "$@"
