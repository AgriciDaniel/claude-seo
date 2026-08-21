# Install the optional, read-only Xquik research extension on Windows.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$SkillRoot = Join-Path $HOME ".claude/skills"
$SkillTarget = Join-Path $SkillRoot "seo-xquik"
$SettingsJson = Join-Path $HOME ".claude/settings.json"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3 is required."
}
if (-not (Test-Path (Join-Path $SkillRoot "seo"))) {
    throw "Claude SEO is not installed. Install the base plugin first."
}
if (-not (Test-Path (Join-Path $SkillRoot "seo/scripts/url_safety.py"))) {
    throw "Claude SEO URL safety support is missing. Update the base plugin first."
}

$SkillSource = Join-Path $SourceDir "skills/seo-xquik/SKILL.md"
$ScriptSource = Join-Path $SourceDir "scripts/xquik_research.py"
if (-not (Test-Path $SkillSource) -or -not (Test-Path $ScriptSource)) {
    throw "Xquik extension source is incomplete."
}

$SecureKey = Read-Host "Xquik API key" -AsSecureString
$Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
try {
    $PlainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    if (-not $PlainKey) { throw "No API key provided." }

    $env:XQUIK_INSTALL_API_KEY = $PlainKey
    $MergeScript = @'
import json
import os
import sys
import tempfile

settings_path = sys.argv[1]
api_key = os.environ.pop("XQUIK_INSTALL_API_KEY")
settings = {}
if os.path.exists(settings_path):
    with open(settings_path, encoding="utf-8-sig") as handle:
        settings = json.load(handle)
    if not isinstance(settings, dict):
        raise ValueError("settings.json must contain a JSON object")
    if "env" in settings and not isinstance(settings["env"], dict):
        raise ValueError("settings.json env must contain a JSON object")
settings.setdefault("env", {})["X_TWITTER_SCRAPER_API_KEY"] = api_key

parent = os.path.dirname(settings_path) or "."
os.makedirs(parent, exist_ok=True)
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
    $MergeScript | python - $SettingsJson

    New-Item -ItemType Directory -Path (Join-Path $SkillTarget "scripts") -Force | Out-Null
    Copy-Item $SkillSource (Join-Path $SkillTarget "SKILL.md") -Force
    Copy-Item $ScriptSource (Join-Path $SkillTarget "scripts/xquik_research.py") -Force
}
finally {
    Remove-Item Env:XQUIK_INSTALL_API_KEY -ErrorAction SilentlyContinue
    if ($Pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
    }
    $PlainKey = $null
}

Write-Host "Installed seo-xquik. Open a new Claude Code session."
Write-Host 'Try: /seo xquik listen "product name"'
