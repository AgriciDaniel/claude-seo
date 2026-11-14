"""Core copies and extension copies must not drift apart.

The plugin ships the seo-dataforseo and seo-image-gen skills and agents, and
the seo-bing skill, in both the core tree and their extension folders. A manual
install copies the extension files over the core ones (install.sh copies
extension skills and agents after the core set), so any drift changes behaviour
depending on how the plugin was installed.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Agents must be byte-identical: the installed copy decides the model,
# maxTurns, tools and prompt.
AGENT_MIRRORS = [
    ("agents/seo-dataforseo.md", "extensions/dataforseo/agents/seo-dataforseo.md"),
    ("agents/seo-image-gen.md", "extensions/banana/agents/seo-image-gen.md"),
]

# The DataForSEO skill has no install-specific content, so the whole folder
# (SKILL.md and references) must match.
DATAFORSEO_CORE = ROOT / "skills/seo-dataforseo"
DATAFORSEO_EXT = ROOT / "extensions/dataforseo/skills/seo-dataforseo"

# The Bing skill (#458) is mirrored so plugin installs load it with
# ${CLAUDE_PLUGIN_ROOT} set; like DataForSEO it has no install-specific content.
IDENTICAL_SKILL_MIRRORS = [
    ("skills/seo-bing", "extensions/bing-webmaster/skills/seo-bing"),
]

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
