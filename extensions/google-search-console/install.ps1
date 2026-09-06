# Google Search Console Extension Installer for Claude SEO (Windows)
$ErrorActionPreference = 'Stop'

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Google Search Console Extension - Installer" -ForegroundColor Cyan
Write-Host "  For Claude SEO" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

$SkillDir = "$env:USERPROFILE\.claude\skills\seo-gsc-extension"
$SeoSkillDir = "$env:USERPROFILE\.claude\skills\seo"
$SettingsFile = "$env:USERPROFILE\.claude\settings.json"

# Check prerequisites
if (-not (Test-Path $SeoSkillDir)) {
    Write-Host "x Claude SEO is not installed." -ForegroundColor Red
    Write-Host "  Install it first: irm https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.ps1 | iex"
    exit 1
}
Write-Host "v Claude SEO detected" -ForegroundColor Green

$nodeVersion = (node -v 2>$null) -replace 'v',''
if (-not $nodeVersion) {
    Write-Host "x Node.js is required but not installed." -ForegroundColor Red
    exit 1
}
$major = [int]($nodeVersion -split '\.')[0]
if ($major -lt 20) {
    Write-Host "x Node.js 20+ required (found v$nodeVersion)." -ForegroundColor Red
    exit 1
}
Write-Host "v Node.js v$nodeVersion detected" -ForegroundColor Green

Write-Host ""
Write-Host "No API key needed. google-searchconsole-mcp ships with built-in" -ForegroundColor Yellow
Write-Host "OAuth credentials; the first tool call opens a browser window for"
Write-Host "you to sign in and grant read-only Search Console access."
Write-Host ""

# Determine source directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceDir = $null
if (Test-Path "$ScriptDir\skills\seo-gsc-extension\SKILL.md") {
    $SourceDir = $ScriptDir
} elseif (Test-Path "$ScriptDir\extensions\google-search-console\skills\seo-gsc-extension\SKILL.md") {
    $SourceDir = "$ScriptDir\extensions\google-search-console"
} else {
    Write-Host "x Cannot find extension source files." -ForegroundColor Red
    exit 1
}

# Install skill
Write-Host "=> Installing Google Search Console skill..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
Copy-Item "$SourceDir\skills\seo-gsc-extension\SKILL.md" "$SkillDir\SKILL.md" -Force

# Configure MCP server
Write-Host "=> Configuring MCP server..." -ForegroundColor Yellow
$settingsContent = if (Test-Path $SettingsFile) { Get-Content $SettingsFile -Raw | ConvertFrom-Json } else { @{} }
if (-not $settingsContent.mcpServers) { $settingsContent | Add-Member -NotePropertyName mcpServers -NotePropertyValue @{} -Force }
$settingsContent.mcpServers | Add-Member -NotePropertyName 'google-searchconsole-mcp' -NotePropertyValue @{
    command = 'npx'
    args = @('-y', 'google-searchconsole-mcp@1.0.1')
} -Force
$settingsContent | ConvertTo-Json -Depth 10 | Set-Content $SettingsFile -Encoding UTF8
# Restrict the settings file to the current user only.
try {
    icacls $SettingsFile /inheritance:r /grant:r "${env:USERNAME}:F" | Out-Null
} catch {
    Write-Host "  Note: could not restrict settings.json ACL; review manually." -ForegroundColor Yellow
}
Write-Host "  v MCP server configured" -ForegroundColor Green

# Pre-warm
Write-Host "=> Pre-downloading google-searchconsole-mcp..." -ForegroundColor Yellow
npx -y google-searchconsole-mcp@1.0.1 --help 2>$null | Out-Null

Write-Host ""
Write-Host "v Google Search Console extension installed!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage (first call opens a browser to sign in):"
Write-Host "  /seo gsc sites"
Write-Host "  /seo gsc analytics https://example.com"
Write-Host "  /seo gsc inspect https://example.com/page"
Write-Host "  /seo gsc sitemaps https://example.com"
