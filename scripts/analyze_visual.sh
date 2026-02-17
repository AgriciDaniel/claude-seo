#!/usr/bin/env bash
#
# Analyze visual aspects of a web page using agent-browser.
#
# Outputs page snapshots and screenshots at desktop and mobile viewports
# for the seo-visual agent to interpret.
#
# Usage:
#   ./analyze_visual.sh https://example.com
#   ./analyze_visual.sh https://example.com --json

set -euo pipefail

URL=""
JSON_OUT=false

usage() {
  echo "Usage: $0 <url> [--json]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --json|-j) JSON_OUT=true; shift ;;
    -h|--help) usage ;;
    *)         URL="$1"; shift ;;
  esac
done

if [[ -z "$URL" ]]; then
  usage
fi

TMP_DIR=$(mktemp -d)
DESKTOP_SHOT="$TMP_DIR/desktop.png"
MOBILE_SHOT="$TMP_DIR/mobile.png"

# ── Desktop analysis ─────────────────────────────────────────────────────────
echo "=== Desktop Analysis (1920x1080) ==="
agent-browser open "$URL"
agent-browser wait --load networkidle
agent-browser wait 1000
agent-browser resize 1920 1080

echo ""
echo "--- Page elements (interactive) ---"
agent-browser snapshot -i

echo ""
echo "--- Full page text (for above-fold / content analysis) ---"
agent-browser get text body

echo ""
echo "--- Page title ---"
agent-browser get title

echo ""
echo "--- Current URL ---"
agent-browser get url

echo ""
echo "--- Desktop screenshot ---"
agent-browser screenshot "$DESKTOP_SHOT"
echo "Saved: $DESKTOP_SHOT"

agent-browser close

# ── Mobile analysis ──────────────────────────────────────────────────────────
echo ""
echo "=== Mobile Analysis (375x812) ==="
agent-browser open "$URL"
agent-browser wait --load networkidle
agent-browser wait 1000
agent-browser resize 375 812

echo ""
echo "--- Page elements (mobile) ---"
agent-browser snapshot -i

echo ""
echo "--- Mobile screenshot ---"
agent-browser screenshot "$MOBILE_SHOT"
echo "Saved: $MOBILE_SHOT"

agent-browser close

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "=== Analysis complete ==="
echo "Screenshots:"
echo "  Desktop: $DESKTOP_SHOT"
echo "  Mobile:  $MOBILE_SHOT"
echo ""
echo "Review the snapshots above to determine:"
echo "  - H1 visibility above the fold"
echo "  - CTA presence and visibility"
echo "  - Mobile layout and responsiveness"
echo "  - Navigation accessibility on mobile"
echo "  - Touch target sizes (should be 48x48px+)"
echo "  - Horizontal scroll (should not exist on mobile)"
