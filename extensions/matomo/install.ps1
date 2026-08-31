$ErrorActionPreference = "Stop"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3 required" }
$SkillDir = Join-Path $HOME ".claude/skills"
$AgentsDir = Join-Path $HOME ".claude/agents"
$SettingsJson = Join-Path $HOME ".claude/settings.json"
if (-not (Test-Path (Join-Path $SkillDir "seo"))) { throw "claude-seo not installed" }
$MatomoUrl  = Read-Host "Matomo instance URL (e.g. https://analytics.example.com)"
if (-not $MatomoUrl) { throw "Matomo URL required" }
$TokenSecure = Read-Host "Matomo API token_auth (32-char hex)" -AsSecureString
$TokenPlain = [System.Net.NetworkCredential]::new("", $TokenSecure).Password
if (-not $TokenPlain) { throw "Matomo token_auth required" }
$SiteId = Read-Host "Default site ID (idSite, optional, e.g. 1)"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillTarget = Join-Path $SkillDir "seo-matomo"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item (Join-Path $SourceDir "skills/seo-matomo/SKILL.md") (Join-Path $SkillTarget "SKILL.md") -Force
$AgentTarget = Join-Path $AgentsDir "seo-matomo.md"
New-Item -ItemType Directory -Path $AgentsDir -Force | Out-Null
Copy-Item (Join-Path $SourceDir "agents/seo-matomo.md") $AgentTarget -Force
$py = @"
import json, os, sys, tempfile
path, url, token, site = sys.argv[1:5]
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except: data = {}
env = data.setdefault('env', {})
env['MATOMO_URL'] = url
env['MATOMO_API_TOKEN'] = token
if site:
    env['MATOMO_SITE_ID'] = site
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.', prefix='.settings.', suffix='.json')
with os.fdopen(fd, 'w') as fh:
    json.dump(data, fh, indent=2)
os.replace(tmp, path)
"@
$py | python - $SettingsJson $MatomoUrl $TokenPlain $SiteId
Write-Host "Done."