# Firecrawl Extension Installer for Claude SEO (Windows)
$ErrorActionPreference = 'Stop'

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "  Firecrawl Extension - Installer" -ForegroundColor Cyan
Write-Host "  For Claude SEO" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

$SkillDir = "$env:USERPROFILE\.claude\skills\seo-firecrawl"
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

# Prompt for API key
Write-Host ""
Write-Host "Firecrawl API key required." -ForegroundColor Yellow
Write-Host "Sign up at: https://www.firecrawl.dev/app/sign-up"
Write-Host "Free tier: 500 credits/month"
Write-Host ""

$apiKey = Read-Host "Firecrawl API key" -AsSecureString
$apiKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($apiKey))
if ([string]::IsNullOrWhiteSpace($apiKeyPlain)) {
    Write-Host "x API key cannot be empty." -ForegroundColor Red
    exit 1
}

# Determine source directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceDir = $null
if (Test-Path "$ScriptDir\skills\seo-firecrawl\SKILL.md") {
    $SourceDir = $ScriptDir
} elseif (Test-Path "$ScriptDir\extensions\firecrawl\skills\seo-firecrawl\SKILL.md") {
    $SourceDir = "$ScriptDir\extensions\firecrawl"
} else {
    Write-Host "x Cannot find extension source files." -ForegroundColor Red
    exit 1
}

# Install skill
Write-Host ""
Write-Host "=> Installing Firecrawl skill..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
Copy-Item "$SourceDir\skills\seo-firecrawl\SKILL.md" "$SkillDir\SKILL.md" -Force

# Configure MCP server
Write-Host "=> Configuring MCP server..." -ForegroundColor Yellow
$settingsContent = if (Test-Path $SettingsFile) { Get-Content $SettingsFile -Raw | ConvertFrom-Json } else { @{} }
if (-not $settingsContent.mcpServers) { $settingsContent | Add-Member -NotePropertyName mcpServers -NotePropertyValue @{} -Force }
$settingsContent.mcpServers | Add-Member -NotePropertyName 'firecrawl-mcp' -NotePropertyValue @{
    command = 'npx'
    args = @('-y', 'firecrawl-mcp')
    env = @{ FIRECRAWL_API_KEY = $apiKeyPlain }
} -Force
$settingsContent | ConvertTo-Json -Depth 10 | Set-Content $SettingsFile -Encoding UTF8
Write-Host "  v MCP server configured" -ForegroundColor Green

# Pre-warm
Write-Host "=> Pre-downloading firecrawl-mcp..." -ForegroundColor Yellow
npx -y firecrawl-mcp --help 2>$null | Out-Null

Write-Host ""
Write-Host "v Firecrawl extension installed!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage:"
Write-Host "  /seo firecrawl crawl https://example.com"
Write-Host "  /seo firecrawl map https://example.com"
Write-Host "  /seo firecrawl scrape https://example.com/page"
