"""install.sh must not overwrite, and uninstall.sh must not delete, skills or
agents that a claude-seo install did not create.

Each test runs the real installer against a throwaway HOME. A stub `git` on
PATH "clones" this checkout, and the copied runtime launcher is replaced with
a no-op so no Python environment or browser is downloaded.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or BASH is None, reason="install.sh is the macOS and Linux installer"
)

FAKE_GIT = """#!/usr/bin/env bash
if [ "$1" = clone ]; then
    if [ -n "${FAKE_GIT_FAIL:-}" ]; then
        echo "fatal: Remote branch v0.0.0 not found in upstream origin" >&2
        exit 128
    fi
    dest="${@: -1}"
    mkdir -p "$dest"
    cp -R "$FAKE_GIT_SOURCE"/. "$dest"/
    printf '#!/usr/bin/env bash\\nexit 0\\n' > "$dest/scripts/claude-seo"
    exit 0
fi
echo "unexpected git call: $*" >&2
exit 1
"""


@pytest.fixture()
def sandbox(tmp_path: Path):
    source = tmp_path / "source"
    shutil.copytree(
        ROOT, source,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"),
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    git = bindir / "git"
    git.write_text(FAKE_GIT, encoding="utf-8")
    git.chmod(0o755)
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".claude" / "agents").mkdir(parents=True)
    env = {
        **os.environ,
        "HOME": str(home),
        "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}",
        "FAKE_GIT_SOURCE": str(source),
    }
    env.pop("CLAUDE_SEO_TAG", None)
    return home, env


def _run(script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH, str(ROOT / script)], env=env, capture_output=True, text=True, timeout=300
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_failed_download_shows_the_error_and_changes_nothing(sandbox):
    home, env = sandbox
    result = _run("install.sh", {**env, "FAKE_GIT_FAIL": "1"})
    assert result.returncode != 0
    assert "Remote branch v0.0.0 not found" in result.stderr
    assert "Nothing was installed" in result.stderr
    assert list((home / ".claude" / "skills").iterdir()) == []
    assert list((home / ".claude" / "agents").iterdir()) == []


def test_install_backs_up_same_named_user_files_and_writes_a_manifest(sandbox):
    home, env = sandbox
    claude = home / ".claude"
    _write(claude / "skills" / "seo-geo" / "SKILL.md", "my own seo-geo\n")
    _write(claude / "agents" / "seo-technical.md", "my own agent\n")
    _write(claude / "skills" / "seo-custom" / "SKILL.md", "unrelated user skill\n")

    result = _run("install.sh", env)
    assert result.returncode == 0, result.stdout + result.stderr

    backups = list(claude.glob("claude-seo-backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "skills" / "seo-geo" / "SKILL.md").read_text(encoding="utf-8") == "my own seo-geo\n"
    assert (backups[0] / "agents" / "seo-technical.md").read_text(encoding="utf-8") == "my own agent\n"
    assert (claude / "skills" / "seo-geo" / "SKILL.md").read_text(encoding="utf-8") != "my own seo-geo\n"
    assert (claude / "skills" / "seo-custom" / "SKILL.md").read_text(encoding="utf-8") == "unrelated user skill\n"

    manifest = (claude / "skills" / "seo" / ".claude-seo-manifest").read_text(encoding="utf-8").split()
    assert "skills/seo" in manifest
    assert "skills/seo-geo" in manifest
    assert "agents/seo-technical.md" in manifest
    assert "skills/seo-custom" not in manifest
    assert len(manifest) == len(set(manifest))


def test_reinstall_does_not_back_up_its_own_files(sandbox):
    home, env = sandbox
    assert _run("install.sh", env).returncode == 0
    second = _run("install.sh", env)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "Backed up" not in second.stdout
    assert list((home / ".claude").glob("claude-seo-backup-*")) == []


def test_uninstall_removes_only_manifest_entries(sandbox):
    home, env = sandbox
    claude = home / ".claude"
    _write(claude / "skills" / "seo-custom" / "SKILL.md", "unrelated user skill\n")
    _write(claude / "agents" / "seo-mine.md", "unrelated user agent\n")
    assert _run("install.sh", env).returncode == 0

    result = _run("uninstall.sh", env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(p.name for p in (claude / "skills").iterdir()) == ["seo-custom"]
    assert sorted(p.name for p in (claude / "agents").iterdir()) == ["seo-mine.md"]


def test_uninstall_ignores_manifest_entries_outside_its_folders(sandbox):
    home, env = sandbox
    claude = home / ".claude"
    _write(claude / "keep.txt", "keep\n")
    _write(claude / "skills" / "other" / "SKILL.md", "keep\n")
    _write(claude / "skills" / "seo" / ".claude-seo-manifest",
           "skills/seo\n../keep.txt\nskills/../keep.txt\nskills/other\nagents/notes.txt\n")

    result = _run("uninstall.sh", env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (claude / "keep.txt").exists()
    assert (claude / "skills" / "other" / "SKILL.md").exists()
    assert not (claude / "skills" / "seo").exists()
    assert result.stdout.count("Skipped unexpected manifest entry") == 4


def test_uninstall_without_manifest_keeps_the_old_glob_behaviour(sandbox):
    home, env = sandbox
    claude = home / ".claude"
    _write(claude / "skills" / "seo" / "SKILL.md", "old install\n")
    _write(claude / "skills" / "seo-geo" / "SKILL.md", "old install\n")
    _write(claude / "agents" / "seo-geo.md", "old install\n")
    _write(claude / "skills" / "other" / "SKILL.md", "keep\n")

    result = _run("uninstall.sh", env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No install manifest found" in result.stdout
    assert sorted(p.name for p in (claude / "skills").iterdir()) == ["other"]
    assert list((claude / "agents").iterdir()) == []
