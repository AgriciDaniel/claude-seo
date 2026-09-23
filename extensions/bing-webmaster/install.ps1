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
path = sys.argv[1]
idx_loc = sys.argv[2] if len(sys.argv) > 2 else ''
bing = os.environ.get('CLAUDE_SEO_SECRET', '')
idx_key = os.environ.get('CLAUDE_SEO_INDEXNOW_KEY', '')
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except ValueError: sys.exit('x ' + path + ' is not valid JSON. Nothing was changed; fix it and rerun.')
env = data.setdefault('env', {})
if bing: env['BING_WEBMASTER_API_KEY'] = bing
if idx_key: env['INDEXNOW_KEY'] = idx_key
if idx_loc: env['INDEXNOW_KEY_LOCATION'] = idx_loc
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.', prefix='.settings.', suffix='.json')
with os.fdopen(fd, 'w') as fh: json.dump(data, fh, indent=2)
os.replace(tmp, path)
"@
$env:CLAUDE_SEO_SECRET = $BingPlain
$env:CLAUDE_SEO_INDEXNOW_KEY = $IdxKey
try {
    $py | python - $SettingsJson $IdxLoc
    # A native command's non-zero exit does not throw, even with Stop.
    if ($LASTEXITCODE -ne 0) { throw "Nothing was saved (python exited $LASTEXITCODE). See the message above." }
} finally { Remove-Item Env:CLAUDE_SEO_SECRET -ErrorAction SilentlyContinue; Remove-Item Env:CLAUDE_SEO_INDEXNOW_KEY -ErrorAction SilentlyContinue }
Write-Host "Done."
