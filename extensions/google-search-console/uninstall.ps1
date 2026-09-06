$ErrorActionPreference = 'Stop'

Write-Host "Removing Google Search Console extension..." -ForegroundColor Cyan

$SkillDir = "$env:USERPROFILE\.claude\skills\seo-gsc-extension"
$SettingsFile = "$env:USERPROFILE\.claude\settings.json"

if (Test-Path $SkillDir) {
    Remove-Item -Recurse -Force $SkillDir
    Write-Host "v Removed skill files" -ForegroundColor Green
}

if (Test-Path $SettingsFile) {
    $settingsContent = Get-Content $SettingsFile -Raw | ConvertFrom-Json
    if ($settingsContent.mcpServers -and $settingsContent.mcpServers.'google-searchconsole-mcp') {
        $settingsContent.mcpServers.PSObject.Properties.Remove('google-searchconsole-mcp')
        $settingsContent | ConvertTo-Json -Depth 10 | Set-Content $SettingsFile -Encoding UTF8
        Write-Host "v Removed MCP server from settings.json" -ForegroundColor Green
    } else {
        Write-Host "  MCP server not found in settings.json (already removed)"
    }
}

Write-Host ""
Write-Host "Note: the OAuth token cache under %USERPROFILE%\.gsc-mcp\tokens\ is left in place." -ForegroundColor Yellow
Write-Host "Remove it manually to fully revoke local access."
Write-Host ""
Write-Host "v Google Search Console extension uninstalled." -ForegroundColor Green
Write-Host "  Core Claude SEO skills are unchanged."
