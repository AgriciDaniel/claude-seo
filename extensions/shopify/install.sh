#!/usr/bin/env bash
# Claude SEO: Shopify Crawler Access extension installer.
#
# Plugin installs already ship the skill (skills/seo-shopify), so nothing is
# copied there. Manual installs (~/.claude/skills/seo) get the skill copied with
# its launcher path rewritten, because they have no ${CLAUDE_PLUGIN_ROOT}.
# The scripts it uses (shopify_env.py, shopify_crawl.py) ship with claude-seo
# already. No API keys: the crawl credential is minted in the merchant's Shopify
# admin and lives in a project-local .shopify-env (see docs/SHOPIFY-SETUP.md).
# On request the installer creates that file from the template with mode 0600;
# it never asks for, reads or prints a signature.
set -euo pipefail

main() {
    SKILL_DIR="${HOME}/.claude/skills"

    echo "════════════════════════════════════════"
    echo "║   Claude SEO: Shopify Crawler Access  ║"
    echo "════════════════════════════════════════"

    SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd)"

    # Support both manual (~/.claude/skills/seo) and plugin installs
    # (${CLAUDE_PLUGIN_ROOT}, this checkout, or ~/.claude/plugins/cache/...).
    # A plugin install never populates ~/.claude/skills/seo, so that check alone
    # would always abort; check the plugin locations too before failing.
    INSTALL_MODE=""
    PLUGIN_ROOT=""
    if [ -d "${SKILL_DIR}/seo" ]; then
        INSTALL_MODE="manual"
    elif [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -d "${CLAUDE_PLUGIN_ROOT}/skills/seo" ]; then
        INSTALL_MODE="plugin"; PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
    else
        _OWN_ROOT="$(cd "${SOURCE_DIR}/../.." >/dev/null 2>&1 && pwd || true)"
        if [ -n "${_OWN_ROOT}" ] && [ -d "${_OWN_ROOT}/skills/seo" ] && [ -f "${_OWN_ROOT}/.claude-plugin/plugin.json" ]; then
            INSTALL_MODE="plugin"; PLUGIN_ROOT="${_OWN_ROOT}"
        else
            _GLOB_MATCH=$(ls -d "${HOME}/.claude/plugins/cache/"*/claude-seo/*/skills/seo 2>/dev/null | tail -n1 || true)
            if [ -n "${_GLOB_MATCH}" ] && [ -d "${_GLOB_MATCH}" ]; then
                INSTALL_MODE="plugin"; PLUGIN_ROOT="$(cd "${_GLOB_MATCH}/../.." >/dev/null 2>&1 && pwd)"
            fi
        fi
    fi
    if [ -z "${INSTALL_MODE}" ]; then
        echo "✗ claude-seo base not installed (no plugin install and no ~/.claude/skills/seo)."
        exit 1
    fi

    if [ "${INSTALL_MODE}" = "plugin" ]; then
        echo "✓ claude-seo plugin detected: the seo-shopify skill ships with it, nothing to copy."
        if [ ! -f "${PLUGIN_ROOT}/skills/seo-shopify/SKILL.md" ]; then
            echo "! This plugin version does not ship the seo-shopify skill yet."
            echo "  Update the claude-seo plugin, then /seo shopify will load."
        fi
    fi

    if [ "${INSTALL_MODE}" = "manual" ]; then
        # Same rewrite the main installer applies: a copied personal skill has
        # no ${CLAUDE_PLUGIN_ROOT}, so the launcher token becomes the absolute
        # manual-install path. In a basic regular expression "$" is literal
        # unless it ends the expression, so the token needs no escaping.
        mkdir -p "${SKILL_DIR}/seo-shopify"
        sed -e 's#"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo"#"$HOME/.claude/skills/seo/scripts/claude-seo"#g' \
            "${SOURCE_DIR}/skills/seo-shopify/SKILL.md" > "${SKILL_DIR}/seo-shopify/SKILL.md"
        echo "✓ Installed skill: ${SKILL_DIR}/seo-shopify/SKILL.md"
    fi

    # Optional: start .shopify-env from the template. It will hold a client
    # credential, so it is created owner-only and an existing file is kept.
    ENV_TARGET="${PWD}/.shopify-env"
    REPLY=""
    if [ -e "${ENV_TARGET}" ] || [ -L "${ENV_TARGET}" ]; then
        # A dangling symlink counts too: BSD cp would write through it.
        echo "✓ ${ENV_TARGET} already exists; left untouched."
    else
        echo
        echo "The signature belongs in .shopify-env, in the folder you run audits from."
        read -rp "Create ${ENV_TARGET} from the template now? [y/N]: " REPLY || REPLY=""
        if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
            ( umask 077; cp "${SOURCE_DIR}/.shopify-env.example" "${ENV_TARGET}" )
            chmod 600 "${ENV_TARGET}"
            echo "✓ Created ${ENV_TARGET} (mode 0600, placeholders only). Keep it out of git."
        fi
    fi

    echo
    echo "Next: issue a Crawler Access signature in the Shopify admin and write it to"
    echo "      .shopify-env in your audit folder (template: ${SOURCE_DIR}/.shopify-env.example)."
    if [ "${INSTALL_MODE}" = "plugin" ]; then
        echo "Done. Try: /seo shopify https://shop.example"
    else
        echo "Done. Restart Claude Code so the skill loads, then try: /seo shopify https://shop.example"
    fi
}
main "$@"
