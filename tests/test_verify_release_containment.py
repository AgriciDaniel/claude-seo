"""verify_release never reads outside the tree it verifies (GHSA-hxhx-mm7f-q4qm).

A manifest is untrusted input. An entry that is absolute, climbs out with
``..`` or goes through a symlink to a file outside the root used to be hashed
and its SHA-256 printed. Such entries are now refused unread, listed under
``outside_root``, and fail the verification.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_release  # noqa: E402

SECRET = b"contents of a private file outside the checkout\n"
SECRET_SHA = hashlib.sha256(SECRET).hexdigest()
GOOD = b"tracked file\n"
GOOD_SHA = hashlib.sha256(GOOD).hexdigest()


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "checkout"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "ok.py").write_bytes(GOOD)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(SECRET)
    return root, outside


def _manifest(tmp_path, files: dict) -> Path:
    path = tmp_path / "release-manifest.json"
    path.write_text(json.dumps({"version": "0", "files": files}))
    return path


def _assert_refused(result: dict, entry: str) -> None:
    assert result["ok"] is False
    assert result["outside_root"] == [entry]
    assert result["mismatched"] == []
    assert SECRET_SHA not in json.dumps(result)


def test_absolute_path_is_refused_unread(tree, tmp_path) -> None:
    root, outside = tree
    result = verify_release.verify(_manifest(tmp_path, {str(outside): "0" * 64}), root)
    _assert_refused(result, str(outside))


def test_parent_traversal_is_refused_unread(tree, tmp_path) -> None:
    root, _outside = tree
    result = verify_release.verify(_manifest(tmp_path, {"../outside.txt": "0" * 64}), root)
    _assert_refused(result, "../outside.txt")


def test_traversal_hidden_inside_a_path_is_refused(tree, tmp_path) -> None:
    root, _outside = tree
    entry = "scripts/../../outside.txt"
    result = verify_release.verify(_manifest(tmp_path, {entry: "0" * 64}), root)
    _assert_refused(result, entry)


def test_symlink_leaving_the_tree_is_refused(tree, tmp_path) -> None:
    root, outside = tree
    try:
        os.symlink(outside, root / "link.txt")
        os.symlink(outside.parent, root / "linkdir")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available here")
    for entry in ("link.txt", "linkdir/outside.txt"):
        result = verify_release.verify(_manifest(tmp_path, {entry: "0" * 64}), root)
        _assert_refused(result, entry)


def test_a_correct_hash_does_not_make_an_outside_file_pass(tree, tmp_path) -> None:
    root, _outside = tree
    result = verify_release.verify(_manifest(tmp_path, {"../outside.txt": SECRET_SHA}), root)
    assert result["ok"] is False
    assert result["outside_root"] == ["../outside.txt"]


@pytest.mark.parametrize("entry", ["", ".", "C:\\Windows\\win.ini", "\\\\host\\share\\f", "\\abs"])
def test_other_unusable_entries_are_refused(tree, tmp_path, entry) -> None:
    root, _outside = tree
    result = verify_release.verify(_manifest(tmp_path, {entry: "0" * 64}), root)
    assert result["ok"] is False
    assert result["outside_root"] == [entry]


def test_files_inside_the_tree_still_verify(tree, tmp_path) -> None:
    root, _outside = tree
    (root / "docs").mkdir()
    (root / "docs" / "inner.txt").write_bytes(GOOD)
    try:
        os.symlink(root / "docs" / "inner.txt", root / "inside-link.txt")
        links = {"inside-link.txt": GOOD_SHA}
    except (OSError, NotImplementedError):
        links = {}
    files = {"scripts/ok.py": GOOD_SHA, "scripts/../docs/inner.txt": GOOD_SHA, **links}
    result = verify_release.verify(_manifest(tmp_path, files), root)
    assert result["ok"] is True
    assert result["outside_root"] == []
    assert result["checked"] == len(files)


def test_mismatch_and_missing_reports_are_unchanged(tree, tmp_path) -> None:
    root, _outside = tree
    result = verify_release.verify(
        _manifest(tmp_path, {"scripts/ok.py": "0" * 64, "scripts/gone.py": GOOD_SHA}), root
    )
    assert result["ok"] is False
    assert result["mismatched"] == [
        {"path": "scripts/ok.py", "expected": "0" * 64, "actual": GOOD_SHA}
    ]
    assert result["missing"] == ["scripts/gone.py"]
    assert result["outside_root"] == []


def test_cli_fails_and_names_the_entry_without_its_hash(tree, tmp_path, monkeypatch, capsys) -> None:
    root, outside = tree
    manifest = _manifest(tmp_path, {str(outside): "0" * 64, "scripts/ok.py": GOOD_SHA})
    monkeypatch.setattr(sys, "argv", ["verify_release.py", str(manifest), "--root", str(root)])
    assert verify_release.main() == 1
    out = capsys.readouterr().out
    assert "Verification: FAIL" in out
    assert "Outside the checkout" in out and str(outside) in out
    assert SECRET_SHA not in out
