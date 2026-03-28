# Claude SEO Installer for Windows
# PowerShell installation script

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "|   Claude SEO - Installer             |" -ForegroundColor Cyan
Write-Host "|   Claude Code SEO Skill              |" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Args,
        [switch]$Quiet
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $hasNativePreference = $null -ne (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue)
    if ($hasNativePreference) {
        $previousNativePreference = $PSNativeCommandUseErrorActionPreference
    }

    try {
        $ErrorActionPreference = 'Continue'
        if ($hasNativePreference) {
            $PSNativeCommandUseErrorActionPreference = $false
        }

        $output = & $Exe @Args 2>&1 | ForEach-Object { $_.ToString() }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
        if ($hasNativePreference) {
            $PSNativeCommandUseErrorActionPreference = $previousNativePreference
        }
    }

    if (-not $Quiet -and $null -ne $output -and $output.Count -gt 0) {
        $output | ForEach-Object { Write-Host $_ }
    }

    return @{ ExitCode = $exitCode; Output = $output }
}

# Helper: symlink in local mode, copy in remote mode
function Install-To {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [bool]$IsLocal = $false
    )

    if ($IsLocal) {
        if (Test-Path $Destination) {
            Remove-Item -Recurse -Force $Destination
        }
        New-Item -ItemType SymbolicLink -Path $Destination -Target $Source | Out-Null
    } else {
        if (Test-Path $Source -PathType Container) {
            New-Item -ItemType Directory -Force -Path $Destination | Out-Null
            Copy-Item -Recurse -Force "$Source\*" $Destination
        } else {
            Copy-Item -Force $Source $Destination
        }
    }
}

# Check prerequisites
if (Get-Command python3 -ErrorAction SilentlyContinue) {
    $pyVer = python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($pyVer) { Write-Host "[+] Python $pyVer detected" -ForegroundColor Green }
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($pyVer) { Write-Host "[+] Python $pyVer detected" -ForegroundColor Green }
} else {
    Write-Host "[!] Python 3 not found. uv can install it automatically if needed." -ForegroundColor Yellow
}

# Set paths
$SkillDir = "$env:USERPROFILE\.claude\skills\seo"
$AgentDir = "$env:USERPROFILE\.claude\agents"
$RepoUrl = "https://github.com/AgriciDaniel/claude-seo"
# Pin to a specific release tag to prevent silent updates from main.
# Override: $env:CLAUDE_SEO_TAG = 'main'; .\install.ps1
$RepoTag = if ($env:CLAUDE_SEO_TAG) { $env:CLAUDE_SEO_TAG } else { 'v1.6.0' }

# Determine source: local repo or GitHub download
# Local mode: auto-detected when install.ps1 is run from within the repo
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$LocalSource = $null

if (Test-Path (Join-Path $ScriptDir 'seo\SKILL.md')) {
    $LocalSource = $ScriptDir
}

# Create directories
New-Item -ItemType Directory -Force -Path $SkillDir | Out-Null
New-Item -ItemType Directory -Force -Path $AgentDir | Out-Null

