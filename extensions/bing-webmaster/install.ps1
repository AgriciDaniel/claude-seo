$ErrorActionPreference = "Stop"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3 required" }
$SkillDir = Join-Path $HOME ".claude/skills"
$SettingsJson = Join-Path $HOME ".claude/settings.json"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Plugin installs already ship the skill (skills/seo-bing), so only the keys are
# stored. Manual installs (~/.claude/skills/seo) also get the skill copied with
# its launcher path rewritten, because they have no ${CLAUDE_PLUGIN_ROOT}.
$InstallMode = ""
$PluginRoot = ""
if (Test-Path (Join-Path $SkillDir "seo")) {
    $InstallMode = "manual"
} elseif ($env:CLAUDE_PLUGIN_ROOT -and (Test-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT "skills/seo"))) {
    $InstallMode = "plugin"; $PluginRoot = $env:CLAUDE_PLUGIN_ROOT
} else {
    $OwnRoot = Split-Path -Parent (Split-Path -Parent $SourceDir)
    if ((Test-Path (Join-Path $OwnRoot "skills/seo")) -and (Test-Path (Join-Path $OwnRoot ".claude-plugin/plugin.json"))) {
        $InstallMode = "plugin"; $PluginRoot = $OwnRoot
    } else {
        $Cached = Get-ChildItem -Path (Join-Path $HOME ".claude/plugins/cache/*/claude-seo/*/skills/seo") -Directory -ErrorAction SilentlyContinue | Select-Object -Last 1
        if ($Cached) { $InstallMode = "plugin"; $PluginRoot = Split-Path -Parent (Split-Path -Parent $Cached.FullName) }
    }
}
if (-not $InstallMode) { throw "claude-seo not installed (no plugin install and no ~/.claude/skills/seo)" }
if ($InstallMode -eq "plugin") {
    Write-Host "claude-seo plugin detected: storing keys only."
    if (-not (Test-Path (Join-Path $PluginRoot "skills/seo-bing/SKILL.md"))) {
        Write-Host "! This plugin version does not ship the seo-bing skill yet. Update the claude-seo plugin, then /seo bing will load."
    }
}
$BingKey = (Read-Host "Bing Webmaster Tools API key" -AsSecureString)
$IdxKey  = Read-Host "IndexNow host key (32+ chars)"
$IdxLoc  = Read-Host "IndexNow keyLocation URL"
$BingPlain = [System.Net.NetworkCredential]::new("", $BingKey).Password
if (-not $BingPlain -and -not $IdxKey) { throw "Provide at least one of: Bing API key, IndexNow key." }
if ($InstallMode -eq "manual") {
    $SkillTarget = Join-Path $SkillDir "seo-bing"
    New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
    # Same rewrite the main installer applies; Claude Code's Bash tool expands $HOME on Windows too.
    $Doc = [System.IO.File]::ReadAllText((Join-Path $SourceDir "skills/seo-bing/SKILL.md"))
    $Doc = $Doc.Replace('"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo"', '"$HOME/.claude/skills/seo/scripts/claude-seo"')
    [System.IO.File]::WriteAllText((Join-Path $SkillTarget "SKILL.md"), $Doc, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "Installed skill: $SkillTarget"
}
$SettingsParent = Split-Path -Parent $SettingsJson
if (-not (Test-Path $SettingsParent)) { New-Item -ItemType Directory -Path $SettingsParent -Force | Out-Null }
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
Write-Host "Done. Restart Claude Code so the new env values load, then run: /seo bing verify-indexnow --host example.com"
