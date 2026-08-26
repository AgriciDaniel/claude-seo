# Claude SEO — Ahrefs extension installer (Windows / PowerShell).
# Mirrors extensions/ahrefs/install.sh.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Test-Cmd($name) {
    $null = Get-Command $name -ErrorAction SilentlyContinue
    return $?
}

if (-not (Test-Cmd python)) { throw "Python 3 is required." }
if (-not (Test-Cmd npx))    { throw "Node 18+ / npx is required." }

$SkillDir = Join-Path $HOME ".claude/skills"
# MCP servers live in ~/.claude.json (the file `claude mcp add` writes).
# NOT ~/.claude/settings.json - `mcpServers` is not a key Claude Code reads
# there, so entries written to settings.json silently never load.
$McpConfigJson = Join-Path $HOME ".claude.json"

if (-not (Test-Path (Join-Path $SkillDir "seo"))) {
    throw "claude-seo base plugin not installed."
}

$Token = Read-Host "Ahrefs API token" -AsSecureString
$Plain = [System.Net.NetworkCredential]::new("", $Token).Password
if (-not $Plain) { throw "No token provided." }

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillTarget = Join-Path $SkillDir "seo-ahrefs"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item -Path (Join-Path $SourceDir "skills/seo-ahrefs/SKILL.md") `
          -Destination (Join-Path $SkillTarget "SKILL.md") -Force
Write-Host "✓ Installed skill: $SkillTarget"

# Pre-warm.
& npx --yes --package=@ahrefs/mcp@0.0.11 mcp --help *> $null

# Merge ~/.claude.json.
$pyScript = @"
import json, os, sys, tempfile
path, token = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    try:
        data = json.load(open(path))
    except Exception:
        data = {}
data.setdefault('mcpServers', {})['ahrefs'] = {
    'command': 'npx',
    'args': ['--yes', '--package=@ahrefs/mcp@0.0.11', 'mcp'],
    'env': {'AHREFS_API_TOKEN': token},
}
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.', prefix='.settings.', suffix='.json')
with os.fdopen(fd, 'w') as fh:
    json.dump(data, fh, indent=2)
os.replace(tmp, path)
print(f'Wrote mcpServers.ahrefs to {path}')
"@
$pyScript | python - $McpConfigJson $Plain

Write-Host ""
Write-Host "Done. Open a new Claude Code session and run /seo ahrefs metrics <url>."
