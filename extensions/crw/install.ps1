# fastCRW Extension Installer for Claude SEO (Windows)
# fastCRW is a Firecrawl-compatible web scraper in a single ~8MB Rust binary.
# Self-host (free, AGPL) or managed cloud at https://fastcrw.com. This extension
# reuses the firecrawl-mcp client and points its base URL at fastCRW.
$ErrorActionPreference = 'Stop'

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "  fastCRW Extension - Installer" -ForegroundColor Cyan
Write-Host "  For Claude SEO" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

$SkillDir = "$env:USERPROFILE\.claude\skills\seo-crw"
$SeoSkillDir = "$env:USERPROFILE\.claude\skills\seo"
$SettingsFile = "$env:USERPROFILE\.claude\settings.json"

# Default to managed cloud; override CRW_API_URL for a self-hosted engine.
$ApiUrl = if ($env:CRW_API_URL) { $env:CRW_API_URL } else { "https://fastcrw.com/api" }

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

# Prompt for API key
Write-Host ""
Write-Host "fastCRW API key required (managed cloud)." -ForegroundColor Yellow
Write-Host "Sign up at: https://fastcrw.com"
Write-Host "Self-host (free, AGPL): set CRW_API_URL to your engine; key may be left empty."
Write-Host "Base URL: $ApiUrl"
Write-Host ""

$apiKey = Read-Host "fastCRW API key (CRW_API_KEY)" -AsSecureString
$apiKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKey))
if ([string]::IsNullOrWhiteSpace($apiKeyPlain)) {
    if ($ApiUrl -eq "https://fastcrw.com/api") {
        Write-Host "x API key cannot be empty for the managed cloud." -ForegroundColor Red
        Write-Host "  For self-host, set CRW_API_URL to your engine and re-run."
        exit 1
    }
    Write-Host "  No key supplied; assuming a self-host engine without auth." -ForegroundColor Yellow
}

# Determine source directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceDir = $null
if (Test-Path "$ScriptDir\skills\seo-crw\SKILL.md") {
    $SourceDir = $ScriptDir
} elseif (Test-Path "$ScriptDir\extensions\crw\skills\seo-crw\SKILL.md") {
    $SourceDir = "$ScriptDir\extensions\crw"
} else {
    Write-Host "x Cannot find extension source files." -ForegroundColor Red
    exit 1
}

# Install skill
Write-Host ""
Write-Host "=> Installing fastCRW skill..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
Copy-Item "$SourceDir\skills\seo-crw\SKILL.md" "$SkillDir\SKILL.md" -Force

# Configure MCP server
Write-Host "=> Configuring MCP server..." -ForegroundColor Yellow
$settingsContent = if (Test-Path $SettingsFile) { Get-Content $SettingsFile -Raw | ConvertFrom-Json } else { @{} }
if (-not $settingsContent.mcpServers) { $settingsContent | Add-Member -NotePropertyName mcpServers -NotePropertyValue @{} -Force }
# fastCRW is Firecrawl API-compatible: reuse firecrawl-mcp, swap base URL.
$mcpEnv = @{ FIRECRAWL_API_URL = $ApiUrl }
if (-not [string]::IsNullOrWhiteSpace($apiKeyPlain)) { $mcpEnv.FIRECRAWL_API_KEY = $apiKeyPlain }
$settingsContent.mcpServers | Add-Member -NotePropertyName 'crw-mcp' -NotePropertyValue @{
    command = 'npx'
    args = @('-y', 'firecrawl-mcp@3.11.0')
    env = $mcpEnv
} -Force
$settingsContent | ConvertTo-Json -Depth 10 | Set-Content $SettingsFile -Encoding UTF8
# Restrict the credential-bearing settings file to the current user only.
try {
    icacls $SettingsFile /inheritance:r /grant:r "${env:USERNAME}:F" | Out-Null
} catch {
    Write-Host "  Note: could not restrict settings.json ACL; review manually." -ForegroundColor Yellow
}
Write-Host "  v MCP server configured" -ForegroundColor Green

# Pre-warm
Write-Host "=> Pre-downloading firecrawl-mcp client..." -ForegroundColor Yellow
npx -y firecrawl-mcp@3.11.0 --help 2>$null | Out-Null

Write-Host ""
Write-Host "v fastCRW extension installed!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage:"
Write-Host "  /seo crw crawl https://example.com"
Write-Host "  /seo crw map https://example.com"
Write-Host "  /seo crw scrape https://example.com/page"
