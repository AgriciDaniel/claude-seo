"""Release manifest verification must detect unexpected checkout files."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verify_release  # noqa: E402


def _manifest(root: Path, manifest_path: Path) -> None:
    safe = root / "scripts" / "safe.py"
    safe.parent.mkdir(parents=True)
    safe.write_text("pass\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps({"files": {safe.relative_to(root).as_posix(): hashlib.sha256(safe.read_bytes()).hexdigest()}}),
        encoding="utf-8",
    )


def test_clean_checkout_ignores_manifest_and_git_metadata(tmp_path):
    manifest_path = tmp_path / "release-manifest.json"
    _manifest(tmp_path, manifest_path)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("git metadata", encoding="utf-8")

    result = verify_release.verify(manifest_path, tmp_path)

    assert result["ok"] is True
    assert result["extra"] == []


def test_extra_untracked_file_fails_verification_and_cli(tmp_path, monkeypatch, capsys):
    manifest_path = tmp_path / "release-manifest.json"
    _manifest(tmp_path, manifest_path)
    (tmp_path / "scripts" / "extra.py").write_text("print('unexpected')\n", encoding="utf-8")

    result = verify_release.verify(manifest_path, tmp_path)
    assert result["ok"] is False
    assert result["extra"] == [Path("scripts", "extra.py").as_posix()]
    assert result["mismatched"] == result["missing"] == []

    monkeypatch.setattr(sys, "argv", ["verify_release.py", str(manifest_path), "--root", str(tmp_path)])
    assert verify_release.main() == 1
    assert "Extra (1):" in capsys.readouterr().out


def test_manifest_outside_checkout_is_not_counted(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    manifest_path = tmp_path / "release-manifest.json"
    _manifest(root, manifest_path)

    assert verify_release.verify(manifest_path, root)["ok"] is True
