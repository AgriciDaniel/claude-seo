"""Core copies and extension copies must not drift apart.

The plugin ships the seo-dataforseo, seo-image-gen and seo-posthog skills and
agents, and the seo-bing and seo-shopify skills, in both the core tree and
their extension folders. A manual install copies the extension files over the
core ones (install.sh copies extension skills and agents after the core set),
so any drift changes behaviour depending on how the plugin was installed.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Agents must be byte-identical: the installed copy decides the model,
# maxTurns, tools and prompt.
AGENT_MIRRORS = [
    ("agents/seo-dataforseo.md", "extensions/dataforseo/agents/seo-dataforseo.md"),
    ("agents/seo-image-gen.md", "extensions/banana/agents/seo-image-gen.md"),
    ("agents/seo-posthog.md", "extensions/posthog/agents/seo-posthog.md"),
]

# The DataForSEO skill has no install-specific content, so the whole folder
# (SKILL.md and references) must match.
DATAFORSEO_CORE = ROOT / "skills/seo-dataforseo"
DATAFORSEO_EXT = ROOT / "extensions/dataforseo/skills/seo-dataforseo"

# The Bing skill (#458) is mirrored so plugin installs load it with
# ${CLAUDE_PLUGIN_ROOT} set; like DataForSEO it has no install-specific content.
# The Shopify (#302) and PostHog (#336) skills are mirrored for the same reason.
IDENTICAL_SKILL_MIRRORS = [
    ("skills/seo-bing", "extensions/bing-webmaster/skills/seo-bing"),
    ("skills/seo-shopify", "extensions/shopify/skills/seo-shopify"),
    ("skills/seo-posthog", "extensions/posthog/skills/seo-posthog"),
]

# The plugin-install detection every mirrored extension installer shares.
PLUGIN_AWARE_INSTALLERS = ["bing-webmaster", "shopify", "posthog"]
LAUNCHER_TOKEN = '"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo"'
MANUAL_LAUNCHER = '"$HOME/.claude/skills/seo/scripts/claude-seo"'

# The image-gen skill differs on purpose: the core copy has no scripts and
# points at the installed Banana MCP, while the extension copy ships
# presets.py, cost_tracker.py and generate.py and resolves them through
# ${CLAUDE_SKILL_DIR}. These files may differ; every other reference must not.
IMAGE_GEN_CORE_REFS = ROOT / "skills/seo-image-gen/references"
IMAGE_GEN_EXT_REFS = ROOT / "extensions/banana/references"
IMAGE_GEN_ALLOWED_DIFFERENCES = {
    "cost-tracking.md",
    "gemini-models.md",
    "mcp-tools.md",
    "prompt-engineering.md",
    "seo-image-presets.md",
}


@pytest.mark.parametrize("core, ext", AGENT_MIRRORS)
def test_agent_mirrors_are_identical(core, ext):
    assert (ROOT / core).read_bytes() == (ROOT / ext).read_bytes(), (
        f"{ext} has drifted from {core}; edit both together"
    )


def _files(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_dataforseo_skill_mirror_is_identical():
    core, ext = _files(DATAFORSEO_CORE), _files(DATAFORSEO_EXT)
    assert core == ext, f"file sets differ: {sorted(core ^ ext)}"
    drifted = [
        name
        for name in sorted(core)
        if (DATAFORSEO_CORE / name).read_bytes() != (DATAFORSEO_EXT / name).read_bytes()
    ]
    assert not drifted, f"seo-dataforseo copies have drifted: {drifted}"


@pytest.mark.parametrize("core, ext", IDENTICAL_SKILL_MIRRORS)
def test_skill_mirror_folders_are_identical(core, ext):
    core_dir, ext_dir = ROOT / core, ROOT / ext
    assert (core_dir / "SKILL.md").is_file(), f"{core}/SKILL.md missing"
    core_files, ext_files = _files(core_dir), _files(ext_dir)
    assert core_files == ext_files, f"file sets differ: {sorted(core_files ^ ext_files)}"
    drifted = [
        name
        for name in sorted(core_files)
        if (core_dir / name).read_bytes() != (ext_dir / name).read_bytes()
    ]
    assert not drifted, f"{ext} has drifted from {core}; edit both together: {drifted}"


def test_bing_installers_work_for_plugin_installs():
    """#458: the installers must not require ~/.claude/skills/seo, and must not
    copy the skill unrewritten (a copied personal skill has no plugin root)."""
    sh = (ROOT / "extensions/bing-webmaster/install.sh").read_text(encoding="utf-8")
    ps = (ROOT / "extensions/bing-webmaster/install.ps1").read_text(encoding="utf-8")
    for text in (sh, ps):
        assert "plugins/cache/" in text
        assert "CLAUDE_PLUGIN_ROOT" in text
        assert "storing keys only" in text
        assert '"$HOME/.claude/skills/seo/scripts/claude-seo"' in text
    assert 'cp "${SOURCE_DIR}/skills/seo-bing/SKILL.md"' not in sh
    assert "Copy-Item (Join-Path $SourceDir \"skills/seo-bing/SKILL.md\")" not in ps
    assert 'if [ "${INSTALL_MODE}" = "manual" ]; then' in sh
    assert 'if ($InstallMode -eq "manual") {' in ps


@pytest.mark.parametrize("name", PLUGIN_AWARE_INSTALLERS)
def test_mirrored_extension_installers_detect_plugin_installs(name):
    """A plugin install never has ~/.claude/skills/seo; the installer must look
    for the plugin too, and copy files only on a manual install."""
    sh = (ROOT / "extensions" / name / "install.sh").read_text(encoding="utf-8")
    ps = (ROOT / "extensions" / name / "install.ps1").read_text(encoding="utf-8")
    for text in (sh, ps):
        assert "plugins/cache/" in text
        assert "CLAUDE_PLUGIN_ROOT" in text
        assert ".claude-plugin/plugin.json" in text
        assert "no plugin install and no ~/.claude/skills/seo" in text
    assert 'if [ "${INSTALL_MODE}" = "manual" ]; then' in sh
    assert 'if ($InstallMode -eq "manual") {' in ps


def test_shopify_installers_rewrite_the_launcher_and_guard_the_env_file():
    """The Shopify skill calls the launcher, so a manual copy must be rewritten.
    The optional .shopify-env is owner-only and never overwritten."""
    sh = (ROOT / "extensions/shopify/install.sh").read_text(encoding="utf-8")
    ps = (ROOT / "extensions/shopify/install.ps1").read_text(encoding="utf-8")
    skill = (ROOT / "skills/seo-shopify/SKILL.md").read_text(encoding="utf-8")
    assert LAUNCHER_TOKEN in skill
    for text in (sh, ps):
        assert MANUAL_LAUNCHER in text
        assert "nothing to copy" in text
        assert "already exists; left untouched" in text
    assert 'cp "${SOURCE_DIR}/skills/seo-shopify/SKILL.md"' not in sh
    assert "Copy-Item (Join-Path $SourceDir \"skills/seo-shopify/SKILL.md\")" not in ps
    assert "umask 077" in sh and 'chmod 600 "${ENV_TARGET}"' in sh
    assert "/inheritance:r" in ps
    # The installer hands out the template only; it never reads a signature.
    assert "read -rs" not in sh and "AsSecureString" not in ps


def test_posthog_installers_register_only_the_mcp_server_for_plugin_installs():
    sh = (ROOT / "extensions/posthog/install.sh").read_text(encoding="utf-8")
    ps = (ROOT / "extensions/posthog/install.ps1").read_text(encoding="utf-8")
    for text in (sh, ps):
        assert "registering the MCP server only" in text
        assert "mcp add --transport http posthog https://mcp.posthog.com/mcp" in text
        assert "API key" not in text and "token" not in text.lower()
    # Neither file carries a launcher path, so the manual copy needs no rewrite.
    for rel in ("skills/seo-posthog/SKILL.md", "agents/seo-posthog.md"):
        assert "CLAUDE_PLUGIN_ROOT" not in (ROOT / rel).read_text(encoding="utf-8"), rel


def _run_installer(tmp_path, name, *, manual, answer="n\n", cwd=None):
    """Run an extension installer with a throwaway HOME and no claude CLI."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    if manual:
        (home / ".claude/skills/seo").mkdir(parents=True, exist_ok=True)
    work = cwd or tmp_path / "work"
    work.mkdir(exist_ok=True)
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for tool in ("bash", "sed", "cp", "mkdir", "chmod", "dirname", "ls", "tail", "rm", "env"):
        found = shutil.which(tool)
        assert found, f"{tool} not available"
        link = bindir / tool
        if not link.exists():
            link.symlink_to(found)
    env = {"HOME": str(home), "PATH": str(bindir)}
    proc = subprocess.run(
        [str(bindir / "bash"), str(ROOT / "extensions" / name / "install.sh")],
        input=answer, capture_output=True, text=True, cwd=work, env=env, timeout=60,
    )
    return proc, home, work


