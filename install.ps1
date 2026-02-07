# Claude SEO Installer for Windows
# PowerShell installation script

$ErrorActionPreference = "Stop"

Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "║   Claude SEO - Installer             ║" -ForegroundColor Cyan
Write-Host "║   Claude Code SEO Skill              ║" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ $pythonVersion detected" -ForegroundColor Green
} catch {
    Write-Host "✗ Python is required but not installed." -ForegroundColor Red
    exit 1
}

try {
    git --version | Out-Null
    Write-Host "✓ Git detected" -ForegroundColor Green
} catch {
    Write-Host "✗ Git is required but not installed." -ForegroundColor Red
    exit 1
}

# Set paths
$SkillDir = "$env:USERPROFILE\.claude\skills\seo"
$AgentDir = "$env:USERPROFILE\.claude\agents"
$RepoUrl = "https://github.com/AgriciDaniel/claude-seo"

# Create directories
New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
New-Item -ItemType Directory -Force -Path $AgentDir | Out-Null

# Clone to temp directory
$TempDir = Join-Path $env:TEMP "claude-seo-install"
if (Test-Path $TempDir) {
    Remove-Item -Recurse -Force $TempDir
}

Write-Host "↓ Downloading Claude SEO..." -ForegroundColor Yellow
git clone --depth 1 $RepoUrl $TempDir 2>$null

# Copy skill files
Write-Host "→ Installing skill files..." -ForegroundColor Yellow
Copy-Item -Recurse -Force "$TempDir\seo\*" $SkillDir

# Copy sub-skills
$SkillsPath = "$TempDir\skills"
if (Test-Path $SkillsPath) {
    Get-ChildItem -Directory $SkillsPath | ForEach-Object {
        $target = "$env:USERPROFILE\.claude\skills\$($_.Name)"
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Copy-Item -Recurse -Force "$($_.FullName)\*" $target
    }
}

# Copy agents
Write-Host "→ Installing subagents..." -ForegroundColor Yellow
Copy-Item -Force "$TempDir\agents\*.md" $AgentDir 2>$null

# Copy shared scripts
$ScriptsPath = "$TempDir\scripts"
if (Test-Path $ScriptsPath) {
    $SkillScripts = "$SkillDir\scripts"
    New-Item -ItemType Directory -Force -Path $SkillScripts | Out-Null
    Copy-Item -Recurse -Force "$ScriptsPath\*" $SkillScripts
}

# Copy hooks
$HooksPath = "$TempDir\hooks"
if (Test-Path $HooksPath) {
    $SkillHooks = "$SkillDir\hooks"
    New-Item -ItemType Directory -Force -Path $SkillHooks | Out-Null
    Copy-Item -Recurse -Force "$HooksPath\*" $SkillHooks
}

# Install Python dependencies
Write-Host "→ Installing Python dependencies..." -ForegroundColor Yellow
try {
    pip install -q -r "$TempDir\requirements.txt" 2>$null
} catch {
    Write-Host "⚠  Could not auto-install Python packages. Run: pip install -r requirements.txt" -ForegroundColor Yellow
}

# Optional: Install Playwright browsers
Write-Host "→ Installing Playwright browsers (optional)..." -ForegroundColor Yellow
try {
    python -m playwright install chromium 2>$null
} catch {
    Write-Host "⚠  Playwright browser install failed. Screenshots won't work." -ForegroundColor Yellow
}

# Cleanup
Remove-Item -Recurse -Force $TempDir

Write-Host ""
Write-Host "✓ Claude SEO installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  1. Start Claude Code:  claude"
Write-Host "  2. Run commands:       /seo audit https://example.com"
