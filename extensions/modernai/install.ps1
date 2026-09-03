# Claude SEO: Modern AI Extension Installer (Windows)
#
# No API key needed. The endpoint is free/anonymous up to a rolling rate
# ceiling.

$ErrorActionPreference = "Stop"

$ExtensionName = "modernai"
$SkillDir = Join-Path $HOME ".claude\skills\seo-$ExtensionName"

Write-Host "Claude SEO: Modern AI Extension"
Write-Host "=================================="
Write-Host ""

$ClaudeSkillsDir = Join-Path $HOME ".claude\skills"
if (-not (Test-Path $ClaudeSkillsDir)) {
    Write-Error "ERROR: $ClaudeSkillsDir not found. Install the base claude-seo package first."
    exit 1
}

New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Copy-Item -Path (Join-Path $ScriptDir "skills\seo-modernai\SKILL.md") -Destination (Join-Path $SkillDir "SKILL.md") -Force

Write-Host "Installed: $SkillDir\SKILL.md"
Write-Host ""
Write-Host "No API key required. This extension queries Modern AI's free, gated"
Write-Host "known-entity lookup endpoint directly (anonymous access, rate-limited"
Write-Host "per a published anti-scrape policy)."
Write-Host ""
Write-Host 'Usage: "/seo modernai brandname"'
