$ErrorActionPreference = 'Stop'

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "  SEO Content Machine - Installer" -ForegroundColor Cyan
Write-Host "  For Claude SEO" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

$SkillDir = "$env:USERPROFILE\.claude\skills\seo-scm"
$SeoSkillDir = "$env:USERPROFILE\.claude\skills\seo"
$McpConfigFile = "$env:USERPROFILE\.claude.json"
$ScmMcpPackage = 'seo-content-machine-mcp@1.1.1'

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
if ($major -lt 18) {
    Write-Host "x Node.js 18+ required (found v$nodeVersion)." -ForegroundColor Red
    exit 1
}
Write-Host "v Node.js v$nodeVersion detected" -ForegroundColor Green

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceDir = $null
if (Test-Path "$ScriptDir\skills\seo-scm\SKILL.md") {
    $SourceDir = $ScriptDir
} elseif (Test-Path "$ScriptDir\extensions\scm\skills\seo-scm\SKILL.md") {
    $SourceDir = "$ScriptDir\extensions\scm"
} else {
    Write-Host "x Cannot find extension source files." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=> Installing SCM skill..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
Copy-Item "$SourceDir\skills\seo-scm\SKILL.md" "$SkillDir\SKILL.md" -Force

Write-Host "=> Configuring MCP server (no API key needed, it talks to the SCM app on this machine)..." -ForegroundColor Yellow
$settingsContent = if (Test-Path $McpConfigFile) { Get-Content $McpConfigFile -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
if (-not $settingsContent.mcpServers) { $settingsContent | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) -Force }
if ($settingsContent.mcpServers.PSObject.Properties.Name -contains 'scm') {
    Write-Host '  v An "scm" MCP server is already configured; kept as it is' -ForegroundColor Green
} else {
    $settingsContent.mcpServers | Add-Member -NotePropertyName 'scm' -NotePropertyValue @{
        command = 'npx'
        args = @('-y', $ScmMcpPackage)
    } -Force
    $TempConfigFile = Join-Path (Split-Path -Parent $McpConfigFile) ".claude.json.$([guid]::NewGuid().ToString('N')).tmp"
    $jsonText = $settingsContent | ConvertTo-Json -Depth 100
    [System.IO.File]::WriteAllText($TempConfigFile, $jsonText, (New-Object System.Text.UTF8Encoding $false))
    Move-Item -Path $TempConfigFile -Destination $McpConfigFile -Force
    Write-Host "  v MCP server configured" -ForegroundColor Green
}

Write-Host "=> Pre-downloading $ScmMcpPackage..." -ForegroundColor Yellow
npx --yes --package=$ScmMcpPackage -- node -e '""' 2>$null | Out-Null

Write-Host ""
Write-Host "v SEO Content Machine extension installed!" -ForegroundColor Green
Write-Host ""
Write-Host "SEO Content Machine must be running on this machine."
Write-Host "No SCM yet? 14-day free trial, no card needed:"
Write-Host "  https://seocontentmachine.com/members/signup/trial?utm_source=claude-seo&utm_medium=extension&utm_campaign=claude-seo&utm_content=installer"
Write-Host ""
Write-Host "Usage:"
Write-Host "  /seo cluster plan `"<seed keyword>`""
Write-Host "  /seo scm execute"
Write-Host "  /seo scm status"
