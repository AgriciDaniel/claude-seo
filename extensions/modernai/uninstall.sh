#!/usr/bin/env bash
# Claude SEO -- Modern AI Extension Uninstaller

set -euo pipefail

SKILL_DIR="${HOME}/.claude/skills/seo-modernai"

if [ -d "${SKILL_DIR}" ]; then
  rm -rf "${SKILL_DIR}"
  echo "Removed ${SKILL_DIR}"
else
  echo "Not installed (${SKILL_DIR} not found)."
fi
