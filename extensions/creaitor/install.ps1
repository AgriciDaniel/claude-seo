# Claude SEO — Creaitor (GEO visibility) extension installer (Windows / PowerShell).
# Mirrors extensions/creaitor/install.sh.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3 is required."
}

$SkillDir = Join-Path $HOME ".claude/skills"
# Remote MCP servers live in the Claude user config, not settings.json.
$ClaudeJson = Join-Path $HOME ".claude.json"
$McpUrl = if ($env:CREAITOR_MCP_URL) { $env:CREAITOR_MCP_URL } else { "https://app.creaitor.ai/api/v2/mcp" }

if (-not (Test-Path (Join-Path $SkillDir "seo"))) {
    throw "claude-seo base plugin not installed."
}

Write-Host "MCP endpoint: $McpUrl"
Write-Host "Important: quit other Claude Code sessions first; they may rewrite ~/.claude.json on exit."
$Secure = Read-Host "Creaitor API token (input hidden)" -AsSecureString
$Token = [System.Net.NetworkCredential]::new("", $Secure).Password
if (-not $Token) { throw "No token provided." }

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillTarget = Join-Path $SkillDir "seo-creaitor"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item -Path (Join-Path $SourceDir "skills/seo-creaitor/SKILL.md") `
          -Destination (Join-Path $SkillTarget "SKILL.md") -Force
Write-Host "Installed skill: $SkillTarget"

# The token travels in the environment, never in argv and never interpolated
# into the Python source (this is a literal here-string: no $ expansion).
$pyScript = @'
import json, os, sys, tempfile
path = sys.argv[1]
token = os.environ["CREAITOR_TOKEN"]
url = os.environ["CREAITOR_MCP_URL"]
data = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as fh:
        raw = fh.read().strip()
    if raw:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            sys.exit(f"{path} is not valid JSON - refusing to overwrite it.")
    if not isinstance(data, dict):
        sys.exit(f"{path} is not a JSON object - refusing to overwrite it.")
servers = data.setdefault("mcpServers", {})
if not isinstance(servers, dict):
    sys.exit(f"mcpServers in {path} is not an object - refusing to overwrite it.")
servers["creaitor-geo"] = {
    "type": "http",
    "url": url,
    "headers": {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
}
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
print(f"Wrote mcpServers.creaitor-geo -> {url} in {path}")
'@

try {
    $env:CREAITOR_TOKEN = $Token
    $env:CREAITOR_MCP_URL = $McpUrl
    $pyScript | python - $ClaudeJson
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update $ClaudeJson (Python exit code $LASTEXITCODE)."
    }
} finally {
    Remove-Item Env:CREAITOR_TOKEN -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Done. Open a new Claude Code session and run /seo creaitor overview <url>."
