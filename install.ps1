# Claude SEO Installer for Windows
# PowerShell installation script

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "|   Claude SEO - Installer             |" -ForegroundColor Cyan
Write-Host "|   Claude Code SEO Skill              |" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Resolve-Python {
    $candidates = @(
        @{ Exe = 'py'; Args = @('-3') },
        @{ Exe = 'python3'; Args = @() },
        @{ Exe = 'python'; Args = @() }
    )

    foreach ($candidate in $candidates) {
        $resolved = Test-PythonCandidate -Exe $candidate.Exe -Args $candidate.Args
        if ($null -ne $resolved) {
            return $resolved
        }
    }

    return $null
}

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

function Test-PythonCandidate {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Args
    )

    $pythonCmd = Get-Command -Name $Exe -ErrorAction SilentlyContinue
    if ($null -eq $pythonCmd) {
        return $null
    }

    $probeCode = 'import sys; print(sys.executable); print(sys.version.split()[0]); raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'
    $probe = Invoke-External -Exe $Exe -Args @($Args + @('-c', $probeCode)) -Quiet
    $probeText = ($probe.Output -join "`n")

    if ($probe.ExitCode -ne 0) {
        return $null
    }

    if ($probeText -match 'Microsoft Store|WindowsApps|App execution alias|was not found') {
        return $null
    }

    return @{ Exe = $Exe; Args = $Args }
}

# Check prerequisites
$python = Resolve-Python
if ($null -eq $python) {
    Write-Host "[x] Python is required but was not found (tried 'py -3', 'python3', and 'python')." -ForegroundColor Red
    exit 1
}

try {
    $pythonVersion = & $python.Exe @($python.Args + @('--version')) 2>&1
    Write-Host "[+] $pythonVersion detected" -ForegroundColor Green
} catch {
    Write-Host "[x] Python is installed but could not be executed." -ForegroundColor Red
    exit 1
}

try {
    git --version | Out-Null
    Write-Host "[+] Git detected" -ForegroundColor Green
} catch {
    Write-Host "[x] Git is required but not installed." -ForegroundColor Red
    exit 1
}

