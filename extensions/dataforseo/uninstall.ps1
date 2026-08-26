# DataForSEO Extension Uninstaller for Claude SEO (Windows)

$ErrorActionPreference = "Stop"

Write-Host "→ Uninstalling DataForSEO extension..." -ForegroundColor Yellow

# Remove skill
if (Test-Path "$env:USERPROFILE\.claude\skills\seo-dataforseo") {
    Remove-Item -Recurse -Force "$env:USERPROFILE\.claude\skills\seo-dataforseo"
}

# Remove agent
$agentFile = "$env:USERPROFILE\.claude\agents\seo-dataforseo.md"
if (Test-Path $agentFile) {
    Remove-Item -Force $agentFile
}

# Remove field config
$fieldConfig = "$env:USERPROFILE\.claude\skills\seo\dataforseo-field-config.json"
if (Test-Path $fieldConfig) {
    Remove-Item -Force $fieldConfig
}

# Remove MCP server entry from ~/.claude.json
$settingsFile = "$env:USERPROFILE\.claude.json"
if (Test-Path $settingsFile) {
    $python = Get-Command -Name python -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        $python = Get-Command -Name py -ErrorAction SilentlyContinue
    }

    if ($null -ne $python) {
        $pyExe = $python.Source
        $pyScript = @"
import json
settings_path = r'$settingsFile'
with open(settings_path, 'r') as f:
    settings = json.load(f)
if 'mcpServers' in settings and 'dataforseo' in settings['mcpServers']:
    del settings['mcpServers']['dataforseo']
    if not settings['mcpServers']:
        del settings['mcpServers']
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    print('  ok')
"@
        $result = & $pyExe -c $pyScript 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Removed dataforseo from ~/.claude.json" -ForegroundColor Green
        } else {
            Write-Host "  ⚠  Could not auto-remove MCP config. Remove 'dataforseo' from ~\.claude.json manually." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ⚠  Python not found. Remove 'dataforseo' from ~\.claude.json manually." -ForegroundColor Yellow
    }
}

Write-Host "✓ DataForSEO extension uninstalled." -ForegroundColor Green
