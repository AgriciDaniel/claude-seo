#!/usr/bin/env bash
set -euo pipefail

main() {
    local skill_target="${HOME}/.claude/skills/seo-xquik"
    local settings_json="${HOME}/.claude/settings.json"

    command -v python3 >/dev/null 2>&1 || {
        echo "Python 3 is required." >&2
        exit 1
    }

    if [ -f "${settings_json}" ]; then
        python3 - "${settings_json}" <<'PY'
import json
import os
import sys
import tempfile

settings_path = sys.argv[1]
with open(settings_path, encoding="utf-8") as handle:
    settings = json.load(handle)
if not isinstance(settings, dict):
    raise ValueError("settings.json must contain a JSON object")

environment = settings.get("env")
if isinstance(environment, dict) and "X_TWITTER_SCRAPER_API_KEY" in environment:
    environment.pop("X_TWITTER_SCRAPER_API_KEY")
    if not environment:
        settings.pop("env")
    parent = os.path.dirname(settings_path) or "."
    descriptor, temporary = tempfile.mkstemp(
        dir=parent,
        prefix=".settings.",
        suffix=".json",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, settings_path)
    except Exception:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
PY
    fi

    if [ -d "${skill_target}" ]; then
        rm -rf "${skill_target}"
    fi
    echo "Removed seo-xquik. Claude SEO core remains installed."
}

main "$@"
