# DataForSEO Extension Installer for Claude SEO (Windows)
# PowerShell installation script

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "|   DataForSEO Extension - Installer   |" -ForegroundColor Cyan
Write-Host "|   For Claude SEO                     |" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
$SeoSkillDir = "$env:USERPROFILE\.claude\skills\seo"
if (-not (Test-Path $SeoSkillDir)) {
    Write-Host "[X] Claude SEO is not installed." -ForegroundColor Red
    Write-Host "  Install it first: irm https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.ps1 | iex"
    exit 1
}
Write-Host "[OK] Claude SEO detected" -ForegroundColor Green

$nodeCmd = Get-Command -Name node -ErrorAction SilentlyContinue
if ($null -eq $nodeCmd) {
    Write-Host "[X] Node.js is required but not installed." -ForegroundColor Red
    Write-Host "  Install Node.js 20+: https://nodejs.org/"
    exit 1
}

$nodeVersion = (node -v) -replace 'v','' -split '\.' | Select-Object -First 1
if ([int]$nodeVersion -lt 20) {
    Write-Host "[X] Node.js 20+ required (found v$nodeVersion)." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Node.js $(node -v) detected" -ForegroundColor Green

$npxCmd = Get-Command -Name npx -ErrorAction SilentlyContinue
if ($null -eq $npxCmd) {
    Write-Host "[X] npx is required but not found (comes with npm)." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] npx detected" -ForegroundColor Green

# Prompt for credentials
Write-Host ""
Write-Host "DataForSEO API credentials required." -ForegroundColor Yellow
Write-Host "Sign up at: https://app.dataforseo.com/register"
Write-Host ""

$DfseUsername = Read-Host "DataForSEO username (email)"
if ([string]::IsNullOrEmpty($DfseUsername)) {
    Write-Host "[X] Username cannot be empty." -ForegroundColor Red
    exit 1
}

$DfsePasswordSecure = Read-Host "DataForSEO password" -AsSecureString
$DfsePassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($DfsePasswordSecure)
)
if ([string]::IsNullOrEmpty($DfsePassword)) {
    Write-Host "[X] Password cannot be empty." -ForegroundColor Red
    exit 1
}

# Determine source directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path "$ScriptDir\skills\seo-dataforseo\SKILL.md") {
    $SourceDir = $ScriptDir
} elseif (Test-Path "$ScriptDir\extensions\dataforseo\skills\seo-dataforseo\SKILL.md") {
    $SourceDir = "$ScriptDir\extensions\dataforseo"
} else {
    Write-Host "[X] Cannot find extension source files." -ForegroundColor Red
    Write-Host "  Run this script from the claude-seo repo."
    exit 1
}

# Set paths
$SkillDir = "$env:USERPROFILE\.claude\skills\seo-dataforseo"
$AgentDir = "$env:USERPROFILE\.claude\agents"
# MCP servers live in ~/.claude.json (the file `claude mcp add` writes).
# NOT ~/.claude/settings.json - `mcpServers` is not a key Claude Code reads
# there, so entries written to settings.json silently never load.
$McpConfigFile = "$env:USERPROFILE\.claude.json"
$FieldConfigPath = "$SeoSkillDir\dataforseo-field-config.json"

# Install skill
Write-Host ""
Write-Host "-> Installing DataForSEO skill..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
Copy-Item -Force "$SourceDir\skills\seo-dataforseo\SKILL.md" "$SkillDir\SKILL.md"

# Install agent
Write-Host "-> Installing DataForSEO agent..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $AgentDir | Out-Null
Copy-Item -Force "$SourceDir\agents\seo-dataforseo.md" "$AgentDir\seo-dataforseo.md"

# Install field config
Write-Host "-> Installing field config..." -ForegroundColor Yellow
Copy-Item -Force "$SourceDir\field-config.json" $FieldConfigPath

# Merge MCP config into ~/.claude.json
Write-Host "-> Configuring MCP server..." -ForegroundColor Yellow

$settingsContent = if (Test-Path $McpConfigFile) { Get-Content $McpConfigFile -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
if (-not $settingsContent.mcpServers) { $settingsContent | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force }
$settingsContent.mcpServers | Add-Member -NotePropertyName 'dataforseo' -NotePropertyValue @{
    command = 'npx'
    args = @('-y', 'dataforseo-mcp-server@2.8.10')
    env = @{
        DATAFORSEO_USERNAME = $DfseUsername
        DATAFORSEO_PASSWORD = $DfsePassword
        ENABLED_MODULES = 'SERP,KEYWORDS_DATA,ONPAGE,DATAFORSEO_LABS,BACKLINKS,DOMAIN_ANALYTICS,BUSINESS_DATA,CONTENT_ANALYSIS,AI_OPTIMIZATION'
        FIELD_CONFIG_PATH = $FieldConfigPath
    }
} -Force
# Write atomically: stage to a temp file in the same directory, then swap
# it into place, so a crash mid-write never leaves ~/.claude.json truncated
# or half-written (it is shared with Claude Code and other installers).
# -Depth 100 (not the ConvertTo-Json default of 2) so an existing
# ~/.claude.json with deeply nested config round-trips intact.
$TempConfigFile = Join-Path (Split-Path -Parent $McpConfigFile) ".claude.json.$([guid]::NewGuid().ToString('N')).tmp"
$jsonText = $settingsContent | ConvertTo-Json -Depth 100
# Write without a byte-order mark: on Windows PowerShell 5.1, Set-Content -Encoding UTF8
# emits a BOM and Node's JSON.parse rejects it, which would make ~/.claude.json unreadable.
[System.IO.File]::WriteAllText($TempConfigFile, $jsonText, (New-Object System.Text.UTF8Encoding $false))
Move-Item -Path $TempConfigFile -Destination $McpConfigFile -Force
# Restrict the credential-bearing settings file to the current user only.
try {
    icacls $McpConfigFile /inheritance:r /grant:r "${env:USERNAME}:F" | Out-Null
} catch {
    Write-Host "  Note: could not restrict ~/.claude.json ACL; review manually." -ForegroundColor Yellow
}
Write-Host "  [OK] MCP server configured in ~/.claude.json" -ForegroundColor Green

# Pre-warm npx package
Write-Host "-> Pre-downloading dataforseo-mcp-server..." -ForegroundColor Yellow
try {
    & npx -y dataforseo-mcp-server@2.8.10 --help 2>&1 | Out-Null
} catch {
    # Ignore errors from pre-warm
}

Write-Host ""
Write-Host "[OK] DataForSEO extension installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  1. Start Claude Code:  claude"
Write-Host "  2. Run commands:"
Write-Host "     /seo dataforseo serp best coffee shops"
Write-Host "     /seo dataforseo keywords seo tools"
Write-Host "     /seo dataforseo backlinks example.com"
Write-Host "     /seo dataforseo ai-mentions your brand"
Write-Host ""
Write-Host "All 23 commands: see extensions\dataforseo\README.md"
Write-Host "To uninstall: .\extensions\dataforseo\uninstall.ps1"
