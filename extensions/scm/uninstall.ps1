$ErrorActionPreference = 'Stop'

Write-Host "Removing SEO Content Machine extension..." -ForegroundColor Yellow

$SkillDir = "$env:USERPROFILE\.claude\skills\seo-scm"
$McpConfigFile = "$env:USERPROFILE\.claude.json"

if (Test-Path $SkillDir) {
    Remove-Item -Recurse -Force $SkillDir
    Write-Host "v Removed skill files" -ForegroundColor Green
}

if (Test-Path $McpConfigFile) {
    $settings = Get-Content $McpConfigFile -Raw | ConvertFrom-Json
    $entry = $settings.mcpServers.scm
    if ($entry -and ($entry.args | Where-Object { "$_" -like 'seo-content-machine-mcp*' })) {
        $settings.mcpServers.PSObject.Properties.Remove('scm')
        $TempConfigFile = Join-Path (Split-Path -Parent $McpConfigFile) ".claude.json.$([guid]::NewGuid().ToString('N')).tmp"
        $jsonText = $settings | ConvertTo-Json -Depth 100
        [System.IO.File]::WriteAllText($TempConfigFile, $jsonText, (New-Object System.Text.UTF8Encoding $false))
        Move-Item -Path $TempConfigFile -Destination $McpConfigFile -Force
        Write-Host "v Removed MCP server from ~/.claude.json" -ForegroundColor Green
    } else {
        Write-Host '  No "scm" MCP server from this extension in ~/.claude.json; any other "scm" entry is left alone'
    }
}

Write-Host ""
Write-Host "v SEO Content Machine extension uninstalled." -ForegroundColor Green
Write-Host "  Core Claude SEO skills are unchanged."
