$ErrorActionPreference = "Stop"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw "Python 3 required" }
$SkillDir = Join-Path $HOME ".claude/skills"
$AgentsDir = Join-Path $HOME ".claude/agents"
if (-not (Test-Path (Join-Path $SkillDir "seo"))) { throw "claude-seo not installed" }
$MatomoUrl  = Read-Host "Matomo instance URL (e.g. https://analytics.example.com)"
if (-not $MatomoUrl) { throw "Matomo URL required" }
$TokenSecure = Read-Host "Matomo API token_auth (32-char hex)" -AsSecureString
$TokenPlain = [System.Net.NetworkCredential]::new("", $TokenSecure).Password
if (-not $TokenPlain) { throw "Matomo token_auth required" }
$SiteId = Read-Host "Default site ID (idSite, optional, e.g. 1)"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $SourceDir)
$MatomoAuth = Join-Path $RepoRoot "scripts/matomo_auth.py"
# Every Matomo request goes through the SSRF guard, which refuses private
# addresses unless they are named in CLAUDE_SEO_LOCAL_TARGETS. Tell the user
# now, with the exact host:port, rather than at the first failed call.
if (Test-Path $MatomoAuth) {
    $Hint = & python $MatomoAuth --local-target-hint $MatomoUrl 2>$null
    if ($Hint) {
        Write-Host ""
        Write-Host "! $MatomoUrl is on a private address."
        Write-Host "  $Hint"
        Write-Host ""
    }
}
$SkillTarget = Join-Path $SkillDir "seo-matomo"
New-Item -ItemType Directory -Path $SkillTarget -Force | Out-Null
Copy-Item (Join-Path $SourceDir "skills/seo-matomo/SKILL.md") (Join-Path $SkillTarget "SKILL.md") -Force
$AgentTarget = Join-Path $AgentsDir "seo-matomo.md"
New-Item -ItemType Directory -Path $AgentsDir -Force | Out-Null
Copy-Item (Join-Path $SourceDir "agents/seo-matomo.md") $AgentTarget -Force
# Credentials go to ~/.config/claude-seo/matomo.json (0600 on POSIX, an
# icacls-restricted ACL on Windows), written atomically via os.replace, not
# into ~/.claude/settings.json: settings.json is a general-purpose config file
# that tooling reads, prints, and syncs, and an API token has no business in
# it. matomo_auth.py still falls back to the MATOMO_* environment variables.
if (-not (Test-Path $MatomoAuth)) { throw "$MatomoAuth not found" }
$py = @"
import importlib.util, sys

# PowerShell 5.1 drops an empty string argument to a native command, so the
# optional site ID may simply not arrive. Tolerate that rather than crashing
# the installer after the token has already been typed.
args = sys.argv[1:]
auth_path, url, token = args[0], args[1], args[2]
site = args[3] if len(args) > 3 else ""
spec = importlib.util.spec_from_file_location('matomo_auth', auth_path)
matomo_auth = importlib.util.module_from_spec(spec)
sys.modules['matomo_auth'] = matomo_auth
spec.loader.exec_module(matomo_auth)

matomo_auth.save_config({
    'matomo_url': url,
    'matomo_token': token,
    'matomo_site_id': site,
})
print('Wrote Matomo credentials to ' + matomo_auth.CONFIG_PATH)
"@
$py | python - $MatomoAuth $MatomoUrl $TokenPlain $SiteId
Write-Host "Done. MATOMO_URL / MATOMO_API_TOKEN / MATOMO_SITE_ID still override the file."