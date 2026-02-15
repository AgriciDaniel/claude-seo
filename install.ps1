# Claude SEO Installer for Windows
# PowerShell installation script

$ErrorActionPreference = "Stop"

Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "║   Claude SEO - Installer             ║" -ForegroundColor Cyan
Write-Host "║   Claude Code SEO Skill              ║" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

function Resolve-Python {
    $pythonCmd = Get-Command -Name python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCmd) {
        return @{ Exe = 'python'; Args = @() }
    }

    $pyCmd = Get-Command -Name py -ErrorAction SilentlyContinue
    if ($null -ne $pyCmd) {
        return @{ Exe = 'py'; Args = @('-3') }
    }

    return $null
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Args,
        [switch]$Quiet
    )

    $output = & $Exe @Args 2>&1
    $exitCode = $LASTEXITCODE

    if (-not $Quiet -and $null -ne $output -and $output.Count -gt 0) {
        $output | ForEach-Object { Write-Host $_ }
    }

    return @{ ExitCode = $exitCode; Output = $output }
}

# Check prerequisites
$python = Resolve-Python
if ($null -eq $python) {
    Write-Host "✗ Python is required but was not found (tried 'python' and 'py')." -ForegroundColor Red
    exit 1
}

try {
    $pythonVersion = & $python.Exe @($python.Args + @('--version')) 2>&1
    Write-Host "✓ $pythonVersion detected" -ForegroundColor Green
} catch {
    Write-Host "✗ Python is installed but could not be executed." -ForegroundColor Red
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

$keepTemp = ($env:CLAUDE_SEO_KEEP_TEMP -eq '1')

try {
    Write-Host "↓ Downloading Claude SEO..." -ForegroundColor Yellow
    $clone = Invoke-External -Exe 'git' -Args @('clone','--depth','1',$RepoUrl,$TempDir) -Quiet
    if ($clone.ExitCode -ne 0) {
        throw "git clone failed. Output:`n$($clone.Output -join "`n")"
    }

    # Copy skill files
    Write-Host "→ Installing skill files..." -ForegroundColor Yellow
    $skillSource = Join-Path $TempDir 'seo'
    if (-not (Test-Path $skillSource)) {
        $skillSource = Join-Path $TempDir 'skills\seo'
    }
    if (-not (Test-Path $skillSource)) {
        throw "Could not find skill source folder in repo clone. Expected '$($TempDir)\\seo' or '$($TempDir)\\skills\\seo'."
    }
    Copy-Item -Recurse -Force (Join-Path $skillSource '*') $SkillDir

# Copy sub-skills
$SkillsPath = "$TempDir\skills"
if (Test-Path $SkillsPath) {
    Get-ChildItem -Directory $SkillsPath | ForEach-Object {
        $target = "$env:USERPROFILE\.claude\skills\$($_.Name)"
        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Copy-Item -Recurse -Force "$($_.FullName)\*" $target
    }
}

# Copy schema templates
$SchemaPath = "$TempDir\schema"
if (Test-Path $SchemaPath) {
    $SkillSchema = "$SkillDir\schema"
    New-Item -ItemType Directory -Force -Path $SkillSchema | Out-Null
    Copy-Item -Recurse -Force "$SchemaPath\*" $SkillSchema
}

# Copy reference docs
$PdfPath = "$TempDir\pdf"
if (Test-Path $PdfPath) {
    $SkillPdf = "$SkillDir\pdf"
    New-Item -ItemType Directory -Force -Path $SkillPdf | Out-Null
    Copy-Item -Recurse -Force "$PdfPath\*" $SkillPdf
}

    # Copy agents
    Write-Host "→ Installing subagents..." -ForegroundColor Yellow
    $AgentsPath = Join-Path $TempDir 'agents'
    if (Test-Path $AgentsPath) {
        Copy-Item -Force (Join-Path $AgentsPath '*.md') $AgentDir -ErrorAction SilentlyContinue
    }

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
    $reqFile = Join-Path $TempDir 'requirements.txt'
    $installedReqFile = Join-Path $SkillDir 'requirements.txt'
    if (Test-Path $reqFile) {
        Copy-Item -Force $reqFile $installedReqFile
        try {
            $pip = Invoke-External -Exe $python.Exe -Args @($python.Args + @('-m','pip','install','-q','-r',$reqFile)) -Quiet
            if ($pip.ExitCode -ne 0) {
                throw ($pip.Output -join "`n")
            }
        } catch {
            Write-Host "⚠  Could not auto-install Python packages." -ForegroundColor Yellow
            Write-Host "   Try: $($python.Exe) $($python.Args -join ' ') -m pip install -r `"$installedReqFile`"" -ForegroundColor Yellow
        }
    } else {
        Write-Host "⚠  No requirements.txt found in the repo; skipping Python dependency install." -ForegroundColor Yellow
    }

    # Optional: Install Playwright browsers
    Write-Host "→ Installing Playwright browsers (optional)..." -ForegroundColor Yellow
    try {
        $pw = Invoke-External -Exe $python.Exe -Args @($python.Args + @('-m','playwright','install','chromium')) -Quiet
        if ($pw.ExitCode -ne 0) {
            throw ($pw.Output -join "`n")
        }
    } catch {
        Write-Host "⚠  Playwright browser install failed. Screenshots won't work." -ForegroundColor Yellow
    }
} catch {
    Write-Host "" 
    Write-Host "✗ Installation failed: $($_.Exception.Message)" -ForegroundColor Red
    if ($keepTemp -and (Test-Path $TempDir)) {
        Write-Host "Temp dir kept at: $TempDir" -ForegroundColor Yellow
    }
    throw
} finally {
    if (-not $keepTemp -and (Test-Path $TempDir)) {
        Remove-Item -Recurse -Force $TempDir
    }
}

Write-Host ""
Write-Host "✓ Claude SEO installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  1. Start Claude Code:  claude"
Write-Host "  2. Run commands:       /seo audit https://example.com"