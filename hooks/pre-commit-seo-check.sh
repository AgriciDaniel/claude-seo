#!/usr/bin/env bash
set -euo pipefail

# Pre-commit SEO validation hook for Claude Code.
#
# Hook configuration in ~/.claude/settings.json:
# {
#   "hooks": {
#     "PreToolUse": [
#       {
#         "matcher": "Bash",
#         "hooks": [
#           {
#             "type": "command",
#             "command": "~/.claude/skills/seo/hooks/pre-commit-seo-check.sh",
#             "exitCodes": { "2": "block" }
#           }
#         ]
#       }
#     ]
#   }
# }
#
# NOTE: The matcher is "Bash" (tool name only). This script runs on ALL
# Bash tool uses. It checks if there are staged files before proceeding.
# If there are no staged changes, it exits 0 immediately.

ERRORS=0
WARNINGS=0

# Check if there are staged changes — exit early if not
if ! git diff --cached --quiet 2>/dev/null; then
    : # There are staged changes, proceed with checks
else
    exit 0  # No staged changes, nothing to check
fi

echo "🔍 Running pre-commit SEO checks..."

# Check staged HTML-like files
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep -E '\.(html|htm|php|jsx|tsx|vue|svelte)$' || true)

if [ -z "${STAGED_FILES}" ]; then
    echo "✓ No HTML files staged — skipping SEO checks"
    exit 0
fi

for file in ${STAGED_FILES}; do
    if [ ! -f "${file}" ]; then
        continue
    fi

    # Check for placeholder text in schema
    if grep -qiE '\[(Business Name|City|State|Phone|Address|Your|INSERT|REPLACE)\]' "${file}" 2>/dev/null; then
        echo "🛑 ${file}: Contains placeholder text in schema markup"
        ERRORS=$((ERRORS + 1))
    fi

    # Check title tag length
    TITLE=$(grep -oP '(?<=<title>).*?(?=</title>)' "${file}" 2>/dev/null | head -1 || true)
    if [ -n "${TITLE}" ]; then
        TITLE_LEN=${#TITLE}
        if [ "${TITLE_LEN}" -lt 30 ] || [ "${TITLE_LEN}" -gt 70 ]; then
            echo "⚠️  ${file}: Title tag length ${TITLE_LEN} chars (recommend 30-60)"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi

    # Check for images without alt text
    if grep -qP '<img(?![^>]*alt=)' "${file}" 2>/dev/null; then
        echo "⚠️  ${file}: Images found without alt text"
        WARNINGS=$((WARNINGS + 1))
    fi

    # Check for deprecated schema types
    if grep -qE '"@type"\s*:\s*"(HowTo|SpecialAnnouncement)"' "${file}" 2>/dev/null; then
        echo "🛑 ${file}: Contains deprecated schema type"
        ERRORS=$((ERRORS + 1))
    fi

    # Check for FID references (should be INP)
    if grep -qi 'First Input Delay\|"FID"' "${file}" 2>/dev/null; then
        echo "⚠️  ${file}: References FID — should use INP (Interaction to Next Paint)"
        WARNINGS=$((WARNINGS + 1))
    fi

    # Check meta description length
    META_DESC=$(grep -oP '(?<=<meta name="description" content=").*?(?=")' "${file}" 2>/dev/null | head -1 || true)
    if [ -n "${META_DESC}" ]; then
        META_LEN=${#META_DESC}
        if [ "${META_LEN}" -lt 120 ] || [ "${META_LEN}" -gt 160 ]; then
            echo "⚠️  ${file}: Meta description length ${META_LEN} chars (recommend 120-160)"
            WARNINGS=$((WARNINGS + 1))
        fi
    fi
done

echo ""
if [ "${ERRORS}" -gt 0 ]; then
    echo "🛑 ${ERRORS} critical error(s) found — commit blocked"
    echo "Fix the errors above and try again."
    exit 2
elif [ "${WARNINGS}" -gt 0 ]; then
    echo "⚠️  ${WARNINGS} warning(s) found — commit allowed"
    exit 0
else
    echo "✓ All SEO checks passed"
    exit 0
fi
