# Claude SEO: Shopify Crawler Access extension installer (Windows).
#
# Plugin installs already ship the skill (skills/seo-shopify), so nothing is
# copied there. Manual installs (~/.claude/skills/seo) get the skill copied with
# its launcher path rewritten, because they have no ${CLAUDE_PLUGIN_ROOT}.
# No API keys: the crawl credential lives in a project-local .shopify-env. On
# request the installer creates that file from the template, readable by the
# current user only; it never asks for, reads or prints a signature.
$ErrorActionPreference = "Stop"
$SkillDir = Join-Path $HOME ".claude/skills"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallMode = ""
$PluginRoot = ""
if (Test-Path (Join-Path $SkillDir "seo")) {
    $InstallMode = "manual"
} elseif ($env:CLAUDE_PLUGIN_ROOT -and (Test-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT "skills/seo"))) {
    $InstallMode = "plugin"; $PluginRoot = $env:CLAUDE_PLUGIN_ROOT
} else {
    $OwnRoot = Split-Path -Parent (Split-Path -Parent $SourceDir)
    if ((Test-Path (Join-Path $OwnRoot "skills/seo")) -and (Test-Path (Join-Path $OwnRoot ".claude-plugin/plugin.json"))) {
        $InstallMode = "plugin"; $PluginRoot = $OwnRoot
    } else {
        $Cached = Get-ChildItem -Path (Join-Path $HOME ".claude/plugins/cache/*/claude-seo/*/skills/seo") -Directory -ErrorAction SilentlyContinue | Select-Object -Last 1
        if ($Cached) { $InstallMode = "plugin"; $PluginRoot = Split-Path -Parent (Split-Path -Parent $Cached.FullName) }
    }
}
if (-not $InstallMode) { throw "claude-seo not installed (no plugin install and no ~/.claude/skills/seo)" }
if ($InstallMode -eq "plugin") {
    Write-Host "claude-seo plugin detected: the seo-shopify skill ships with it, nothing to copy."
    if (-not (Test-Path (Join-Path $PluginRoot "skills/seo-shopify/SKILL.md"))) {
        Write-Host "! This plugin version does not ship the seo-shopify skill yet. Update the claude-seo plugin, then /seo shopify will load."
    }
}
if ($InstallMode -eq "manual") {
    $SkillTarget = Join-Path $SkillDir "seo-shopify"
    New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
    # Same rewrite the main installer applies; Claude Code's Bash tool expands $HOME on Windows too.
    $Doc = [System.IO.File]::ReadAllText((Join-Path $SourceDir "skills/seo-shopify/SKILL.md"))
    $Doc = $Doc.Replace('"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo"', '"$HOME/.claude/skills/seo/scripts/claude-seo"')
    [System.IO.File]::WriteAllText((Join-Path $SkillTarget "SKILL.md"), $Doc, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "Installed skill: $SkillTarget"
}
# Optional: start .shopify-env from the template. It will hold a client
# credential, so access is cut down to the current user and an existing file is kept.
$EnvTarget = Join-Path (Get-Location).Path ".shopify-env"
if (Test-Path -LiteralPath $EnvTarget) {
    Write-Host "$EnvTarget already exists; left untouched."
} else {
    Write-Host ""
    Write-Host "The signature belongs in .shopify-env, in the folder you run audits from."
    $Reply = Read-Host "Create $EnvTarget from the template now? [y/N]"
    if ($Reply -match '^[Yy]$') {
        Copy-Item -LiteralPath (Join-Path $SourceDir ".shopify-env.example") -Destination $EnvTarget
        # Windows has no mode bits: drop inherited access and grant only this
        # user, named by SID so a renamed or domain account still matches.
        $Restricted = $false
        try {
            $Sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
            & icacls $EnvTarget /inheritance:r /grant:r "*$($Sid):F" | Out-Null
            $Restricted = ($LASTEXITCODE -eq 0)
        } catch { $Restricted = $false }
        if (-not $Restricted) { Write-Host "! Could not restrict access to $EnvTarget. Restrict it by hand before adding a signature." }
        Write-Host "Created $EnvTarget (placeholders only). Keep it out of git."
    }
}
Write-Host ""
Write-Host "Next: issue a Crawler Access signature in the Shopify admin and write it to .shopify-env"
Write-Host "      in your audit folder (template: $SourceDir\.shopify-env.example)."
if ($InstallMode -eq "plugin") {
    Write-Host "Done. Try: /seo shopify https://shop.example"
} else {
    Write-Host "Done. Restart Claude Code so the skill loads, then try: /seo shopify https://shop.example"
}
