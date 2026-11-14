# Claude SEO: PostHog extension installer (Windows).
#
# Plugin installs already ship the skill (skills/seo-posthog) and the agent
# (agents/seo-posthog.md), so only the MCP server is registered there. Manual
# installs (~/.claude/skills/seo) also get the skill and agent copied. Data
# comes from the PostHog MCP server, so no credential is collected or stored
# here.
$ErrorActionPreference = "Stop"
$SkillDir = Join-Path $HOME ".claude/skills"
$AgentsDir = Join-Path $HOME ".claude/agents"
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
if (-not $InstallMode) { throw "claude-seo base not installed (no plugin install and no ~/.claude/skills/seo)." }
if ($InstallMode -eq "plugin") {
    Write-Host "claude-seo plugin detected: registering the MCP server only."
    if (-not ((Test-Path (Join-Path $PluginRoot "skills/seo-posthog/SKILL.md")) -and (Test-Path (Join-Path $PluginRoot "agents/seo-posthog.md")))) {
        Write-Host "! This plugin version does not ship the seo-posthog skill and agent yet. Update the claude-seo plugin, then /seo posthog will load."
    }
}
if ($InstallMode -eq "manual") {
    # Neither file carries a ${CLAUDE_PLUGIN_ROOT} launcher path, so a plain copy is correct.
    $SkillTarget = Join-Path $SkillDir "seo-posthog"
    New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
    Copy-Item (Join-Path $SourceDir "skills/seo-posthog/SKILL.md") (Join-Path $SkillTarget "SKILL.md") -Force
    Write-Host "Installed skill: $SkillTarget"

    New-Item -ItemType Directory -Path $AgentsDir -Force | Out-Null
    $AgentTarget = Join-Path $AgentsDir "seo-posthog.md"
    Copy-Item (Join-Path $SourceDir "agents/seo-posthog.md") $AgentTarget -Force
    Write-Host "Installed agent: $AgentTarget"
}

if (Get-Command claude -ErrorAction SilentlyContinue) {
    Write-Host ""
    $Reply = Read-Host "Register the PostHog MCP server now (https://mcp.posthog.com/mcp)? [y/N]"
    if ($Reply -match '^[Yy]$') {
        & claude mcp add --transport http posthog https://mcp.posthog.com/mcp
        # A native command's non-zero exit does not throw, even with Stop.
        if ($LASTEXITCODE -eq 0) {
            Write-Host "MCP server registered. Run /mcp in Claude Code to authenticate."
        } else {
            Write-Host "! Could not register the MCP server. See extensions/posthog/docs/POSTHOG-SETUP.md"
        }
    }
} else {
    Write-Host ""
    Write-Host "! 'claude' CLI not found. Register the MCP server manually:"
    Write-Host "  claude mcp add --transport http posthog https://mcp.posthog.com/mcp"
}

Write-Host ""
Write-Host "Use read-only PostHog access when you authenticate (see the setup doc)."
Write-Host "Done. Verify inside Claude Code with: /seo posthog check"
Write-Host "Full docs: extensions/posthog/docs/POSTHOG-SETUP.md"
