# Claude SEO: PostHog extension installer (Windows).
#
# Installs the seo-posthog skill and agent. Data comes from the PostHog MCP
# server, so no credential is collected or stored here.
$ErrorActionPreference = "Stop"
$SkillDir = Join-Path $HOME ".claude/skills"
$AgentsDir = Join-Path $HOME ".claude/agents"
if (-not (Test-Path (Join-Path $SkillDir "seo"))) { throw "claude-seo base not installed." }
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$SkillTarget = Join-Path $SkillDir "seo-posthog"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item (Join-Path $SourceDir "skills/seo-posthog/SKILL.md") (Join-Path $SkillTarget "SKILL.md") -Force
Write-Host "Installed skill: $SkillTarget"

New-Item -ItemType Directory -Path $AgentsDir -Force | Out-Null
$AgentTarget = Join-Path $AgentsDir "seo-posthog.md"
Copy-Item (Join-Path $SourceDir "agents/seo-posthog.md") $AgentTarget -Force
Write-Host "Installed agent: $AgentTarget"

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
Write-Host "Done. Verify inside Claude Code with: /seo posthog check"
Write-Host "Full docs: extensions/posthog/docs/POSTHOG-SETUP.md"
