#!/usr/bin/env bash
set -euo pipefail

main() {
    echo "-> Uninstalling Atlas Cloud SEO image generation extension..."
    rm -rf "${HOME}/.claude/skills/seo-atlas-image-gen"
    echo "v Atlas Cloud extension uninstalled."
}

main "$@"
