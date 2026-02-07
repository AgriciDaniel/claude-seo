#!/usr/bin/env bash
set -euo pipefail

main() {
    echo "→ Uninstalling Claude SEO..."

    # Remove main skill
    rm -rf "${HOME}/.claude/skills/seo"

    # Remove sub-skills
    for skill in seo-audit seo-competitor-pages seo-content seo-geo seo-hreflang seo-images seo-page seo-plan seo-programmatic seo-schema seo-sitemap seo-technical; do
        rm -rf "${HOME}/.claude/skills/${skill}"
    done

    # Remove agents
    for agent in seo-technical seo-content seo-schema seo-sitemap seo-performance seo-visual; do
        rm -f "${HOME}/.claude/agents/${agent}.md"
    done

    echo "✓ Claude SEO uninstalled."
}

main "$@"
