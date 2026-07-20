$ErrorActionPreference = "Stop"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3 required" }
$SkillDir = Join-Path $HOME ".claude/skills"
$SettingsJson = Join-Path $HOME ".claude/settings.json"
if (-not (Test-Path (Join-Path $SkillDir "seo"))) { throw "claude-seo not installed" }
$BingKey = (Read-Host "Bing Webmaster Tools API key" -AsSecureString)
$IdxKey  = Read-Host "IndexNow host key (32+ chars)"
$IdxLoc  = Read-Host "IndexNow keyLocation URL"
$BingPlain = [System.Net.NetworkCredential]::new("", $BingKey).Password
if (-not $BingPlain -and -not $IdxKey) { throw "Provide at least one of: Bing API key, IndexNow key." }
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillTarget = Join-Path $SkillDir "seo-bing"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item (Join-Path $SourceDir "skills/seo-bing/SKILL.md") (Join-Path $SkillTarget "SKILL.md") -Force
$py = @"
import json, os, sys, tempfile
path, bing, idx_key, idx_loc = sys.argv[1:5]
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except: data = {}
env = data.setdefault('env', {})
if bing: env['BING_WEBMASTER_API_KEY'] = bing
if idx_key: env['INDEXNOW_KEY'] = idx_key
if idx_loc: env['INDEXNOW_KEY_LOCATION'] = idx_loc
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.', prefix='.settings.', suffix='.json')
with os.fdopen(fd, 'w') as fh: json.dump(data, fh, indent=2)
os.replace(tmp, path)
"@
$py | python - $SettingsJson $BingPlain $IdxKey $IdxLoc
Write-Host "Done."
