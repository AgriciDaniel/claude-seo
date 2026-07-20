"""Reference-graph consistency gate.

Runs scripts/consistency_check.py and asserts zero errors: no dead references/
research/script/agent refs, routing-table agreement, and FLOW lock integrity.
Warnings (orphan candidates) are allowed; errors are not. Added after the
2026-07 full review, which found dead ``scripts/presets.py`` invocations that
basename-level checking had masked.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "consistency_check.py")


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
