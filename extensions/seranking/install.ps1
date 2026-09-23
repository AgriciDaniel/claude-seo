# Claude SEO — SE Ranking extension installer (Windows / PowerShell).
$ErrorActionPreference = "Stop"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3 is required."
}

$SkillDir = Join-Path $HOME ".claude/skills"
$SettingsJson = Join-Path $HOME ".claude/settings.json"

if (-not (Test-Path (Join-Path $SkillDir "seo"))) {
    throw "claude-seo base plugin not installed."
}

$Key = Read-Host "SE Ranking API key" -AsSecureString
$Plain = [System.Net.NetworkCredential]::new("", $Key).Password
if (-not $Plain) { throw "No key provided." }

$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillTarget = Join-Path $SkillDir "seo-seranking"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item -Path (Join-Path $SourceDir "skills/seo-seranking/SKILL.md") `
          -Destination (Join-Path $SkillTarget "SKILL.md") -Force

$pyScript = @"
import json, os, sys, tempfile
path, key = sys.argv[1], os.environ['CLAUDE_SEO_SECRET']
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except ValueError: sys.exit('x ' + path + ' is not valid JSON. Nothing was changed; fix it and rerun.')
data.setdefault('env', {})['SERANKING_API_KEY'] = key
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.', prefix='.settings.', suffix='.json')
with os.fdopen(fd, 'w') as fh:
    json.dump(data, fh, indent=2)
os.replace(tmp, path)
"@
$env:CLAUDE_SEO_SECRET = $Plain
try { $pyScript | python - $SettingsJson } finally { Remove-Item Env:CLAUDE_SEO_SECRET -ErrorAction SilentlyContinue }
Write-Host "Done. Try: /seo seranking ai-visibility brandname"
