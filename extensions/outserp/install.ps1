$ErrorActionPreference = "Stop"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3 required" }
$SkillDir = Join-Path $HOME ".claude/skills"
$SettingsJson = Join-Path $HOME ".claude/settings.json"
if (-not (Test-Path (Join-Path $SkillDir "seo"))) { throw "claude-seo not installed" }
Write-Host "The Outserp MCP server authenticates via OAuth (run /mcp in Claude Code after install)."
$Key = Read-Host "Outserp API key (optional, press Enter to skip)" -AsSecureString
$Plain = [System.Net.NetworkCredential]::new("", $Key).Password
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SkillTarget = Join-Path $SkillDir "seo-outserp"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item (Join-Path $SourceDir "skills/seo-outserp/SKILL.md") `
          (Join-Path $SkillTarget "SKILL.md") -Force
$py = @"
import json, os, sys, tempfile
path, key = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    try: data = json.load(open(path))
    except: data = {}
data.setdefault('mcpServers', {})['outserp'] = {'type': 'http', 'url': 'https://mcp.outserp.ai/mcp'}
if key:
    data.setdefault('env', {})['OUTSERP_API_KEY'] = key
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.', prefix='.settings.', suffix='.json')
with os.fdopen(fd, 'w') as fh: json.dump(data, fh, indent=2)
os.replace(tmp, path)
"@
$py | python - $SettingsJson $Plain
Write-Host "Done. Run /mcp in Claude Code to authenticate 'outserp', then: /seo outserp whoami"
