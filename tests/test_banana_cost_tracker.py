"""
Tests for extensions/banana/scripts/cost_tracker.py — cost-ledger integrity.

Same defect class as tests/test_dataforseo_costs.py, and worse here: this
ledger had no file locking at all, non-atomic writes, and running aggregates
(total_cost, total_images, daily) that are incremented alongside each entry.
A lost write dropped the entry AND its aggregate increments together, so the
file stayed internally self-consistent while under-reporting spend. Internal
consistency is therefore not evidence that nothing was lost.

Every test runs against an isolated BANANA_HOME, never the real
~/.banana/costs.json.
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
_SCRIPT = _REPO / "extensions" / "banana" / "scripts" / "cost_tracker.py"

MODEL = "gemini-3.1-flash-image-preview"
COST_1K = 0.039


def _seed_pricing(home: Path) -> None:
    """Write the dated pricing config the tracker requires."""
    home.mkdir(parents=True, exist_ok=True)
    (home / "pricing.json").write_text(json.dumps({
        "checked_date": "2026-08-02",
        "models": {MODEL: {"512": 0.020, "1K": COST_1K, "2K": 0.078, "4K": 0.156}},
    }))


def _run(home: Path, *argv: str) -> subprocess.CompletedProcess:
    """Invoke the CLI in a subprocess with an isolated ledger."""
    if not (home / "pricing.json").exists():
        _seed_pricing(home)
    env = dict(os.environ)
    env["BANANA_HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *argv],
        capture_output=True,
        text=True,
        env=env,
    )


def _ledger(home: Path) -> dict:
    return json.loads((home / "costs.json").read_text())


# ---------------------------------------------------------------------------
# concurrency
# ---------------------------------------------------------------------------


def test_concurrent_logs_do_not_lose_entries(tmp_path) -> None:
    """20 concurrent `log` calls must produce exactly 20 entries.

    Fails on the pre-fix code, which had no locking whatsoever.
    """
    calls = 20

    with ThreadPoolExecutor(max_workers=calls) as pool:
        results = list(
            pool.map(
                lambda i: _run(
                    tmp_path, "log", "--model", MODEL, "--resolution", "1K",
                    "--prompt", f"call-{i}",
                ),
                range(calls),
            )
        )

    failed = [r for r in results if r.returncode != 0]
    assert not failed, f"{len(failed)} log calls failed: {failed[0].stderr}"

    ledger = _ledger(tmp_path)
    assert len(ledger["entries"]) == calls, (
        f"lost {calls - len(ledger['entries'])} of {calls} concurrent writes"
    )

    prompts = sorted(e["prompt"] for e in ledger["entries"])
    assert prompts == sorted(f"call-{i}" for i in range(calls)), "entries were clobbered"


def test_concurrent_logs_keep_aggregates_correct(tmp_path) -> None:
    """The running aggregates must match the entries after concurrent writes.

    These are the numbers the user actually reads, and they were incremented
    in the same lost write as the entry itself.
    """
    calls = 20

    with ThreadPoolExecutor(max_workers=calls) as pool:
        list(
            pool.map(
                lambda i: _run(
                    tmp_path, "log", "--model", MODEL, "--resolution", "1K",
                    "--prompt", f"call-{i}",
                ),
                range(calls),
            )
        )

    ledger = _ledger(tmp_path)
    assert ledger["total_images"] == calls
    assert ledger["total_cost"] == pytest.approx(calls * COST_1K, abs=1e-4)
    assert ledger["total_cost"] == pytest.approx(
        sum(e["cost"] for e in ledger["entries"]), abs=1e-4
    )

    daily_count = sum(d["count"] for d in ledger["daily"].values())
    daily_cost = sum(d["cost"] for d in ledger["daily"].values())
    assert daily_count == calls
    assert daily_cost == pytest.approx(calls * COST_1K, abs=1e-4)


def test_concurrent_log_and_reset_keep_the_ledger_parseable(tmp_path) -> None:
    """Interleaved writers must never leave a torn/unparseable ledger."""
    _run(tmp_path, "log", "--model", MODEL, "--resolution", "1K", "--prompt", "seed")

    def job(i: int) -> subprocess.CompletedProcess:
        if i % 5 == 4:
            return _run(tmp_path, "reset", "--confirm")
        return _run(tmp_path, "log", "--model", MODEL, "--resolution", "1K",
                    "--prompt", f"p{i}")

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(job, range(10)))

    ledger = _ledger(tmp_path)
    assert isinstance(ledger["entries"], list)
    assert _run(tmp_path, "summary").returncode == 0


# ---------------------------------------------------------------------------
# durability
# ---------------------------------------------------------------------------


def test_corrupt_ledger_is_not_silently_zeroed(tmp_path) -> None:
    """A truncated ledger must fail closed, not restart the budget at zero."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    ledger = tmp_path / "costs.json"
    ledger.write_text('{"entries": [{"ts": "2026-01-01T00:00:00", "cos')

    result = _run(tmp_path, "log", "--model", MODEL, "--resolution", "1K",
                  "--prompt", "x")
    assert result.returncode != 0, "corrupt ledger must not be silently accepted"
    assert "not valid JSON" in result.stderr

    # Left in place for inspection, not overwritten.
    assert ledger.read_text().endswith('"cos')


def test_reset_recovers_a_corrupt_ledger(tmp_path) -> None:
    """reset must not depend on the existing file parsing.

    It is the documented recovery path, so requiring a readable ledger first
    would leave a corrupt ledger unrecoverable through the CLI.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "costs.json").write_text("{ this is not json")

    assert _run(tmp_path, "reset", "--confirm").returncode == 0
    assert _ledger(tmp_path) == {
        "total_cost": 0.0, "total_images": 0, "entries": [], "daily": {},
    }


def test_ledger_write_is_atomic_no_temp_files_left(tmp_path) -> None:
    """The tempfile used for the atomic replace must not accumulate."""
    for i in range(5):
        _run(tmp_path, "log", "--model", MODEL, "--resolution", "1K",
             "--prompt", f"p{i}")

    leftovers = list(tmp_path.glob(".costs.*.tmp"))
    assert leftovers == [], f"temp files left behind: {leftovers}"


def test_missing_aggregate_fields_are_tolerated(tmp_path) -> None:
    """An older ledger without the aggregate keys must still be loggable."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "costs.json").write_text('{"entries": []}')

    assert _run(tmp_path, "log", "--model", MODEL, "--resolution", "1K",
                "--prompt", "x").returncode == 0
    ledger = _ledger(tmp_path)
    assert ledger["total_images"] == 1
    assert ledger["total_cost"] == pytest.approx(COST_1K)


# ---------------------------------------------------------------------------
# portability guard
# ---------------------------------------------------------------------------


def test_locking_is_never_disabled_unconditionally() -> None:
    """The tracker must never run the ledger unlocked on any platform."""
    source = _SCRIPT.read_text()
    assert "import fcntl" in source and "import msvcrt" in source
    assert "Refusing to touch the cost ledger unlocked" in source


def test_isolated_home_is_honoured(tmp_path) -> None:
    """Tests must never write to the operator's real ~/.banana ledger."""
    _run(tmp_path, "log", "--model", MODEL, "--resolution", "1K", "--prompt", "x")
    assert (tmp_path / "costs.json").exists()
