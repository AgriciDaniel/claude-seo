"""
Tests for scripts/dataforseo_costs.py — spend-ledger integrity.

Regression cover for the lost-update race: the ledger used to take its file
lock twice, once to read and once to write, and drop it in between, so two
concurrent `log` calls both read the same ledger and the second overwrote the
first. A budget ledger that quietly under-reports spend is the one thing it
must not do.

Every test runs against an isolated CLAUDE_SEO_CONFIG_DIR, never the real
~/.config/claude-seo/ ledger.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "scripts" / "dataforseo_costs.py"


def _run(config_dir: Path, *argv: str) -> subprocess.CompletedProcess:
    """Invoke the CLI in a subprocess with an isolated ledger."""
    env = dict(os.environ)
    env["CLAUDE_SEO_CONFIG_DIR"] = str(config_dir)
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *argv],
        capture_output=True,
        text=True,
        env=env,
    )


def _entries(config_dir: Path) -> list[dict]:
    return json.loads((config_dir / "dataforseo-ledger.json").read_text())["entries"]


# ---------------------------------------------------------------------------
# concurrency — the reported bug
# ---------------------------------------------------------------------------


def test_concurrent_logs_do_not_lose_entries(tmp_path) -> None:
    """20 concurrent `log` calls must produce exactly 20 entries.

    Fails on the pre-fix code, which loses entries whenever two processes
    interleave their read-modify-write.
    """
    calls = 20
    unit_cost = 0.01

    with ThreadPoolExecutor(max_workers=calls) as pool:
        results = list(
            pool.map(
                lambda i: _run(
                    tmp_path, "log", "serp_organic_live_advanced", str(unit_cost),
                    "--note", f"call-{i}",
                ),
                range(calls),
            )
        )

    failed = [r for r in results if r.returncode != 0]
    assert not failed, f"{len(failed)} log calls failed: {failed[0].stderr}"

    entries = _entries(tmp_path)
    assert len(entries) == calls, (
        f"lost {calls - len(entries)} of {calls} concurrent writes"
    )

    notes = sorted(e["note"] for e in entries)
    assert notes == sorted(f"call-{i}" for i in range(calls)), "entries were clobbered"

    total = sum(e["cost"] for e in entries)
    assert total == pytest.approx(calls * unit_cost), "recorded spend under-reports"


def test_concurrent_log_and_reset_keep_the_ledger_parseable(tmp_path) -> None:
    """Interleaved writers must never leave a torn/unparseable ledger."""
    _run(tmp_path, "log", "serp_organic_live_advanced", "0.01")

    def job(i: int) -> subprocess.CompletedProcess:
        if i % 5 == 4:
            return _run(tmp_path, "reset", "--confirm")
        return _run(tmp_path, "log", "serp_organic_live_advanced", "0.01")

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(job, range(10)))

    # The ledger must still be valid JSON with an entries list. Which entries
    # survive depends on reset ordering; that the file parses is the invariant.
    entries = _entries(tmp_path)
    assert isinstance(entries, list)

    result = json.loads(_run(tmp_path, "today").stdout)
    assert result["status"] == "today"


# ---------------------------------------------------------------------------
# durability
# ---------------------------------------------------------------------------


def test_corrupt_ledger_is_not_silently_zeroed(tmp_path) -> None:
    """A truncated ledger must fail closed, not restart the budget at zero.

    The old code caught JSONDecodeError and returned {"entries": []}, so the
    next write persisted an empty ledger and the entire spend history vanished.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    ledger = tmp_path / "dataforseo-ledger.json"
    ledger.write_text('{"entries": [{"timestamp": "2026-01-01T00:00:00", "cos')

    result = _run(tmp_path, "log", "serp_organic_live_advanced", "0.01")
    assert result.returncode != 0, "corrupt ledger must not be silently accepted"
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert "not valid JSON" in payload["message"]

    # The damaged file is left in place for inspection, not overwritten.
    assert ledger.read_text().endswith('"cos')


def test_today_totals_survive_a_write(tmp_path) -> None:
    """Basic round trip: logged spend is reflected in `today`."""
    _run(tmp_path, "log", "on_page_lighthouse", "0.02")
    _run(tmp_path, "log", "on_page_lighthouse", "0.03")

    payload = json.loads(_run(tmp_path, "today").stdout)
    assert payload["total_usd"] == pytest.approx(0.05)
    assert payload["calls"] == 2


def test_ledger_write_is_atomic_no_temp_files_left(tmp_path) -> None:
    """The tempfile used for the atomic replace must not accumulate."""
    for _ in range(5):
        _run(tmp_path, "log", "on_page_lighthouse", "0.02")

    leftovers = list(tmp_path.glob(".dataforseo-ledger.*.tmp"))
    assert leftovers == [], f"temp files left behind: {leftovers}"


# ---------------------------------------------------------------------------
# portability guard
# ---------------------------------------------------------------------------


def test_locking_is_never_disabled_unconditionally() -> None:
    """Guard against the `fcntl = None` regression.

    The module previously ran with no locking at all on Windows. It must now
    fall back to msvcrt and, failing that, refuse to touch the ledger.
    """
    source = _SCRIPT.read_text()
    assert "import msvcrt" in source, "no Windows locking fallback"
    assert "Refusing to touch the spend ledger unlocked" in source, (
        "module must fail closed when no locking primitive is available"
    )


def test_isolated_config_dir_is_honoured(tmp_path) -> None:
    """Tests must never write to the operator's real ledger."""
    _run(tmp_path, "log", "on_page_lighthouse", "0.02")
    assert (tmp_path / "dataforseo-ledger.json").exists()