# Set paths
$SkillDir = "$env:USERPROFILE\.claude\skills\seo"
$AgentDir = "$env:USERPROFILE\.claude\agents"
$RepoUrl = "https://github.com/AgriciDaniel/claude-seo"
# Pin to a specific release tag to prevent silent updates from main.
# This default MUST be bumped on every release. CI guard
# (tests/test_manifest_consistency.py) enforces this matches plugin.json.
# Override: $env:CLAUDE_SEO_TAG = 'main'; .\install.ps1
$RepoTag = if ($env:CLAUDE_SEO_TAG) { $env:CLAUDE_SEO_TAG } else { 'v2.2.5' }

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
    Write-Host ">> Downloading Claude SEO ($RepoTag)..." -ForegroundColor Yellow
    $clone = Invoke-External -Exe 'git' -Args @('clone','--depth','1','--branch',$RepoTag,$RepoUrl,$TempDir) -Quiet
    if ($clone.ExitCode -ne 0) {
        throw "git clone failed. Output:`n$($clone.Output -join "`n")"
    }

    # Copy skill files
    Write-Host "=> Installing skill files..." -ForegroundColor Yellow
    $skillSource = Join-Path $TempDir 'skills\seo'
    if (-not (Test-Path $skillSource)) {
        throw "Could not find skill source folder in repo clone."
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

    # Copy deterministic data files consumed by bundled scripts such as
    # seo_updates.py. Keep the repository-relative data\ layout intact.
    $DataPath = "$TempDir\data"
    if (Test-Path $DataPath) {
        $SkillData = "$SkillDir\data"
        New-Item -ItemType Directory -Force -Path $SkillData | Out-Null
        Copy-Item -Recurse -Force "$DataPath\*" $SkillData
    }

    # Copy reference docs
    $PdfPath = "$TempDir\pdf"
    if (Test-Path $PdfPath) {
        $SkillPdf = "$SkillDir\pdf"
        New-Item -ItemType Directory -Force -Path $SkillPdf | Out-Null
        Copy-Item -Recurse -Force "$PdfPath\*" $SkillPdf
    }

    # Copy agents
    Write-Host "=> Installing subagents..." -ForegroundColor Yellow
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

    # Copy the stable launcher used by skill and agent instructions.
    $BinPath = Join-Path $TempDir 'bin'
    $SkillBin = Join-Path $SkillDir 'bin'
    if (Test-Path (Join-Path $BinPath 'claude-seo')) {
        New-Item -ItemType Directory -Force -Path $SkillBin | Out-Null
        Copy-Item -Force (Join-Path $BinPath 'claude-seo') (Join-Path $SkillBin 'claude-seo')
    }

    # Copy hooks
    Write-Host "  Note: hook enforcement requires plugin install; manual hook copy is best-effort." -ForegroundColor Yellow
    $HooksPath = "$TempDir\hooks"
    if (Test-Path $HooksPath) {
        $SkillHooks = "$SkillDir\hooks"
        New-Item -ItemType Directory -Force -Path $SkillHooks | Out-Null
        Copy-Item -Recurse -Force "$HooksPath\*" $SkillHooks
    }

    # Copy extensions (optional add-ons: dataforseo, banana)
    $ExtensionsPath = Join-Path $TempDir 'extensions'
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
                    New-Item -ItemType Directory -Force -Path $target | Out-Null
                    Copy-Item -Recurse -Force "$($_.FullName)\*" $target
                }
            }
            # Extension agents
            $extAgents = Join-Path $extDir 'agents'
            if (Test-Path $extAgents) {
                Copy-Item -Force (Join-Path $extAgents '*.md') $AgentDir -ErrorAction SilentlyContinue
            }
            # Extension references
            $extRefs = Join-Path $extDir 'references'
            if (Test-Path $extRefs) {
                $refTarget = "$SkillDir\extensions\$extName\references"
                New-Item -ItemType Directory -Force -Path $refTarget | Out-Null
                Copy-Item -Recurse -Force "$extRefs\*" $refTarget
            }
            # Extension scripts
            $extScripts = Join-Path $extDir 'scripts'
            if (Test-Path $extScripts) {
                $scriptTarget = "$SkillDir\extensions\$extName\scripts"
                New-Item -ItemType Directory -Force -Path $scriptTarget | Out-Null
                Copy-Item -Recurse -Force "$extScripts\*" $scriptTarget
            }
        }
    }

    # Copy requirements.txt to skill dir for retry
    $reqFile = Join-Path $TempDir 'requirements.txt'
    $installedReqFile = Join-Path $SkillDir 'requirements.txt'
    if (Test-Path $reqFile) {
        Copy-Item -Force $reqFile $installedReqFile
    }
    $pluginManifest = Join-Path $TempDir '.claude-plugin\plugin.json'
    if (Test-Path $pluginManifest) {
        Copy-Item -Force $pluginManifest (Join-Path $SkillDir 'runtime-plugin.json')
    }

    # Manual installs do not receive plugin bin/ PATH injection. Rewrite only
    # the canonical runtime token in installed Markdown. Claude Code's Bash tool
    # expands $HOME on Windows as well as Unix.
    $manualRunner = '"$HOME/.claude/skills/seo/bin/claude-seo" run'
    $installedDocs = @()
    Get-ChildItem -Path $SkillsPath -Directory | ForEach-Object {
        $sourceRoot = $_.FullName
        $targetRoot = "$env:USERPROFILE\.claude\skills\$($_.Name)"
        $installedDocs += Get-ChildItem -Path $sourceRoot -Recurse -File -Filter '*.md' | ForEach-Object {
            $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\','/')
            Get-Item (Join-Path $targetRoot $relative) -ErrorAction SilentlyContinue
        }
    }
    Get-ChildItem -Path $ExtensionsPath -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $extName = $_.Name
        $extSkills = Join-Path $_.FullName 'skills'
        Get-ChildItem -Path $extSkills -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $sourceRoot = $_.FullName
            $targetRoot = "$env:USERPROFILE\.claude\skills\$($_.Name)"
            $installedDocs += Get-ChildItem -Path $sourceRoot -Recurse -File -Filter '*.md' | ForEach-Object {
                $relative = $_.FullName.Substring($sourceRoot.Length).TrimStart('\','/')
                Get-Item (Join-Path $targetRoot $relative) -ErrorAction SilentlyContinue
            }
        }
        $extRefs = Join-Path $_.FullName 'references'
        if (Test-Path $extRefs) {
            $targetRefs = Join-Path $SkillDir "extensions\$extName\references"
            $installedDocs += Get-ChildItem -Path $extRefs -Recurse -File -Filter '*.md' | ForEach-Object {
                $relative = $_.FullName.Substring($extRefs.Length).TrimStart('\','/')
                Get-Item (Join-Path $targetRefs $relative) -ErrorAction SilentlyContinue
            }
        }
    }
    $agentSources = @()
    $agentSources += Get-ChildItem -Path $AgentsPath -File -Filter '*.md' -ErrorAction SilentlyContinue
    $agentSources += Get-ChildItem -Path $ExtensionsPath -Recurse -File -Filter '*.md' -ErrorAction SilentlyContinue |
        Where-Object { $_.Directory.Name -eq 'agents' }
    $installedDocs += $agentSources | ForEach-Object {
        Get-Item (Join-Path $AgentDir $_.Name) -ErrorAction SilentlyContinue
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $installedDocs | ForEach-Object {
        $text = [System.IO.File]::ReadAllText($_.FullName)
        $manualSetup = '"$HOME/.claude/skills/seo/bin/claude-seo" setup'
        $manualDoctor = '"$HOME/.claude/skills/seo/bin/claude-seo" doctor'
        $updated = $text.Replace('claude-seo run', $manualRunner)
        $updated = $updated.Replace('claude-seo setup', $manualSetup)
        $updated = $updated.Replace('claude-seo doctor', $manualDoctor)
        if ($updated -ne $text) {
            [System.IO.File]::WriteAllText($_.FullName, $updated, $utf8NoBom)
        }
    }

    # Use the same standard-library runtime on Windows. It creates an isolated
    # .venv with Scripts\python.exe and installs Chromium through that interpreter.
    Write-Host "=> Creating isolated Python runtime..." -ForegroundColor Yellow
    $runtimeScript = Join-Path $SkillDir 'scripts\runtime.py'
    $runtime = Invoke-External -Exe $python.Exe -Args @($python.Args + @($runtimeScript,'setup'))
    if ($runtime.ExitCode -ne 0 -and $runtime.ExitCode -ne 10) {
        throw "Core Python runtime setup failed. Installation is incomplete."
    }
    if ($runtime.ExitCode -eq 10) {
        Write-Host "  [!] Core runtime installed, but Chromium setup is incomplete." -ForegroundColor Yellow
    }
} catch {
    Write-Host ""
    Write-Host "[x] Installation failed: $($_.Exception.Message)" -ForegroundColor Red
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
Write-Host "[+] Claude SEO installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  1. Start Claude Code:  claude"
Write-Host "  2. Run commands:       /seo audit https://example.com"
Write-Host ""
Write-Host "Python deps location: $installedReqFile" -ForegroundColor Gray
