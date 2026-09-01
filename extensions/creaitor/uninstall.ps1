# Claude SEO — Creaitor extension uninstaller (Windows / PowerShell).
# Removes the MCP entry first, then the skill. Other Claude config is preserved.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Python = if (Get-Command python3 -ErrorAction SilentlyContinue) {
    (Get-Command python3).Source
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    (Get-Command python).Source
} else {
    throw "Python 3 is required."
}

$SkillDir = Join-Path $HOME ".claude/skills/seo-creaitor"
$ClaudeJson = Join-Path $HOME ".claude.json"

$pyScript = @'
import json, os, sys, tempfile
path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    data = json.load(fh)
if not isinstance(data, dict):
    sys.exit(f"{path} is not a JSON object - leaving it untouched.")
servers = data.get("mcpServers")
if not isinstance(servers, dict) or "creaitor-geo" not in servers:
    raise SystemExit(0)
servers.pop("creaitor-geo")
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)),
                           prefix=".claude.", suffix=".json")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)
except Exception:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise
'@

if (Test-Path $ClaudeJson) {
    $pyScript | & $Python - $ClaudeJson
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update $ClaudeJson (Python exit code $LASTEXITCODE)."
    }
}

# Config validation/removal succeeded, so it is now safe to remove the skill.
if (Test-Path $SkillDir) {
    Remove-Item -Path $SkillDir -Recurse -Force
    Write-Host "Removed $SkillDir"
}

Write-Host "Done. Revoke the token at https://app.creaitor.ai/user/api-tokens if it is no longer needed."
