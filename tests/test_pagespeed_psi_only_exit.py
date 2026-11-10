"""Exit-code regression for scripts/pagespeed_check.py --psi-only.

--crux-only and the default combined check both surface a failure at the
top-level ``error`` key, so the final exit check (``sys.exit(1)`` when
``result.get("error")``) reports a non-zero status to a CI gate. The
--psi-only branch nested every failure under ``result["psi"][strat]["error"]``
and never set a top-level error, so the process always exited 0 even when
every PSI call failed. A pipeline gating on --psi-only got a false success.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("requests")

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pagespeed_check.py"

# A non-http(s) URL is rejected by the URL-safety guard inside run_pagespeed
# before any network call, so this reproduces a failing PSI run offline.
_BAD_URL = "ftp://example.com/"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), _BAD_URL, *args],
        capture_output=True, text=True,
    )


def test_psi_only_exits_nonzero_when_every_psi_call_fails() -> None:
    proc = _run(["--psi-only", "--strategy", "mobile", "--json"])
    assert proc.returncode == 1, (proc.returncode, proc.stdout, proc.stderr)
    payload = json.loads(proc.stdout)
    assert payload["psi"]["mobile"]["error"]  # the failure is still reported


def test_crux_only_control_already_exits_nonzero() -> None:
    # Control: the sibling branch (no API key) exits non-zero today.
    proc = _run(["--crux-only", "--json"])
    assert proc.returncode == 1
