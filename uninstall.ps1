#!/usr/bin/env pwsh
# claude-seo manual-install uninstaller (Windows)
#
# Removes the orchestrator skill (~/.config/opencode/seo-skills), all sub-skills
# (~/.config/opencode/seo-skills/seo-*), and all sub-agents (~/.config/opencode/agents/seo-*.md).
#
# Uses glob enumeration rather than a hardcoded list so future skill
# additions are cleaned up automatically without releasing a new
# uninstaller.
#
# Plugin-install users should use Claude Code's own command instead:
#   /plugin uninstall claude-seo@agricidaniel-claude-seo
#   /plugin marketplace remove AgriciDaniel/claude-seo

$ErrorActionPreference = "Stop"

function Write-Color($Color, $Text) {
    Write-Host $Text -ForegroundColor $Color
}

function Main {
    $SkillDir = Join-Path $env:USERPROFILE ".config" "opencode" "seo-skills"
    $AgentDir = Join-Path $env:USERPROFILE ".config" "opencode" "agents"
    $CommandsDir = Join-Path $env:USERPROFILE ".config" "opencode" "commands"

    Write-Color Cyan "=== Uninstalling claude-seo ==="
    Write-Host ""

    $removedSkills = 0
    $removedAgents = 0
    $removedCommands = 0

    # Remove orchestrator if present
    $orchestratorPath = $SkillDir
    if (Test-Path $orchestratorPath -PathType Container) {
        Remove-Item -Recurse -Force $orchestratorPath
        Write-Color Green "  Removed: $orchestratorPath"
        $removedSkills++
    }

    # Remove every seo-* sub-skill directory
    if (Test-Path $SkillDir -PathType Container) {
        Get-ChildItem -Path $SkillDir -Directory -Filter "seo-*" -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item -Recurse -Force $_.FullName
            Write-Color Green "  Removed: $($_.FullName)"
            $script:removedSkills++
        }
    }

    # Remove every seo-*.md agent file
    if (Test-Path $AgentDir -PathType Container) {
        Get-ChildItem -Path $AgentDir -File -Filter "seo-*.md" -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item -Force $_.FullName
            Write-Color Green "  Removed: $($_.FullName)"
            $script:removedAgents++
        }
    }

    # Remove every seo*.md command file
    if (Test-Path $CommandsDir -PathType Container) {
        Get-ChildItem -Path $CommandsDir -File -Filter "seo*.md" -ErrorAction SilentlyContinue | ForEach-Object {
            Remove-Item -Force $_.FullName
            Write-Color Green "  Removed: $($_.FullName)"
            $script:removedCommands++
        }
    }

    Write-Host ""
    if ($removedSkills -eq 0 -and $removedAgents -eq 0 -and $removedCommands -eq 0) {
        Write-Color Yellow "Nothing to remove. Claude SEO does not appear to be installed."
        Write-Color Yellow "If you installed via /plugin install, run /plugin uninstall instead."
        return
    }

    Write-Color Cyan "=== claude-seo uninstalled ($removedSkills skill dirs, $removedAgents agent files, $removedCommands command files) ==="
    Write-Host ""
    Write-Color Yellow "Restart Claude Code to complete removal."
}

Main
