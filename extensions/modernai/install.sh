#!/usr/bin/env bash
# Claude SEO -- Modern AI Extension Installer

set -euo pipefail

EXTENSION_NAME="modernai"
SKILL_DIR="${HOME}/.claude/skills/seo-${EXTENSION_NAME}"

echo "Claude SEO -- Modern AI Extension"
echo "=================================="
echo ""

# --- Prerequisite check: base claude-seo package ---
if [ ! -d "${HOME}/.claude/skills" ]; then
  echo "ERROR: ~/.claude/skills not found. Install the base claude-seo package first."
  exit 1
fi

# --- Create the skill directory ---
mkdir -p "${SKILL_DIR}"

# --- Copy skill definition ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "${SCRIPT_DIR}/skills/seo-modernai/SKILL.md" "${SKILL_DIR}/SKILL.md"

echo "Installed: ${SKILL_DIR}/SKILL.md"
echo ""
echo "No API key required -- this extension queries Modern AI's free, gated"
echo "known-entity lookup endpoint directly (anonymous access, rate-limited)."
echo ""
echo "Usage: \"/seo modernai brandname\""