_NEEDS_BASH = pytest.mark.skipif(
    os.name != "posix" or shutil.which("bash") is None, reason="needs a POSIX bash"
)


@_NEEDS_BASH
@pytest.mark.parametrize("name", ["shopify", "posthog"])
def test_plugin_install_copies_nothing(tmp_path, name):
    proc, home, work = _run_installer(tmp_path, name, manual=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "claude-seo plugin detected" in proc.stdout
    assert "does not ship" not in proc.stdout
    assert not (home / ".claude").exists()
    assert not (work / ".shopify-env").exists()


@_NEEDS_BASH
def test_shopify_manual_install_rewrites_the_launcher(tmp_path):
    proc, home, _ = _run_installer(tmp_path, "shopify", manual=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    installed = (home / ".claude/skills/seo-shopify/SKILL.md").read_text(encoding="utf-8")
    assert "CLAUDE_PLUGIN_ROOT" not in installed
    assert installed.count(MANUAL_LAUNCHER) == 2
    source = (ROOT / "extensions/shopify/skills/seo-shopify/SKILL.md").read_text(encoding="utf-8")
    assert installed == source.replace(LAUNCHER_TOKEN, MANUAL_LAUNCHER)


@_NEEDS_BASH
def test_shopify_env_template_is_owner_only_and_never_overwritten(tmp_path):
    proc, _, work = _run_installer(tmp_path, "shopify", manual=False, answer="y\n")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    env_file = work / ".shopify-env"
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert env_file.read_bytes() == (ROOT / "extensions/shopify/.shopify-env.example").read_bytes()

    env_file.write_text("Domain = mine.example\n", encoding="utf-8")
    again, _, _ = _run_installer(tmp_path, "shopify", manual=False, answer="y\n", cwd=work)
    assert again.returncode == 0, again.stdout + again.stderr
    assert "already exists; left untouched" in again.stdout
    assert env_file.read_text(encoding="utf-8") == "Domain = mine.example\n"


@_NEEDS_BASH
def test_posthog_manual_install_copies_skill_and_agent(tmp_path):
    proc, home, _ = _run_installer(tmp_path, "posthog", manual=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (home / ".claude/skills/seo-posthog/SKILL.md").read_bytes() == (
        ROOT / "skills/seo-posthog/SKILL.md"
    ).read_bytes()
    assert (home / ".claude/agents/seo-posthog.md").read_bytes() == (
        ROOT / "agents/seo-posthog.md"
    ).read_bytes()
    # No claude CLI on PATH: the installer prints the manual command instead.
    assert "claude mcp add --transport http posthog https://mcp.posthog.com/mcp" in proc.stdout


@_NEEDS_BASH
@pytest.mark.parametrize("name", ["shopify", "posthog"])
def test_installer_refuses_when_claude_seo_is_absent(tmp_path, name):
    """Copied out of the repository, with no manual and no plugin install."""
    ext = tmp_path / "loose" / name
    shutil.copytree(ROOT / "extensions" / name, ext)
    home = tmp_path / "home"
    home.mkdir()
    proc = subprocess.run(
        [shutil.which("bash"), str(ext / "install.sh")], input="n\n",
        capture_output=True, text=True, cwd=tmp_path,
        env={"HOME": str(home), "PATH": os.environ.get("PATH", "")}, timeout=60,
    )
    assert proc.returncode == 1
    assert "claude-seo base not installed" in proc.stdout
    assert not (home / ".claude").exists()


def test_image_gen_references_differ_only_where_documented():
    core, ext = _files(IMAGE_GEN_CORE_REFS), _files(IMAGE_GEN_EXT_REFS)
    assert core == ext, f"reference file sets differ: {sorted(core ^ ext)}"
    drifted = {
        name
        for name in core
        if (IMAGE_GEN_CORE_REFS / name).read_bytes() != (IMAGE_GEN_EXT_REFS / name).read_bytes()
    }
    unexpected = drifted - IMAGE_GEN_ALLOWED_DIFFERENCES
    assert not unexpected, f"undocumented image-gen reference drift: {sorted(unexpected)}"