if ($LocalSource) {
    Write-Host "=> Installing from local source (symlinked): $LocalSource" -ForegroundColor Yellow
    $SourceDir = $LocalSource
} else {
    try {
        git --version | Out-Null
        Write-Host "[+] Git detected" -ForegroundColor Green
    } catch {
        Write-Host "[x] Git is required but not installed." -ForegroundColor Red
        exit 1
    }

    $TempDir = Join-Path $env:TEMP "claude-seo-install"
    if (Test-Path $TempDir) {
        Remove-Item -Recurse -Force $TempDir
    }

    Write-Host ">> Downloading Claude SEO ($RepoTag)..." -ForegroundColor Yellow
    $clone = Invoke-External -Exe 'git' -Args @('clone','--depth','1','--branch',$RepoTag,$RepoUrl,$TempDir) -Quiet
    if ($clone.ExitCode -ne 0) {
        throw "git clone failed. Output:`n$($clone.Output -join "`n")"
    }
    $SourceDir = $TempDir
}

$IsLocal = $null -ne $LocalSource

try {
    # Main skill: install individual items from seo/ into SkillDir
    Write-Host "=> Installing skill files..." -ForegroundColor Yellow
    $skillSource = Join-Path $SourceDir 'seo'
    if (-not (Test-Path $skillSource)) {
        throw "Could not find skill source folder (seo/)."
    }
    Get-ChildItem $skillSource | ForEach-Object {
        Install-To -Source $_.FullName -Destination (Join-Path $SkillDir $_.Name) -IsLocal $IsLocal
    }

    # Sub-skills
    $SkillsPath = Join-Path $SourceDir 'skills'
    if (Test-Path $SkillsPath) {
        Get-ChildItem -Directory $SkillsPath | ForEach-Object {
            $target = "$env:USERPROFILE\.claude\skills\$($_.Name)"
            Install-To -Source $_.FullName -Destination $target -IsLocal $IsLocal
        }
    }

    # Schema, pdf, scripts, hooks -> merged into SkillDir
    foreach ($dirName in @('schema', 'pdf', 'scripts', 'hooks')) {
        $dirPath = Join-Path $SourceDir $dirName
        if (Test-Path $dirPath) {
            Install-To -Source $dirPath -Destination (Join-Path $SkillDir $dirName) -IsLocal $IsLocal
        }
    }

    # Agents
    Write-Host "=> Installing subagents..." -ForegroundColor Yellow
    $AgentsPath = Join-Path $SourceDir 'agents'
    if (Test-Path $AgentsPath) {
        Get-ChildItem $AgentsPath -Filter '*.md' | ForEach-Object {
            Install-To -Source $_.FullName -Destination (Join-Path $AgentDir $_.Name) -IsLocal $IsLocal
        }
    }

    # Extensions (optional add-ons: dataforseo, banana)
    $ExtensionsPath = Join-Path $SourceDir 'extensions'
    if (Test-Path $ExtensionsPath) {
        Write-Host "=> Installing extensions..." -ForegroundColor Yellow
        Get-ChildItem -Directory $ExtensionsPath | ForEach-Object {
            $extName = $_.Name
            $extDir = $_.FullName
            # Extension skills
            $extSkills = Join-Path $extDir 'skills'
            if (Test-Path $extSkills) {
                Get-ChildItem -Directory $extSkills | ForEach-Object {
                    $target = "$env:USERPROFILE\.claude\skills\$($_.Name)"
                    Install-To -Source $_.FullName -Destination $target -IsLocal $IsLocal
                }
            }
            # Extension agents
            $extAgents = Join-Path $extDir 'agents'
            if (Test-Path $extAgents) {
                Get-ChildItem $extAgents -Filter '*.md' | ForEach-Object {
                    Install-To -Source $_.FullName -Destination (Join-Path $AgentDir $_.Name) -IsLocal $IsLocal
                }
            }
            # Extension references
            $extRefs = Join-Path $extDir 'references'
            if (Test-Path $extRefs) {
                $refTarget = Join-Path $SkillDir "extensions\$extName"
                New-Item -ItemType Directory -Force -Path $refTarget | Out-Null
                Install-To -Source $extRefs -Destination (Join-Path $refTarget 'references') -IsLocal $IsLocal
            }
            # Extension scripts
            $extScripts = Join-Path $extDir 'scripts'
            if (Test-Path $extScripts) {
                $scriptTarget = Join-Path $SkillDir "extensions\$extName"
                New-Item -ItemType Directory -Force -Path $scriptTarget | Out-Null
                Install-To -Source $extScripts -Destination (Join-Path $scriptTarget 'scripts') -IsLocal $IsLocal
            }
        }
    }

    # Check for uv (required for running scripts via PEP 723 inline metadata)
    $uvCmd = Get-Command -Name uv -ErrorAction SilentlyContinue
    if ($null -ne $uvCmd) {
        Write-Host "  [+] uv detected -- scripts will auto-resolve dependencies via PEP 723" -ForegroundColor Green
        Write-Host "=> Installing Playwright browsers (optional, for visual analysis)..." -ForegroundColor Yellow
        try {
            $pw = Invoke-External -Exe 'uv' -Args @('run','--with','playwright','python','-m','playwright','install','chromium') -Quiet
            if ($pw.ExitCode -ne 0) {
                throw ($pw.Output -join "`n")
            }
        } catch {
            Write-Host "  [!]  Playwright browser install failed. Visual analysis will use WebFetch fallback." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  [!]  uv not found. Install it: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Yellow
        Write-Host "       Scripts use PEP 723 inline metadata and require 'uv run' to execute." -ForegroundColor Yellow
    }
} catch {
    Write-Host ""
    Write-Host "[x] Installation failed: $($_.Exception.Message)" -ForegroundColor Red
    throw
} finally {
    if (-not $IsLocal -and (Test-Path -ErrorAction SilentlyContinue $TempDir)) {
        Remove-Item -Recurse -Force $TempDir
    }
}

Write-Host ""
Write-Host "[+] Claude SEO installed successfully!" -ForegroundColor Green
if ($IsLocal) {
    Write-Host "  (local mode: changes to source files are reflected immediately)" -ForegroundColor Green
}
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  1. Start Claude Code:  claude"
Write-Host "  2. Run commands:       /seo audit https://example.com"
Write-Host ""
Write-Host "To uninstall: irm https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/uninstall.ps1 | iex" -ForegroundColor Gray
