"""Manual installers must preserve the runtime's repository-relative layout."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_bash_installer_copies_google_update_data_beside_scripts() -> None:
    installer = _text("install.sh")
    assert 'mkdir -p "${SKILL_DIR}/data"' in installer
    assert (
        'cp -r "${TEMP_DIR}/claude-seo/data/"* "${SKILL_DIR}/data/"'
        in installer
    )


def test_powershell_installer_copies_google_update_data_beside_scripts() -> None:
    installer = _text("install.ps1")
    assert '$DataPath = "$TempDir\\data"' in installer
    assert '$SkillData = "$SkillDir\\data"' in installer
    assert 'Copy-Item -Recurse -Force "$DataPath\\*" $SkillData' in installer


def test_runtime_import_validation_requires_html_clean_split_package() -> None:
    runtime = _text("scripts/runtime.py")
    assert "import bs4, lxml, lxml_html_clean, playwright, requests, trafilatura" in runtime


def test_google_updates_data_exists_at_installed_relative_path() -> None:
    assert (ROOT / "data" / "google-updates.json").is_file()
    assert (ROOT / "scripts" / "seo_updates.py").is_file()
