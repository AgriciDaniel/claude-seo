$ErrorActionPreference = "Stop"
$SkillDir = Join-Path $HOME ".claude/skills"
if (-not (Test-Path (Join-Path $SkillDir "seo"))) { throw "claude-seo not installed" }
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillTarget = Join-Path $SkillDir "seo-shopify"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item (Join-Path $SourceDir "skills/seo-shopify/SKILL.md") `
          (Join-Path $SkillTarget "SKILL.md") -Force
Write-Host "Installed skill: $SkillTarget"
Write-Host "Next: issue a Crawler Access signature in the Shopify admin and write it to .shopify-env"
Write-Host "      in your audit folder (template: $SourceDir\.shopify-env.example)."
Write-Host "Done."
