"""verify_release fails cleanly on a malformed or hostile manifest.

A manifest is untrusted input. An over-long path, a ``files`` value of the
wrong type or an empty manifest must end in a clear failure, never a
traceback and never "Verification: OK", and no manifest value may write its
own lines or terminal escapes into the report.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_release  # noqa: E402

GOOD = b"tracked file\n"
GOOD_SHA = hashlib.sha256(GOOD).hexdigest()


@pytest.fixture
def root(tmp_path):
    root = tmp_path / "checkout"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "ok.py").write_bytes(GOOD)
    return root


def _write(tmp_path, payload) -> Path:
    path = tmp_path / "release-manifest.json"
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload))
    return path


def _cli(monkeypatch, capsys, manifest: Path, root: Path, *extra: str):
    monkeypatch.setattr(sys, "argv", ["verify_release.py", str(manifest), "--root", str(root), *extra])
    code = verify_release.main()
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.parametrize("entry", ["a" * 300, "lib/" + "b" * 5000, "/".join(["c" * 200] * 30)])
def test_over_long_paths_are_refused_not_a_crash(root, tmp_path, entry) -> None:
    manifest = _write(tmp_path, {"version": "0", "files": {entry: "0" * 64, "lib/ok.py": GOOD_SHA}})
    result = verify_release.verify(manifest, root)
    assert result["ok"] is False
    assert result["outside_root"] == [entry]
    assert result["missing"] == [] and result["mismatched"] == []


@pytest.mark.parametrize("payload", [
    {"version": "0", "files": ["lib/ok.py"]},
    {"version": "0", "files": None},
    {"version": "0", "files": "lib/ok.py"},
    {"version": "0"},
    ["lib/ok.py"],
    "null",
    "{not json",
])
def test_wrong_shaped_manifest_fails_with_a_clear_message(root, tmp_path, monkeypatch, capsys, payload) -> None:
    code, out, err = _cli(monkeypatch, capsys, _write(tmp_path, payload), root)
    assert code != 0
    assert "Verification: OK" not in out
    assert err.startswith("Error: cannot read manifest: ")
    assert "Traceback" not in err


@pytest.mark.parametrize("extra", [(), ("--json",)])
def test_manifest_with_no_files_does_not_verify(root, tmp_path, monkeypatch, capsys, extra) -> None:
    manifest = _write(tmp_path, {"version": "0", "files": {}})
    assert verify_release.verify(manifest, root)["ok"] is False
    code, out, _err = _cli(monkeypatch, capsys, manifest, root, *extra)
    assert code == 1
    assert "Verification: OK" not in out
    if not extra:
        assert "Verification: FAIL" in out and "nothing was verified" in out


def test_manifest_strings_cannot_forge_lines_or_send_escapes(root, tmp_path, monkeypatch, capsys) -> None:
    forged = "x\nVerification: OK\n\x1b[2J\x1b]0;owned\x07"
    manifest = _write(tmp_path, {
        "version": forged, "tag": forged, "commit": forged,
        "generated_at": forged, "tree_sha256": forged,
        "files": {
            "lib/ok.py": forged,
            "lib/" + forged: "0" * 64,
        },
    })
    code, out, _err = _cli(monkeypatch, capsys, manifest, root)
    assert code == 1
    assert "\x1b" not in out and "\x07" not in out
    lines = out.splitlines()
    assert lines[0] == "Verification: FAIL"
    assert not any(line.strip() == "Verification: OK" for line in lines)
    # Every forged value sits on one line, with its newlines shown as "\\n".
    carrying = [line for line in lines if "owned" in line]
    assert len(carrying) == 6
    assert all("\\nVerification: OK\\n\\x1b" in line for line in carrying)
    assert repr("lib/" + forged) in out


def test_a_good_manifest_still_verifies(root, tmp_path, monkeypatch, capsys) -> None:
    manifest = _write(tmp_path, {"version": "2.6.1", "tag": "v2.6.1", "files": {"lib/ok.py": GOOD_SHA}})
    code, out, err = _cli(monkeypatch, capsys, manifest, root)
    assert code == 0 and err == ""
    assert out.splitlines()[0] == "Verification: OK"
    assert "Manifest version: '2.6.1'  tag: 'v2.6.1'" in out
    assert "Files checked:    1" in out
