# Remove only the optional Xquik skill and its Claude Code environment key.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$SkillTarget = Join-Path $HOME ".claude/skills/seo-xquik"
$SettingsJson = Join-Path $HOME ".claude/settings.json"

if (Test-Path $SettingsJson) {
    $UpdateScript = @'
import json
import os
import sys
import tempfile

settings_path = sys.argv[1]
with open(settings_path, encoding="utf-8-sig") as handle:
    settings = json.load(handle)
if not isinstance(settings, dict):
    raise ValueError("settings.json must contain a JSON object")

environment = settings.get("env")
if isinstance(environment, dict) and "X_TWITTER_SCRAPER_API_KEY" in environment:
    environment.pop("X_TWITTER_SCRAPER_API_KEY")
    if not environment:
        settings.pop("env")
    parent = os.path.dirname(settings_path) or "."
    descriptor, temporary = tempfile.mkstemp(dir=parent, prefix=".settings.", suffix=".json")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
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
'@
    $UpdateScript | python - $SettingsJson
}

if (Test-Path $SkillTarget) {
    Remove-Item -Recurse -Force $SkillTarget
}
Write-Host "Removed seo-xquik. Claude SEO core remains installed."
