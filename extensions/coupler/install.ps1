# Claude SEO - Coupler.io extension installer (Windows / PowerShell).
# Mirrors extensions/coupler/install.sh.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$SkillDir = Join-Path $HOME ".claude/skills"
# MCP servers live in ~/.claude.json (the file `claude mcp add` writes).
# NOT ~/.claude/settings.json - `mcpServers` is not a key Claude Code reads
# there, so entries written to settings.json silently never load.
$McpConfigJson = Join-Path $HOME ".claude.json"

if (-not (Test-Path (Join-Path $SkillDir "seo"))) {
    throw "claude-seo base plugin not installed."
}

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillTarget = Join-Path $SkillDir "seo-coupler"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item -Path (Join-Path $SourceDir "skills/seo-coupler/SKILL.md") `
          -Destination (Join-Path $SkillTarget "SKILL.md") -Force
Write-Host "[OK] Installed skill: $SkillTarget"

# Merge ~/.claude.json. No API key: the hosted server uses OAuth.
$settingsContent = if (Test-Path $McpConfigJson) { Get-Content $McpConfigJson -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
if (-not $settingsContent.mcpServers) { $settingsContent | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force }
$settingsContent.mcpServers | Add-Member -NotePropertyName 'coupler-io' -NotePropertyValue @{
    type = 'http'
    url = 'https://mcp.coupler.io/mcp'
} -Force
# Write atomically: stage to a temp file in the same directory, then swap
# it into place, so a crash mid-write never leaves ~/.claude.json truncated
# or half-written (it is shared with Claude Code and other installers).
# -Depth 100 (not the ConvertTo-Json default of 2) so an existing
# ~/.claude.json with deeply nested config round-trips intact.
$TempConfigJson = Join-Path (Split-Path -Parent $McpConfigJson) ".claude.json.$([guid]::NewGuid().ToString('N')).tmp"
$jsonText = $settingsContent | ConvertTo-Json -Depth 100
# Write without a byte-order mark: on Windows PowerShell 5.1, Set-Content -Encoding UTF8
# emits a BOM and Node's JSON.parse rejects it, which would make ~/.claude.json unreadable.
[System.IO.File]::WriteAllText($TempConfigJson, $jsonText, (New-Object System.Text.UTF8Encoding $false))
Move-Item -Path $TempConfigJson -Destination $McpConfigJson -Force
Write-Host "Wrote mcpServers.coupler-io to $McpConfigJson"

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  1. In Coupler.io, create and run a data flow with Claude as the destination."
Write-Host "  2. Open a new Claude Code session, run /mcp, select coupler-io and choose Authenticate."
Write-Host "  3. Run: /seo coupler sources"
