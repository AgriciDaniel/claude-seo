# Claude SEO — MentionAgent extension installer (Windows / PowerShell).
# Mirrors extensions/mentionagent/install.sh.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Test-Cmd($name) {
    $null = Get-Command $name -ErrorAction SilentlyContinue
    return $?
}


$SkillDir = Join-Path $HOME ".claude/skills"
# MCP servers live in ~/.claude.json (the file `claude mcp add` writes).
# NOT ~/.claude/settings.json - `mcpServers` is not a key Claude Code reads
# there, so entries written to settings.json silently never load.
$McpConfigJson = Join-Path $HOME ".claude.json"

if (-not (Test-Path (Join-Path $SkillDir "seo"))) {
    throw "claude-seo base plugin not installed."
}

$Token = Read-Host "MentionAgent API key (ma_live_...)" -AsSecureString
$Plain = [System.Net.NetworkCredential]::new("", $Token).Password
if (-not $Plain) { throw "No key provided." }

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillTarget = Join-Path $SkillDir "seo-mentionagent"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item -Path (Join-Path $SourceDir "skills/seo-mentionagent/SKILL.md") `
          -Destination (Join-Path $SkillTarget "SKILL.md") -Force
Write-Host "✓ Installed skill: $SkillTarget"


# Merge ~/.claude.json.
$settingsContent = if (Test-Path $McpConfigJson) { Get-Content $McpConfigJson -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
if (-not $settingsContent.mcpServers) { $settingsContent | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force }
$settingsContent.mcpServers | Add-Member -NotePropertyName 'mentionagent' -NotePropertyValue @{
    type = 'http'
    url = 'https://mentionagent.ai/mcp'
    headers = @{ Authorization = "Bearer $Plain" }
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
Write-Host "Wrote mcpServers.mentionagent to $McpConfigJson"

Write-Host ""
Write-Host "Done. Open a new Claude Code session and run /seo mentionagent status."
