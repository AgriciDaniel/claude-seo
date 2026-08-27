#!/usr/bin/env bash
set -euo pipefail

# Install the optional, read-only Xquik research extension.
main() {
    local skill_root="${HOME}/.claude/skills"
    local skill_target="${skill_root}/seo-xquik"
    local settings_json="${HOME}/.claude/settings.json"
    local source_dir

    command -v python3 >/dev/null 2>&1 || {
        echo "Python 3 is required." >&2
        exit 1
    }
    if [ ! -d "${skill_root}/seo" ]; then
        echo "Claude SEO is not installed. Install the base plugin first." >&2
        exit 1
    fi
    if [ ! -f "${skill_root}/seo/scripts/url_safety.py" ]; then
        echo "Claude SEO URL safety support is missing. Update the base plugin first." >&2
        exit 1
    fi

    source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
    for source_file in \
        "${source_dir}/skills/seo-xquik/SKILL.md" \
        "${source_dir}/scripts/xquik_research.py"; do
        if [ ! -f "${source_file}" ]; then
            echo "Xquik extension source is incomplete: ${source_file}" >&2
            exit 1
        fi
    done

    read -rsp "Xquik API key: " XQUIK_INSTALL_API_KEY
    echo
    if [ -z "${XQUIK_INSTALL_API_KEY}" ]; then
        echo "No API key provided." >&2
        exit 1
    fi
    export XQUIK_INSTALL_API_KEY
    trap 'unset XQUIK_INSTALL_API_KEY' EXIT

    # Validate existing settings before copying files. Invalid JSON is preserved.
    python3 - "${settings_json}" <<'PY'
import json
import os
import sys

settings_path = sys.argv[1]
if os.path.exists(settings_path):
    with open(settings_path, encoding="utf-8") as handle:
        settings = json.load(handle)
    if not isinstance(settings, dict):
        raise ValueError("settings.json must contain a JSON object")
    if "env" in settings and not isinstance(settings["env"], dict):
        raise ValueError("settings.json env must contain a JSON object")
PY

    mkdir -p "${skill_target}/scripts"
    cp "${source_dir}/skills/seo-xquik/SKILL.md" "${skill_target}/SKILL.md"
    cp "${source_dir}/scripts/xquik_research.py" "${skill_target}/scripts/xquik_research.py"
    chmod 0755 "${skill_target}/scripts/xquik_research.py"

    # Pass the credential through the process environment, never Python source or argv.
    python3 - "${settings_json}" <<'PY'
import json
import os
import sys
import tempfile

settings_path = sys.argv[1]
api_key = os.environ.pop("XQUIK_INSTALL_API_KEY")
settings = {}
if os.path.exists(settings_path):
    with open(settings_path, encoding="utf-8") as handle:
        settings = json.load(handle)
settings.setdefault("env", {})["X_TWITTER_SCRAPER_API_KEY"] = api_key

parent = os.path.dirname(settings_path) or "."
os.makedirs(parent, exist_ok=True)
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

    unset XQUIK_INSTALL_API_KEY
    trap - EXIT
    echo "Installed seo-xquik. Open a new Claude Code session."
    echo "Try: /seo xquik listen \"product name\""
}

main "$@"
