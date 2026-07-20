# DataForSEO Extension Installer for Claude SEO (Windows)
# PowerShell installation script

$ErrorActionPreference = "Stop"

Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "║   DataForSEO Extension - Installer   ║" -ForegroundColor Cyan
Write-Host "║   For Claude SEO                     ║" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
$SeoSkillDir = "$env:USERPROFILE\.claude\skills\seo"
if (-not (Test-Path $SeoSkillDir)) {
    Write-Host "✗ Claude SEO is not installed." -ForegroundColor Red
    Write-Host "  Install it first: irm https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.ps1 | iex"
    exit 1
}
Write-Host "✓ Claude SEO detected" -ForegroundColor Green

$nodeCmd = Get-Command -Name node -ErrorAction SilentlyContinue
if ($null -eq $nodeCmd) {
    Write-Host "✗ Node.js is required but not installed." -ForegroundColor Red
    Write-Host "  Install Node.js 20+: https://nodejs.org/"
    exit 1
}

$nodeVersion = (node -v) -replace 'v','' -split '\.' | Select-Object -First 1
if ([int]$nodeVersion -lt 20) {
    Write-Host "✗ Node.js 20+ required (found v$nodeVersion)." -ForegroundColor Red
    exit 1
}
Write-Host "✓ Node.js $(node -v) detected" -ForegroundColor Green

$npxCmd = Get-Command -Name npx -ErrorAction SilentlyContinue
if ($null -eq $npxCmd) {
    Write-Host "✗ npx is required but not found (comes with npm)." -ForegroundColor Red
    exit 1
}
Write-Host "✓ npx detected" -ForegroundColor Green

# Prompt for credentials
Write-Host ""
Write-Host "DataForSEO API credentials required." -ForegroundColor Yellow
Write-Host "Sign up at: https://app.dataforseo.com/register"
Write-Host ""

$DfseUsername = Read-Host "DataForSEO username (email)"
if ([string]::IsNullOrEmpty($DfseUsername)) {
    Write-Host "✗ Username cannot be empty." -ForegroundColor Red
    exit 1
}

$DfsePasswordSecure = Read-Host "DataForSEO password" -AsSecureString
$DfsePassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($DfsePasswordSecure)
)
if ([string]::IsNullOrEmpty($DfsePassword)) {
    Write-Host "✗ Password cannot be empty." -ForegroundColor Red
    exit 1
}

# Determine source directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path "$ScriptDir\skills\seo-dataforseo\SKILL.md") {
    $SourceDir = $ScriptDir
} elseif (Test-Path "$ScriptDir\extensions\dataforseo\skills\seo-dataforseo\SKILL.md") {
    $SourceDir = "$ScriptDir\extensions\dataforseo"
} else {
    Write-Host "✗ Cannot find extension source files." -ForegroundColor Red
    Write-Host "  Run this script from the claude-seo repo."
    exit 1
}

# Set paths
$SkillDir = "$env:USERPROFILE\.claude\skills\seo-dataforseo"
$AgentDir = "$env:USERPROFILE\.claude\agents"
$SettingsFile = "$env:USERPROFILE\.claude\settings.json"
$FieldConfigPath = "$SeoSkillDir\dataforseo-field-config.json"

# Install skill
Write-Host ""
Write-Host "→ Installing DataForSEO skill..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
Copy-Item -Force "$SourceDir\skills\seo-dataforseo\SKILL.md" "$SkillDir\SKILL.md"

# Install agent
Write-Host "→ Installing DataForSEO agent..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $AgentDir | Out-Null
Copy-Item -Force "$SourceDir\agents\seo-dataforseo.md" "$AgentDir\seo-dataforseo.md"

# Install field config
Write-Host "→ Installing field config..." -ForegroundColor Yellow
Copy-Item -Force "$SourceDir\field-config.json" $FieldConfigPath

# Merge MCP config into settings.json
Write-Host "→ Configuring MCP server..." -ForegroundColor Yellow

$python = Get-Command -Name python -ErrorAction SilentlyContinue
if ($null -eq $python) {
    $python = Get-Command -Name py -ErrorAction SilentlyContinue
}

if ($null -ne $python) {
    $pyExe = $python.Source
    # Credentials are passed as argv (never interpolated into the source string)
    # and the settings file is written atomically with 0600 permissions.
    $pyScript = @"
import json, os, sys, tempfile
path, username, password, field_config = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
settings = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            settings = json.load(f)
    except json.JSONDecodeError:
        settings = {}
settings.setdefault('mcpServers', {})['dataforseo'] = {
    'command': 'npx',
    'args': ['-y', 'dataforseo-mcp-server@2.8.10'],
    'env': {
        'DATAFORSEO_USERNAME': username,
        'DATAFORSEO_PASSWORD': password,
        'ENABLED_MODULES': 'SERP,KEYWORDS_DATA,ONPAGE,DATAFORSEO_LABS,BACKLINKS,DOMAIN_ANALYTICS,BUSINESS_DATA,CONTENT_ANALYSIS,AI_OPTIMIZATION',
        'FIELD_CONFIG_PATH': field_config,
    },
}
os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.', prefix='.settings.', suffix='.json')
try:
    with os.fdopen(fd, 'w') as f:
        json.dump(settings, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
except Exception:
    if os.path.exists(tmp):
        os.unlink(tmp)
    raise
print('  ok')
"@

    $result = $pyScript | & $pyExe - $SettingsFile $DfseUsername $DfsePassword $FieldConfigPath 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ MCP server configured in settings.json" -ForegroundColor Green
    } else {
        Write-Host "  ⚠  Could not auto-configure MCP server." -ForegroundColor Yellow
        Write-Host "  Add the dataforseo server manually to ~\.claude\settings.json"
    }
} else {
    Write-Host "  ⚠  Python not found. Configure MCP server manually." -ForegroundColor Yellow
    Write-Host "  See: extensions\dataforseo\docs\DATAFORSEO-SETUP.md"
}

# Pre-warm npx package
Write-Host "→ Pre-downloading dataforseo-mcp-server..." -ForegroundColor Yellow
try {
    & npx -y dataforseo-mcp-server@2.8.10 --help 2>&1 | Out-Null
} catch {
    # Ignore errors from pre-warm
}

Write-Host ""
Write-Host "✓ DataForSEO extension installed successfully!" -ForegroundColor Green
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
