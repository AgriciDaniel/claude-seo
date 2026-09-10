"""Reference-graph consistency gate.

Runs scripts/consistency_check.py and asserts zero errors: no dead references/
research/script/agent refs, routing-table agreement, and FLOW lock integrity.
Warnings (orphan candidates) are allowed; errors are not. Added after the
2026-07 full review, which found dead ``scripts/presets.py`` invocations that
basename-level checking had masked.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "consistency_check.py")
_SCRIPTS = os.path.join(REPO, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import consistency_check  # noqa: E402


def run_checker():
    proc = subprocess.run([sys.executable, SCRIPT, "--json"],
                          capture_output=True, text=True, cwd=REPO)
    return proc, json.loads(proc.stdout)


def test_no_consistency_errors():
    proc, result = run_checker()
    assert result["errors"] == [], "consistency errors: " + "\n".join(result["errors"])
    assert result["status"] == "PASS"
    assert proc.returncode == 0


def test_checker_scans_whole_tree():
    _, result = run_checker()
    assert result["files_checked"] > 300


def test_user_facing_markdown_has_no_raw_core_script_paths():
    pattern = re.compile(r"(?<![\w/])scripts/([A-Za-z0-9_]+\.py)\b")
    root = Path(REPO)
    offenders = []
    for top in ("skills", "agents", "extensions"):
        for path in (root / top).rglob("*.md"):
            for match in pattern.finditer(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.relative_to(root)}: scripts/{match.group(1)}")
    assert offenders == [], "raw bundled script paths:\n" + "\n".join(offenders)


def _locked_paths() -> list:
    lock = Path(REPO) / consistency_check.LOCK_PATH
    return [line.split()[1] for line in lock.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def _copy_with_crlf(dst: Path, rels: list) -> None:
    """Mirror ``rels`` under ``dst`` the way core.autocrlf=true checks them out."""
    for rel in rels:
        data = (Path(REPO) / rel).read_bytes().replace(b"\r\n", b"\n")
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data.replace(b"\n", b"\r\n"))


def test_flow_lock_accepts_crlf_checkout(tmp_path, monkeypatch):
    """Git for Windows defaults to core.autocrlf=true, so the locked prompt
    files check out with CRLF while the lock was written from LF content.
    Hashing must fold CRLF, or a stock Windows clone reports every locked
    file as tampered."""
    locked = _locked_paths()
    _copy_with_crlf(tmp_path, [consistency_check.LOCK_PATH, *locked])
    monkeypatch.setattr(consistency_check, "REPO", str(tmp_path))
    assert consistency_check.check_flow_lock(locked) == []


def test_flow_lock_still_detects_content_change(tmp_path, monkeypatch):
    """Folding CRLF must not weaken the lock: any other change is caught."""
    locked = _locked_paths()
    _copy_with_crlf(tmp_path, [consistency_check.LOCK_PATH, *locked])
    with open(tmp_path / locked[0], "ab") as fh:
        fh.write(b"tampered\r\n")
    monkeypatch.setattr(consistency_check, "REPO", str(tmp_path))
    assert consistency_check.check_flow_lock(locked) == [
        f"flow lock: hash mismatch {locked[0]}"
    ]


def test_agent_refs_resolve_inside_an_extension_tree():
    """An extension-supplied agent is a live reference, not a dead one.

    ``seo-matomo`` ships only at ``extensions/matomo/agents/seo-matomo.md``
    (no core mirror, unlike ``seo-dataforseo``). Its installer copies it into
    ``~/.claude/agents/``, so the installers' ``agents/seo-matomo.md``
    mentions must resolve. Before this rule was path-aware, all three Matomo
    installer scripts were reported as dead agent refs.
    """
    files = ["agents/seo-technical.md", "extensions/matomo/agents/seo-matomo.md"]
    texts = ["extensions/matomo/install.sh"]
    assert consistency_check.check_agent_refs(files, texts) == []


def test_agent_refs_still_catch_a_genuinely_missing_agent():
    files = ["agents/seo-technical.md", "extensions/matomo/agents/seo-matomo.md"]
    errors = consistency_check.check_agent_refs(files, ["extensions/matomo/uninstall.sh"])
    assert errors == []
    # A name that exists in neither tree is still an error.
    original = consistency_check.read
    try:
        consistency_check.read = lambda rel, **kw: "see agents/seo-nonexistent.md"
        errors = consistency_check.check_agent_refs(files, ["docs/COMMANDS.md"])
    finally:
        consistency_check.read = original
    assert errors == ["docs/COMMANDS.md: dead agent ref agents/seo-nonexistent.md"]
