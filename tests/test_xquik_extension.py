"""Installation and documentation contracts for the Xquik extension."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "extensions" / "xquik"
INSTALLER = EXTENSION / "install.sh"
UNINSTALLER = EXTENSION / "uninstall.sh"


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    scripts = home / ".claude" / "skills" / "seo" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "url_safety.py").write_text("# fixture\n", encoding="utf-8")
    return home


def _run(script: Path, home: Path, *, input_text: str = "") -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    return subprocess.run(
        ["bash", str(script)],
        input=input_text,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )


def test_installer_preserves_settings_and_treats_key_as_data(tmp_path: Path) -> None:
    home = _home(tmp_path)
    settings_path = home / ".claude" / "settings.json"
    settings_path.write_text(
        json.dumps({"env": {"KEEP": "yes"}, "permissions": {"allow": ["Read"]}}),
        encoding="utf-8",
    )
    marker = tmp_path / "must-not-exist"
    credential = f"''' ; touch {marker} ; #"

    result = _run(INSTALLER, home, input_text=f"{credential}\n")

    assert result.returncode == 0, result.stderr
    assert not marker.exists()
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings == {
        "env": {"KEEP": "yes", "X_TWITTER_SCRAPER_API_KEY": credential},
        "permissions": {"allow": ["Read"]},
    }
    assert stat.S_IMODE(settings_path.stat().st_mode) == 0o600
    installed = home / ".claude" / "skills" / "seo-xquik"
    assert (installed / "SKILL.md").is_file()
    assert (installed / "scripts" / "xquik_research.py").is_file()
    assert credential not in result.stdout
    assert credential not in result.stderr


def test_installer_replaces_only_its_key_on_repeat(tmp_path: Path) -> None:
    home = _home(tmp_path)

    first = _run(INSTALLER, home, input_text="first-key\n")
    second = _run(INSTALLER, home, input_text="second-key\n")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    settings_path = home / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["env"] == {"X_TWITTER_SCRAPER_API_KEY": "second-key"}


def test_invalid_settings_stop_install_without_modification(tmp_path: Path) -> None:
    home = _home(tmp_path)
    settings_path = home / ".claude" / "settings.json"
    original = "{invalid json\n"
    settings_path.write_text(original, encoding="utf-8")

    result = _run(INSTALLER, home, input_text="unused-key\n")

    assert result.returncode != 0
    assert settings_path.read_text(encoding="utf-8") == original
    assert not (home / ".claude" / "skills" / "seo-xquik").exists()


def test_uninstaller_removes_only_xquik_state(tmp_path: Path) -> None:
    home = _home(tmp_path)
    installed = _run(INSTALLER, home, input_text="temporary-key\n")
    assert installed.returncode == 0, installed.stderr
    settings_path = home / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["env"]["KEEP"] = "yes"
    settings["mcpServers"] = {"other": {"command": "example"}}
    settings_path.write_text(json.dumps(settings), encoding="utf-8")

    removed = _run(UNINSTALLER, home)

    assert removed.returncode == 0, removed.stderr
    assert not (home / ".claude" / "skills" / "seo-xquik").exists()
    assert json.loads(settings_path.read_text(encoding="utf-8")) == {
        "env": {"KEEP": "yes"},
        "mcpServers": {"other": {"command": "example"}},
    }
    assert (home / ".claude" / "skills" / "seo").is_dir()


def test_public_docs_preserve_research_boundaries() -> None:
    skill = (EXTENSION / "skills" / "seo-xquik" / "SKILL.md").read_text(
        encoding="utf-8",
    )
    combined = skill + (EXTENSION / "README.md").read_text(encoding="utf-8")

    assert "not a ranking signal" in combined
    assert "cannot post" in combined
    assert "untrusted evidence" in skill
    assert "claude-seo run --extension xquik xquik_research.py" in skill
    assert len(skill.splitlines()) < 500
    setup = EXTENSION / "docs" / "XQUIK-SETUP.md"
    assert len(setup.read_text(encoding="utf-8").splitlines()) < 200
