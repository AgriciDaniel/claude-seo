# Firecrawl Extension Uninstaller for Claude SEO (Windows)
$ErrorActionPreference = 'Stop'

Write-Host "Removing Firecrawl extension..." -ForegroundColor Yellow

$SkillDir = "$env:USERPROFILE\.claude\skills\seo-firecrawl"
$McpConfigFile = "$env:USERPROFILE\.claude.json"

if (Test-Path $SkillDir) {
    Remove-Item -Recurse -Force $SkillDir
    Write-Host "v Removed skill files" -ForegroundColor Green
}

if (Test-Path $McpConfigFile) {
    $settings = Get-Content $McpConfigFile -Raw | ConvertFrom-Json
    if ($settings.mcpServers.'firecrawl-mcp') {
        $settings.mcpServers.PSObject.Properties.Remove('firecrawl-mcp')
        $settings | ConvertTo-Json -Depth 10 | Set-Content $McpConfigFile -Encoding UTF8
        Write-Host "v Removed MCP server from ~/.claude.json" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "v Firecrawl extension uninstalled." -ForegroundColor Green
Write-Host "  Core Claude SEO skills are unchanged."
