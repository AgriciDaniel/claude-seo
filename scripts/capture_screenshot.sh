#!/usr/bin/env bash
#
# Capture screenshots of web pages using agent-browser.
#
# Usage:
#   ./capture_screenshot.sh https://example.com
#   ./capture_screenshot.sh https://example.com --mobile
#   ./capture_screenshot.sh https://example.com --viewport laptop
#   ./capture_screenshot.sh https://example.com --all --output screenshots/
#   ./capture_screenshot.sh https://example.com --full

set -euo pipefail

URL=""
OUTPUT_DIR="screenshots"
VIEWPORT="desktop"
FULL_PAGE=false

# Viewport dimensions (width x height)
declare -A VIEWPORT_W=( [desktop]=1920 [laptop]=1366 [tablet]=768  [mobile]=375 )
declare -A VIEWPORT_H=( [desktop]=1080 [laptop]=768  [tablet]=1024 [mobile]=812 )

usage() {
  echo "Usage: $0 <url> [options]"
  echo ""
  echo "Options:"
  echo "  --output,   -o <dir>     Output directory (default: screenshots)"
  echo "  --viewport, -v <name>    Viewport preset: desktop, laptop, tablet, mobile (default: desktop)"
  echo "  --all,      -a           Capture all viewport presets"
  echo "  --full,     -f           Capture full page (not just viewport)"
  echo "  --mobile,   -m           Shorthand for --viewport mobile"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output|-o)   OUTPUT_DIR="$2"; shift 2 ;;
    --viewport|-v) VIEWPORT="$2";   shift 2 ;;
    --all|-a)      VIEWPORT="all";  shift   ;;
    --full|-f)     FULL_PAGE=true;  shift   ;;
    --mobile|-m)   VIEWPORT="mobile"; shift ;;
    -h|--help)     usage ;;
    *)             URL="$1"; shift ;;
  esac
done

if [[ -z "$URL" ]]; then
  usage
fi

# Validate viewport
valid_viewports=(desktop laptop tablet mobile all)
if [[ ! " ${valid_viewports[*]} " =~ " ${VIEWPORT} " ]]; then
  echo "Error: invalid viewport '${VIEWPORT}'. Choose from: desktop, laptop, tablet, mobile, all"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Derive a safe base filename from the URL domain
DOMAIN=$(echo "$URL" | sed 's|https\?://||; s|/.*||; s/\./_/g')

capture() {
  local vp="$1"
  local w="${VIEWPORT_W[$vp]}"
  local h="${VIEWPORT_H[$vp]}"
  local out="$OUTPUT_DIR/${DOMAIN}_${vp}.png"

  echo "Capturing ${vp} (${w}x${h})..."

  agent-browser open "$URL"
  agent-browser wait --load networkidle
  agent-browser wait 1000
  agent-browser resize "$w" "$h"

  if $FULL_PAGE; then
    agent-browser screenshot --full "$out"
  else
    agent-browser screenshot "$out"
  fi

  echo "  ✓ Saved: $out"
  agent-browser close
}

if [[ "$VIEWPORT" == "all" ]]; then
  for vp in desktop laptop tablet mobile; do
    capture "$vp"
  done
else
  capture "$VIEWPORT"
fi
