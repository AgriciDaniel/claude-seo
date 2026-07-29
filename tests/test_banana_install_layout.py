"""Banana script references must match core and standalone install layouts."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_SKILL = ROOT / "skills" / "seo-image-gen" / "SKILL.md"
CORE_PRESETS = ROOT / "skills" / "seo-image-gen" / "references" / "seo-image-presets.md"
EXTENSION = ROOT / "extensions" / "banana"
EXTENSION_SKILL = EXTENSION / "skills" / "seo-image-gen" / "SKILL.md"
EXTENSION_PRESETS = EXTENSION / "references" / "seo-image-presets.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _runtime_extension_scripts(text: str) -> set[str]:
    return set(
        re.findall(
            r'"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/claude-seo" run --extension banana ([A-Za-z0-9_]+\.py)',
            text,
        )
    )


def test_core_image_skill_does_not_assume_banana_scripts_are_local():
    combined = _text(CORE_SKILL) + _text(CORE_PRESETS)
    assert "${CLAUDE_SKILL_DIR}/scripts/" not in combined
    assert "extensions/banana/scripts/" not in combined
    assert "~/.claude/skills/seo-image-gen/scripts/" not in combined


def test_standalone_extension_uses_managed_runtime_for_every_script():
    combined = _text(EXTENSION_SKILL) + _text(EXTENSION_PRESETS)
    referenced = _runtime_extension_scripts(combined)
    assert referenced == {
        "batch.py",
        "cost_tracker.py",
        "generate.py",
        "presets.py",
        "setup_mcp.py",
    }
    for script in referenced:
        assert (EXTENSION / "scripts" / script).is_file()
    assert "BANANA_EXTENSION_ROOT" not in combined
    assert "python3" not in combined
    assert "~/.claude/skills/seo-image-gen/scripts/" not in combined


def test_standalone_installer_copies_scripts_beside_skill_file():
    installer = _text(EXTENSION / "install.sh")
    assert 'mkdir -p "${SKILL_DIR}/scripts" "${SKILL_DIR}/references"' in installer
    assert 'cp "${SOURCE_DIR}/scripts/"*.py "${SKILL_DIR}/scripts/"' in installer
    assert '"$HOME/.claude/skills/seo/bin/claude-seo" run' in installer


def test_top_level_installer_keeps_extension_scripts_under_core_extension_tree():
    installer = _text(ROOT / "install.sh")
    assert 'mkdir -p "${SKILL_DIR}/extensions/${ext_name}/scripts"' in installer
    assert 'cp -r "${ext_dir}scripts/"* "${SKILL_DIR}/extensions/${ext_name}/scripts/"' in installer
