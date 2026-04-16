#!/usr/bin/env pwsh
# claude-seo uninstaller for Windows
# Cleanly removes all SEO skills, agents, and scripts

$ErrorActionPreference = "Stop"

function Write-Color($Color, $Text) {
    Write-Host $Text -ForegroundColor $Color
}

function Main {
    $SkillDir = Join-Path $env:USERPROFILE ".claude" "skills"
    $AgentDir = Join-Path $env:USERPROFILE ".claude" "agents"

    Write-Color Cyan "=== Uninstalling claude-seo ==="
    Write-Host ""

    # Remove main skill (includes venv, references, scripts, hooks)
    $seoDir = Join-Path $SkillDir "seo"
    if (Test-Path $seoDir) {
        Remove-Item -Recurse -Force $seoDir
        Write-Color Green "  Removed: $seoDir"
    }

    # Remove sub-skills
    $subSkills = @(
        "seo-audit", "seo-competitor-pages", "seo-content", "seo-geo",
        "seo-hreflang", "seo-images", "seo-page", "seo-plan",
        "seo-programmatic", "seo-schema", "seo-sitemap", "seo-technical"
    )
    foreach ($skill in $subSkills) {
        $skillPath = Join-Path $SkillDir $skill
        if (Test-Path $skillPath) {
            Remove-Item -Recurse -Force $skillPath
            Write-Color Green "  Removed: $skillPath"
        }
    }

    # Remove agents
    $agents = @(
        "seo-technical", "seo-content", "seo-schema",
        "seo-sitemap", "seo-performance", "seo-visual", "seo-geo"
    )
    foreach ($agent in $agents) {
        $agentPath = Join-Path $AgentDir "$agent.md"
        if (Test-Path $agentPath) {
            Remove-Item -Force $agentPath
            Write-Color Green "  Removed: $agentPath"
        }
    }

    Write-Host ""
    Write-Color Cyan "=== claude-seo uninstalled ==="
    Write-Host ""
    Write-Color Yellow "Restart Claude Code to complete removal."
}

Main
