$ErrorActionPreference = "Stop"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3 required" }
$SkillDir = Join-Path $HOME ".claude/skills"
$SettingsJson = Join-Path $HOME ".claude/settings.json"
if (-not (Test-Path (Join-Path $SkillDir "seo"))) { throw "claude-seo not installed" }
$Key = Read-Host "Profound API key" -AsSecureString
$Plain = [System.Net.NetworkCredential]::new("", $Key).Password
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillTarget = Join-Path $SkillDir "seo-profound"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item (Join-Path $SourceDir "skills/seo-profound/SKILL.md") `
          (Join-Path $SkillTarget "SKILL.md") -Force
$py = @"
import json, os, sys, tempfile
path, key = sys.argv[1], os.environ['CLAUDE_SEO_SECRET']
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except ValueError: sys.exit('x ' + path + ' is not valid JSON. Nothing was changed; fix it and rerun.')
data.setdefault('env', {})['PROFOUND_API_KEY'] = key
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.', prefix='.settings.', suffix='.json')
with os.fdopen(fd, 'w') as fh: json.dump(data, fh, indent=2)
os.replace(tmp, path)
"@
$env:CLAUDE_SEO_SECRET = $Plain
try {
    $py | python - $SettingsJson
    # A native command's non-zero exit does not throw, even with Stop.
    if ($LASTEXITCODE -ne 0) { throw "Nothing was saved (python exited $LASTEXITCODE). See the message above." }
} finally { Remove-Item Env:CLAUDE_SEO_SECRET -ErrorAction SilentlyContinue }
Write-Host "Done."
